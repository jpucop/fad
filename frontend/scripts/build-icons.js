// build-icons.js

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { iconToSVG } from '@iconify/utils';
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
};

// SVGO configuration for optimizing local SVGs
const svgoConfig = {
  plugins: [
    { name: 'removeDimensions' }, // Remove width/height attributes
    { name: 'removeAttrs', params: { attrs: ['fill'] } }, // Remove fill attributes
    { name: 'convertTransform' }, // Bake transforms into path data
    { name: 'cleanupNumericValues', params: { floatPrecision: 0 } }, // Reduce precision to integers
    { name: 'removeUselessStrokeAndFill' }, // Remove unnecessary stroke/fill
    { name: 'mergePaths' }, // Merge paths where possible (careful with visual impact)
    { name: 'removeXMLNS' }, // Remove xmlns (we set it in the sprite)
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
    console.warn(`⚠️ Local icons directory not found: ${config.localIconsPath}`);
  }
}

// Extract icon refs from HTML (matches i-prefix-name and l-name)
function extractIconRefs(html) {
  const regex = /class="[^"]*\b((?:i-[a-z0-9]+-[a-z0-9-]+|l-[a-z0-9-]+))\b[^"]*"/g;
  const matches = new Set();
  for (const match of html.matchAll(regex)) {
    matches.add(match[1]);
  }
  const refs = Array.from(matches);
  console.log(`📋 Found ${refs.length} icon refs: ${refs.join(', ')}`);
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
  const iconData = iconSet.icons[name];
  if (!iconData) {
    throw new Error(`❌ Icon not found: ${name}`);
  }

  const { attributes, body } = iconToSVG(iconData, {
    height: '1em',
    width: '1em',
  });

  const viewBox = attributes.viewBox || '0 0 24 24';
  const svg = `<svg viewBox="${viewBox}" width="1em" height="1em">${body}</svg>`;
  const symbol = `<symbol id="${ref}" viewBox="${viewBox}">${body}</symbol>`;

  return { svg, symbol };
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
    return '0 0 24 24'; // Fallback if no valid coordinates found
  }

  const padding = 10;
  const width = maxX - minX;
  const height = maxY - minY;
  return `${minX - padding} ${minY - padding} ${width + 2 * padding} ${height + 2 * padding}`;
}

// Load and process local SVG
function processLocalSVG(name, ref) {
  const svgPath = path.join(config.localIconsPath, `${name}.svg`);
  if (!fs.existsSync(svgPath)) {
    throw new Error(`❌ Local icon not found: ${svgPath}`);
  }
  let svg = fs.readFileSync(svgPath, 'utf8');

  // Remove XML declaration
  svg = svg.replace(/<\?xml[^?]*\?>\s*/, '');

  // Optimize SVG with SVGO
  const optimizedSvg = optimize(svg, svgoConfig).data;

  // Extract viewBox or calculate it
  const viewBoxMatch = optimizedSvg.match(/viewBox="([^"]+)"/);
  let viewBox = viewBoxMatch ? viewBoxMatch[1] : calculateViewBox(optimizedSvg);

  // Extract SVG content (remove <svg> tags and any leading/trailing whitespace)
  const content = optimizedSvg
    .replace(/^<svg[^>]*>/, '')
    .replace(/<\/svg>\s*$/, '')
    .trim();

  // Validate content
  if (!content) {
    throw new Error(`❌ No valid SVG content found in ${svgPath}`);
  }

  // Reconstruct SVG for individual output (if needed)
  const svgOutput = `<svg viewBox="${viewBox}" width="1em" height="1em">${content}</svg>`;
  const symbol = `<symbol id="${ref}" viewBox="${viewBox}">${content}</symbol>`;
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
        const match = ref.match(/^i-([a-z0-9]+)-([a-z0-9-]+)$/);
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
    }
  }

  // Write sprite
  if (mode !== 'i' && spriteSymbols.length > 0) {
    // Minify sprite output by removing unnecessary whitespace
    const spriteContent = `<svg xmlns="http://www.w3.org/2000/svg" style="display:none">${spriteSymbols.join('')}</svg>`;
    const spritePath = path.join(config.outputDir, 'icons.svg');
    fs.mkdirSync(config.outputDir, { recursive: true });
    fs.writeFileSync(spritePath, spriteContent, 'utf8');
    console.log(`✅ Sprite written: ${spritePath} (${spriteSymbols.length} symbols)`);
  } else if (mode !== 'i') {
    console.warn(`⚠️ No symbols generated for sprite`);
  }

  // Write icons.json
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