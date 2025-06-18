import { cleanupSVG, parseColors, runSVGO, SVG } from '@iconify/tools';
import { getIconData, iconToSVG } from '@iconify/utils';
import fs from 'fs';
import path from 'path';
import { optimize } from 'svgo';
import { CONFIG } from './config.js';

// SVGO configuration for optimizing local SVGs during sprite generation
const svgoSpriteConfig = {
  plugins: [
    { name: 'removeDimensions' },
    { name: 'removeAttrs', params: { attrs: ['fill'] } },
    { name: 'convertTransform' },
    { name: 'cleanupNumericValues', params: { floatPrecision: 0 } },
    { name: 'removeUselessStrokeAndFill' },
    { name: 'mergePaths' },
    { name: 'removeXMLNS' },
  ],
};

// SVGO configuration for cleaning local SVGs
const svgoCleanConfig = {
  plugins: [
    'preset-default',
    { name: 'removeViewBox', active: false },
    { name: 'cleanupNumericValues', params: { floatPrecision: 3 } },
  ],
};

// Derived paths
const spritePath = path.join(CONFIG.paths.src, CONFIG.src.sprite);
const imgPath = path.join(CONFIG.paths.src, 'img');
const iconifyPath = path.join(CONFIG.paths.base, '../node_modules/@iconify-json');

// Validate config paths
function validateConfig() {
  const indexHtml = CONFIG.src.html.find(file => file === 'index.html');
  if (!indexHtml || !fs.existsSync(path.join(CONFIG.paths.src, indexHtml))) {
    throw new Error(`❌ index.html not found`);
  }
  if (!fs.existsSync(iconifyPath)) {
    throw new Error(`❌ Iconify packages not found: ${iconifyPath}`);
  }
  if (!fs.existsSync(imgPath)) {
    fs.mkdirSync(imgPath, { recursive: true });
    console.log(`✅ Created img directory: ${imgPath}`);
  }
}

// Extract icon refs from all HTML files
function extractIconRefs() {
  const matches = new Set();
  for (const htmlFile of CONFIG.src.html) {
    const htmlPath = path.join(CONFIG.paths.src, htmlFile);
    if (!fs.existsSync(htmlPath)) continue;
    const html = fs.readFileSync(htmlPath, 'utf8');
    const spans = html.match(CONFIG.iconConfig.spanRegex) || [];
    for (const span of spans) {
      const classMatch = span.match(/class="([^"]*)"/);
      if (classMatch) {
        const classes = classMatch[1].split(/\s+/);
        const iconClass = classes.find(cls => CONFIG.iconConfig.validateRegex.test(cls));
        if (iconClass && classes.includes('icon')) {
          matches.add(iconClass);
        }
      }
    }
  }
  const refs = Array.from(matches);
  const localRefs = refs.filter(ref => ref.startsWith('l-'));
  const iconifyRefs = refs.filter(ref => ref.startsWith('i-'));
  console.log(`✅ Found ${refs.length} icon refs across ${CONFIG.src.html.length} HTML files:`);
  console.log(`  - Iconify (${iconifyRefs.length}): ${iconifyRefs.join(', ') || 'none'}`);
  console.log(`  - Local (${localRefs.length}): ${localRefs.join(', ') || 'none'}`);
  return refs;
}

// Load Iconify icon set
function loadIconSet(packageName) {
  const iconSetPath = path.join(iconifyPath, `${packageName}/icons.json`);
  if (!fs.existsSync(iconSetPath)) {
    throw new Error(`❌ Iconify package not found: ${iconSetPath}`);
  }
  const raw = fs.readFileSync(iconSetPath, 'utf8');
  const json = JSON.parse(raw);
  if (!json.icons) {
    throw new Error(`❌ Invalid icon set in ${packageName}`);
  }
  return json;
}

// Calculate viewBox from SVG paths
function calculateViewBox(svgContent) {
  const pathRegex = /d="([^"]+)"/g;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

  let match;
  while ((match = pathRegex.exec(svgContent)) !== null) {
    const d = match[1];
    const coords = d.match(/[\d.-]+/g)?.map(Number) || [];
    for (let i = 0; i < coords.length; i += 2) {
      const x = coords[i];
      const y = coords[i + 1];
      if (!isNaN(x) && !isNaN(y)) {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
      }
    }
  }

  if (minX === Infinity || minY === Infinity || maxX === -Infinity || maxY === -Infinity) {
    return '0 0 24 24';
  }

  const padding = 10;
  const width = maxX - minX;
  const height = maxY - minY;
  return `${minX - padding} ${minY - padding} ${width + 2 * padding} ${height + 2 * padding}`;
}

// Process Iconify icon
function processIconifyIcon(iconSet, name, ref) {
  console.log(`✅ Processing Iconify icon: ${ref}`);
  const iconData = getIconData(iconSet, name);
  if (!iconData) {
    throw new Error(`❌ Icon not found: ${name}`);
  }

  const svgObj = iconToSVG(iconData, {
    height: '1em',
    width: 'auto',
  });

  const viewBox = svgObj.attributes.viewBox || '0 0 24 24';
  let body = svgObj.body;

  const svg = new SVG(`<svg viewBox="${viewBox}" xmlns="http://www.w3.org/2000/svg">${body}</svg>`);
  cleanupSVG(svg);
  parseColors(svg, {
    defaultColor: 'currentColor',
    callback: (attr, colorStr, color) => !color || color === 'none' ? colorStr : 'currentColor',
  });
  runSVGO(svg);

  body = svg.getBody();

  const symbol = `<symbol id="${ref}" viewBox="${viewBox}">${body}</symbol>`;
  return symbol;
}

// Process local SVG
function processLocalSVG(name, ref) {
  console.log(`✅ Processing local icon: ${ref}`);
  const svgPath = path.join(imgPath, `${name}.svg`);
  if (!fs.existsSync(svgPath)) {
    throw new Error(`❌ Local icon file not found: ${svgPath}`);
  }
  let svg = fs.readFileSync(svgPath, 'utf8');

  svg = svg.replace(/<\?xml[^?]*\?>\s*/, '');
  const optimizedSvg = optimize(svg, svgoSpriteConfig).data;

  const viewBoxMatch = optimizedSvg.match(/viewBox="([^"]+)"/);
  let viewBox = viewBoxMatch ? viewBoxMatch[1] : calculateViewBox(optimizedSvg);

  const content = optimizedSvg
    .replace(/^<svg[^>]*>/, '')
    .replace(/<\/svg>\s*$/, '')
    .trim();

  if (!content) {
    throw new Error(`❌ No valid SVG content found in ${svgPath}`);
  }

  const symbol = `<symbol id="${ref}" viewBox="${viewBox}">${content}</symbol>`;
  return symbol;
}

// Clean local SVGs
export async function cleanLocalSvgs() {
  try {
    if (!fs.existsSync(imgPath)) {
      console.warn(`⚠️ Directory not found: ${imgPath}, creating it`);
      fs.mkdirSync(imgPath, { recursive: true });
      console.log('ℹ️ No img directory, nothing to clean');
      return;
    }

    const files = fs.readdirSync(imgPath).filter(f => f.endsWith('.svg'));
    if (files.length === 0) {
      console.log('ℹ️ No SVGs found in src/img/');
      return;
    }

    console.log(`📋 Found ${files.length} SVGs: ${files.join(', ')}`);
    for (const file of files) {
      const filePath = path.join(imgPath, file);
      try {
        console.log(`🔄 Processing: ${path.basename(filePath)}`);
        let svgContent = fs.readFileSync(filePath, 'utf8')
          .replace(/<\?xml[^?]*\?>\s*/, '')
          .replace(/<!DOCTYPE[^>]*>\s*/, '');

        // Iconify cleanup
        const svg = new SVG(svgContent);
        cleanupSVG(svg);
        parseColors(svg, {
          defaultColor: 'currentColor',
          callback: (attr, colorStr, color) => color && color !== 'none' ? 'currentColor' : colorStr,
        });

        // SVGO optimization
        const svgoResult = optimize(svg.toMinifiedString(), svgoCleanConfig);
        if (!svgoResult.data.includes('<svg')) {
          throw new Error('Invalid SVG after SVGO');
        }

        fs.writeFileSync(filePath, svgoResult.data, 'utf8');
        console.log(`✅ Cleaned and optimized: ${path.basename(filePath)}`);
      } catch (err) {
        console.error(`❌ Error cleaning ${path.basename(filePath)}: ${err.message}`);
      }
    }

    console.log('✅ All SVGs cleaned');
  } catch (err) {
    console.error(`❌ Cleaning failed: ${err.message}`);
    throw err;
  }
}

export function validateSprite() {
  validateConfig();

  // Get icon classes from all HTML files
  const iconClasses = extractIconRefs();

  // Get symbol IDs from sprite.svg
  let symbolIds = new Set();
  if (fs.existsSync(spritePath)) {
    const spriteContent = fs.readFileSync(spritePath, 'utf8');
    let match;
    while ((match = CONFIG.iconConfig.symbolRegex.exec(spriteContent))) {
      symbolIds.add(match[1]);
    }
  }
  console.log(`✅ Found ${symbolIds.size} symbols in sprite.svg: ${[...symbolIds].join(', ') || 'none'}`);

  // Warn about missing and unused icons
  const missingIcons = iconClasses.filter(id => !symbolIds.has(id));
  const unusedIcons = [...symbolIds].filter(id => !iconClasses.includes(id));

  if (missingIcons.length || unusedIcons.length || !fs.existsSync(spritePath)) {
    console.warn(`⚠️ Sprite issues: ${missingIcons.length} missing, ${unusedIcons.length} unused`);
    if (missingIcons.length) console.warn(`⚠️ Missing icons: ${missingIcons.join(', ')}`);
    if (unusedIcons.length) console.warn(`⚠️ Unused icons: ${unusedIcons.join(', ')}`);
    console.log('✅ Rebuilding sprite.svg...');
    generateSprite(iconClasses);
  } else {
    console.log('✅ Sprite validation passed');
  }
}

async function generateSprite(requiredIcons) {
  const symbols = [];
  const usedIds = new Set();

  for (const ref of requiredIcons) {
    try {
      if (ref.startsWith('i-')) {
        const match = ref.match(/^i-([a-z0-9]+)-([a-z0-9]+(?:-[a-z0-9]+)*)$/);
        if (!match) {
          console.warn(`⚠️ Invalid Iconify ref: ${ref}`);
          continue;
        }
        const [, pkg, name] = match;
        const iconSet = loadIconSet(pkg);
        const symbol = processIconifyIcon(iconSet, name, ref);
        if (!usedIds.has(ref)) {
          symbols.push(symbol);
          usedIds.add(ref);
          console.log(`✅ Added Iconify symbol to sprite: ${ref}`);
        }
      } else if (ref.startsWith('l-')) {
        const name = ref.slice(2);
        const symbol = processLocalSVG(name, ref);
        if (!usedIds.has(ref)) {
          symbols.push(symbol);
          usedIds.add(ref);
          console.log(`✅ Added local symbol to sprite: ${ref}`);
        }
      } else {
        console.warn(`⚠️ Unknown icon ref format: ${ref}`);
      }
    } catch (err) {
      console.error(`❌ Error processing ${ref}: ${err.message}`);
      continue;
    }
  }

  if (symbols.length > 0) {
    const spriteContent = `<svg xmlns="http://www.w3.org/2000/svg" style="display:none">\n${symbols.join('\n')}\n</svg>`;
    fs.mkdirSync(path.dirname(spritePath), { recursive: true });
    fs.writeFileSync(spritePath, spriteContent, 'utf8');
    console.log(`✅ Sprite generated: ${spritePath} (${symbols.length} symbols)`);
  } else {
    console.warn(`⚠️ No symbols generated for sprite`);
    fs.writeFileSync(spritePath, '<svg></svg>', 'utf8');
    console.log(`✅ Empty sprite generated: ${spritePath}`);
  }
}

function buildSprite() {
  try {
    validateSprite();
    console.log('✅ Sprite build completed');
  } catch (err) {
    console.error(`❌ Sprite build failed: ${err.message}`);
    process.exit(1);
  }
}

buildSprite();