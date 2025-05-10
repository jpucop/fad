import { promises as fs } from 'fs';
import path from 'path';
import { createRequire } from 'module';
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

// Config
const iconPrefix = 'i-';
const iconRegEx = new RegExp(`\\b${iconPrefix}([a-z0-9]+)-([a-z0-9-]+)\\b`, 'g');
const htmlFile = './src/index.html';
const outputDir = './dist/icons';
const height = '1em';

// Load HTML source
const html = await fs.readFile(htmlFile, 'utf8');

// Find icon matches: i-<prefix>-<icon-name>
const iconMap = {};

for (const [, prefix, name] of html.matchAll(iconRegEx)) {
  const icons = iconMap[prefix] ||= new Set();
  icons.add(name);
}

// Summarize findings
const foundIconsSummaryByPrefix = Object.entries(iconMap)
  .map(([prefix, icons]) => `${prefix}(${icons.size})`)
  .join(', ');

const totalFoundIconRefs = Object.values(iconMap)
  .reduce((sum, set) => sum + set.size, 0);

console.log(`🔍 Found ${totalFoundIconRefs} icons: ${foundIconsSummaryByPrefix}`);

// Ensure output directory exists
await fs.mkdir(outputDir, { recursive: true });

// Generate and write SVG files
for (const [prefix, icons] of Object.entries(iconMap)) {
  const jsonPath = resolveIconSetPath(prefix);
  if (!jsonPath) continue;

  const iconSet = JSON.parse(await fs.readFile(jsonPath, 'utf8'));

  for (const name of icons) {
    const data = getIconData(iconSet, name);
    if (!data) {
      console.warn(`⚠️  Missing: ${prefix}-${name}`);
      continue;
    }

    const svgObj = iconToSVG(data, { height });

    const svg = new SVG(
      `<svg ${Object.entries(svgObj.attributes)
        .map(([k, v]) => `${k}="${v}"`)
        .join(' ')}>${svgObj.body}</svg>`
    );

    await cleanupSVG(svg);
    await parseColors(svg, {
      defaultColor: 'currentColor',
      callback: (attr, colorStr, color) => {
        return !color || isEmptyColor(color) ? colorStr : 'currentColor';
      },
    });
    await runSVGO(svg);
    const svgStr = svg.toMinifiedString();

    const outputPath = path.join(outputDir, `${prefix}-${name}.svg`);
    await fs.writeFile(outputPath, svgStr, 'utf8');
  }
}

console.log(`✅ Icons saved to ${outputDir}`);

function resolveIconSetPath(prefix) {
  try {
    return require.resolve(`@iconify-json/${prefix}/icons.json`);
  } catch (err) {
    console.error(`❌ Cannot find icon set: ${prefix}`);
    return null;
  }
}
