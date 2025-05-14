// build-icons.js

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { iconToSVG, getIconData } from '@iconify/utils';
import { cleanupSVG, parseColors, runSVGO, SVG } from '@iconify/tools';
import { optimize } from 'svgo';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const modeArg = process.argv[2];
const validModes = ['s', 'i', 'a'];
const mode = validModes.includes(modeArg) ? modeArg : 's';

console.log(`🛠️ Build mode: ${mode} (s=sprite, i=individual, a=both)`);

// CONFIG
const config = {
  htmlPath: path.join(__dirname, '../src/index.html'),
  outputDir: path.join(__dirname, '../dist/icons'),
  iconsJsonPath: path.join(__dirname, '../dist/icons.json'),
  iconifyPath: path.join(__dirname, '../node_modules/@iconify-json'),
  localIconsPath: path.join(__dirname, '../src/icons'),
  svgNs: 'http://www.w3.org/2000/svg',
};

// SVGO configuration for optimizing local SVGs
const svgoConfig = {
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

// Validate config paths
function validateConfig() {
  if (!fs.existsSync(config.htmlPath)) {
    throw new Error(`❌ HTML file not found: ${config.htmlPath}`);
  }
  if (!fs.existsSync(config.iconifyPath)) {
    throw new Error(`❌ Iconify packages not found: ${config.iconifyPath}`);
  }
  if (!fs.existsSync(config.localIconsPath)) {
    console.warn(`⚠️ Local icons directory not found: ${config.localIconsPath}, creating it`);
    fs.mkdirSync(config.localIconsPath, { recursive: true });
  }
}

// Extract icon refs from HTML (matches i-prefix-name and l-name)
function extractIconRefs(html) {
  const regex = /class="[^"]*\b((?:i-[a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*|l-[a-z0-9-]+))\b[^"]*"/g;
  const matches = new Set();
  for (const match of html.matchAll(regex)) {
    matches.add(match[1]);
  }
  const refs = Array.from(matches);
  const localRefs = refs.filter((ref) => ref.startsWith('l-'));
  const iconifyRefs = refs.filter((ref) => ref.startsWith('i-'));
  console.log(`📋 Found ${refs.length} icon refs:`);
  console.log(`  - Iconify (${iconifyRefs.length}): ${iconifyRefs.join(', ') || 'none'}`);
  console.log(`  - Local (${localRefs.length}): ${localRefs.join(', ') || 'none'}`);
  return refs;
}

// Load Iconify icon set
function loadIconSet(packageName) {
  const iconSetPath = path.join(config.iconifyPath, `${packageName}/icons.json`);
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

// Generate SVG and symbol for Iconify icon
function processIconifyIcon(iconSet, name, ref) {
  console.log(`🔄 Processing Iconify icon: ${ref}`);
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

  const svg = new SVG(`<svg viewBox="${viewBox}" xmlns="${config.svgNs}">${body}</svg>`);
  cleanupSVG(svg);
  parseColors(svg, {
    defaultColor: 'currentColor',
    callback: (attr, colorStr, color) => {
      return !color || color === 'none' ? colorStr : 'currentColor';
    },
  });
  runSVGO(svg);

  body = svg.getBody();

  const svgString = `<svg viewBox="${viewBox}" width="1em" height="1em" xmlns="${config.svgNs}">${body}</svg>`;
  const symbol = `<symbol id="${ref}" viewBox="${viewBox}">${body}</symbol>`;

  return { svg: svgString, symbol };
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

// Load and process local SVG
function processLocalSVG(name, ref) {
  console.log(`🔄 Processing local icon: ${ref}`);
  const svgPath = path.join(config.localIconsPath, `${name}.svg`);
  console.log(`📂 Checking file: ${svgPath}`);
  if (!fs.existsSync(svgPath)) {
    throw new Error(`❌ Local icon file not found: ${svgPath}`);
  }
  let svg = fs.readFileSync(svgPath, 'utf8');
  console.log(`📄 Loaded SVG content for ${ref} (${svg.length} bytes)`);

  svg = svg.replace(/<\?xml[^?]*\?>\s*/, '');

  const optimizedSvg = optimize(svg, svgoConfig).data;

  const viewBoxMatch = optimizedSvg.match(/viewBox="([^"]+)"/);
  let viewBox = viewBoxMatch ? viewBoxMatch[1] : calculateViewBox(optimizedSvg);

  const content = optimizedSvg
    .replace(/^<svg[^>]*>/, '')
    .replace(/<\/svg>\s*$/, '')
    .trim();

  if (!content) {
    throw new Error(`❌ No valid SVG content found in ${svgPath}`);
  }

  const svgOutput = `<svg viewBox="${viewBox}" width="1em" height="1em" xmlns="${config.svgNs}">${content}</svg>`;
  const symbol = `<symbol id="${ref}" viewBox="${viewBox}">${content}</symbol>`;
  console.log(`✅ Generated symbol for ${ref}`);
  return { svg: svgOutput, symbol };
}

// MAIN build function
function build() {
  validateConfig();
  const html = fs.readFileSync(config.htmlPath, 'utf8');
  const iconRefs = extractIconRefs(html);

  const icons = {};
  const spriteSymbols = [];

  for (const ref of iconRefs) {
    try {
      if (ref.startsWith('i-')) {
        const match = ref.match(/^i-([a-z0-9]+)-([a-z0-9]+(?:-[a-z0-9]+)*)$/);
        if (!match) {
          console.warn(`⚠️ Invalid Iconify ref: ${ref}`);
          continue;
        }
        const [, pkg, name] = match;
        const iconSet = loadIconSet(pkg);
        const { svg, symbol } = processIconifyIcon(iconSet, name, ref);
        icons[ref] = svg;
        if (mode !== 'i') {
          spriteSymbols.push(symbol);
          console.log(`✅ Added Iconify symbol to sprite: ${ref}`);
        }
        if (mode !== 's') {
          const filePath = path.join(config.outputDir, `${ref}.svg`);
          fs.writeFileSync(filePath, svg, 'utf8');
          console.log(`📄 Wrote individual SVG: ${filePath}`);
        }
      } else if (ref.startsWith('l-')) {
        const name = ref.slice(2);
        const { svg, symbol } = processLocalSVG(name, ref);
        icons[ref] = svg;
        if (mode !== 'i') {
          spriteSymbols.push(symbol);
          console.log(`✅ Added local symbol to sprite: ${ref}`);
        }
        if (mode !== 's') {
          const filePath = path.join(config.outputDir, `${ref}.svg`);
          fs.writeFileSync(filePath, svg, 'utf8');
          console.log(`📄 Wrote individual SVG: ${filePath}`);
        }
      } else {
        console.warn(`⚠️ Unknown icon ref format: ${ref}`);
      }
    } catch (err) {
      console.error(`❌ Error processing ${ref}: ${err.message}`);
      continue;
    }
  }

  if (mode !== 'i' && spriteSymbols.length > 0) {
    const spriteContent = `<svg xmlns="${config.svgNs}" style="display:none">\n${spriteSymbols.join('\n')}\n</svg>`;
    const spritePath = path.join(config.outputDir, 'icons.svg');
    fs.mkdirSync(config.outputDir, { recursive: true });
    fs.writeFileSync(spritePath, spriteContent, 'utf8');
    console.log(`✅ Sprite written: ${spritePath} (${spriteSymbols.length} symbols)`);
  } else if (mode !== 'i') {
    console.warn(`⚠️ No symbols generated for sprite`);
  }

  if (Object.keys(icons).length > 0) {
    fs.writeFileSync(config.iconsJsonPath, JSON.stringify(icons, null, 2), 'utf8');
    console.log(`✅ icons.json written: ${config.iconsJsonPath} (${Object.keys(icons).length} icons)`);
  } else {
    console.warn(`⚠️ No icons generated for icons.json`);
  }
}

try {
  build();
} catch (err) {
  console.error(`❌ Build failed: ${err.message}`);
  process.exit(1);
}