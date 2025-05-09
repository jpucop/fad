import { parseIconSet } from '@iconify/utils';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { optimize } from 'svgo';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlPath = path.join(__dirname, '../index.html');
const iconsDataPath = path.join(__dirname, '../dist/icons.json');

// Read MDI icon set
let mdi;
try {
  mdi = JSON.parse(fs.readFileSync(
    path.join(__dirname, '../node_modules/@iconify-json/mdi/icons.json'),
    'utf8'
  ));
} catch (err) {
  console.error(`❌ Error reading MDI icons: ${err.message}`);
  process.exit(1);
}

// Read source HTML
let html;
try {
  html = fs.readFileSync(htmlPath, 'utf8');
} catch (err) {
  console.error(`❌ Error reading index.html: ${err.message}`);
  process.exit(1);
}

// Find icon classes (e.g., i-mdi-account-multiple-outline)
const iconRegex = /i-mdi-([\w-]+)/g;
const icons = new Set();
let match;
while ((match = iconRegex.exec(html))) {
  icons.add(match[1]);
}

if (icons.size === 0) {
  console.log('No MDI icons found in index.html.');
  fs.mkdirSync(path.dirname(iconsDataPath), { recursive: true });
  fs.writeFileSync(iconsDataPath, '{}');
  process.exit(0);
}

console.log(`Found ${icons.size} unique MDI icons:`, [...icons]);

// Parse MDI icon set
const parsedIcons = {};
parseIconSet(mdi, (name, data) => {
  parsedIcons[name] = data;
});

// Generate icon data
const iconsData = {};
const missingIcons = [];
for (const iconName of icons) {
  const icon = parsedIcons[iconName];
  if (!icon) {
    missingIcons.push(iconName);
    continue;
  }
  const width = icon.width || 24;
  const height = icon.height || 24;
  const viewBox = `0 0 ${width} ${height}`;
  // Create SVG for optimization
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}">${icon.body}</svg>`;
  // Optimize with SVGO
  const optimized = optimize(svg, {
    plugins: [
      { name: 'preset-default' },
      { name: 'removeAttrs', params: { attrs: '(fill|stroke)' } },
      { name: 'addAttributesToSVGElement', params: { attributes: [{ fill: 'currentColor' }] } },
    ],
  });
  // Extract body (remove <svg> wrapper)
  const body = optimized.data.replace(/<svg[^>]*>|<\/svg>/g, '');
  iconsData[iconName] = { viewBox, body };
}

if (missingIcons.length > 0) {
  console.warn(`⚠️ ${missingIcons.length} icons not found in MDI set:`, missingIcons);
}

// Write icon data
fs.mkdirSync(path.dirname(iconsDataPath), { recursive: true });
fs.writeFileSync(iconsDataPath, JSON.stringify(iconsData, null, 2));
console.log(`✅ Generated data for ${Object.keys(iconsData).length} icons in dist/icons.json`);