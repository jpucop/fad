import { promises as fs } from 'fs';
import path from 'path';
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import process from 'process';
import {
  cleanupSVG,
  parseColors,
  isEmptyColor,
  runSVGO,
  SVG,
} from '@iconify/tools';
import { getIconData } from '@iconify/utils';
import { iconToSVG } from '@iconify/utils/lib/svg/build';

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// === CLI toggle ===
const mode = process.argv[2] === 'individual' ? 'individual' : 'sprite';
console.log(`🔧 Mode: ${mode === 'individual' ? 'Individual SVGs' : 'SVG Sprite'}`);

// === Config ===
const iconPrefix = 'i-';
const iconRegEx = new RegExp(`\\b${iconPrefix}([a-z0-9]+)-([a-z0-9-]+)\\b`, 'g');
const htmlFile = path.join(__dirname, '../src/index.html');
const outputDir = path.join(__dirname, '../dist/icons');
const outputJson = path.join(__dirname, '../dist/icons.json');
const height = '1em';

// === Load HTML ===
const html = await fs.readFile(htmlFile, 'utf8');

// === Extract icon usage ===
const iconMap = {};

for (const [, prefix, name] of html.matchAll(iconRegEx)) {
  const icons = iconMap[prefix] ||= new Set();
  icons.add(name);
}

const totalFoundIconRefs = Object.values(iconMap).reduce((sum, set) => sum + set.size, 0);
const summary = Object.entries(iconMap).map(([prefix, set]) => `${prefix}(${set.size})`).join(', ');
console.log(`🔍 Found ${totalFoundIconRefs} icons: ${summary}`);

// === Ensure output dir exists ===
await fs.mkdir(outputDir, { recursive: true });

// === Main loop ===
const iconsJson = {};

let spriteContent = '<svg xmlns="http://www.w3.org/2000/svg" style="display:none;" aria-hidden="true">\n';

for (const [prefix, icons] of Object.entries(iconMap)) {
  const iconSetPath = resolveIconSetPath(prefix);
  if (!iconSetPath) continue;

  const iconSet = JSON.parse(await fs.readFile(iconSetPath, 'utf8'));

  for (const name of icons) {
    const data = getIconData(iconSet, name);
    if (!data) {
      console.warn(`⚠️  Missing icon: ${prefix}-${name}`);
      continue;
    }

    const svgObj = iconToSVG(data, { height });

    // Save metadata
    iconsJson[`${prefix}-${name}`] = {
      viewBox: svgObj.attributes.viewBox,
      body: svgObj.body,
    };

    if (mode === 'sprite') {
      // Append to sprite
      spriteContent += `  <symbol id="${prefix}-${name}" viewBox="${svgObj.attributes.viewBox}">${svgObj.body}</symbol>\n`;
    } else {
      // Create individual minified SVG file
      const rawSVG = `<svg viewBox="${svgObj.attributes.viewBox}" xmlns="http://www.w3.org/2000/svg">${svgObj.body}</svg>`;
      const svg = new SVG(rawSVG);

      await cleanupSVG(svg);
      await parseColors(svg, {
        defaultColor: 'currentColor',
        callback: (attr, colorStr, color) =>
          !color || isEmptyColor(color) ? colorStr : 'currentColor',
      });
      await runSVGO(svg);

      const outputPath = path.join(outputDir, `${prefix}-${name}.svg`);
      await fs.writeFile(outputPath, svg.toMinifiedString(), 'utf8');
    }
  }
}

if (mode === 'sprite') {
  spriteContent += '</svg>\n';
  await fs.writeFile(path.join(outputDir, 'sprite.svg'), spriteContent, 'utf8');
  console.log(`✅ Wrote SVG sprite with ${Object.keys(iconsJson).length} symbols`);
} else {
  console.log(`✅ Wrote ${Object.keys(iconsJson).length} individual SVGs`);
}

// === Write metadata JSON (for injection) ===
await fs.writeFile(outputJson, JSON.stringify(iconsJson, null, 2), 'utf8');

function resolveIconSetPath(prefix) {
  try {
    return require.resolve(`@iconify-json/${prefix}/icons.json`);
  } catch (err) {
    console.error(`❌ Cannot resolve icon set: ${prefix}`);
    return null;
  }
}
