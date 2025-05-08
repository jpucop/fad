import { parseIconSet } from '@iconify/utils';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlPath = path.join(__dirname, '../index.html');
const jsOutputPath = path.join(__dirname, '../dist/js/icons.js');

// Read JSON manually — avoids all import assertion bugs
const logos = JSON.parse(fs.readFileSync(
  path.join(__dirname, '../node_modules/@iconify-json/logos/icons.json'),
  'utf8'
));
const mdi = JSON.parse(fs.readFileSync(
  path.join(__dirname, '../node_modules/@iconify-json/mdi/icons.json'),
  'utf8'
));

const html = fs.readFileSync(htmlPath, 'utf8');
const iconRegex = /data-icon="([^"]+)"/g;
const icons = new Set();

let match;
while ((match = iconRegex.exec(html))) {
  icons.add(match[1]);
}

if (icons.size === 0) {
  console.log('No icons found in index.html.');
  process.exit(0);
}

const collectionMap = new Map();
for (const name of icons) {
  const [collection, icon] = name.split(':');
  if (!collection || !icon) continue;
  if (!collectionMap.has(collection)) {
    collectionMap.set(collection, []);
  }
  collectionMap.get(collection).push(icon);
}

const sets = { logos, mdi };
const output = {};

for (const [collection, names] of collectionMap.entries()) {
  const set = sets[collection];
  if (!set) {
    console.warn(`Icon set "${collection}" not loaded. Skipping...`);
    continue;
  }

  const parsed = {};
  parseIconSet(set, (name, data) => {
    parsed[name] = data;
  });
  for (const name of names) {
    const icon = parsed[name];
    if (icon) {
      const width = icon.width || 16;
      const height = icon.height || 16;
      const viewBox = `0 0 ${width} ${height}`;
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}">${icon.body}</svg>`;
      output[`${collection}:${name}`] = svg;
    } else {
      console.warn(`Icon "${collection}:${name}" not found.`);
    }
  }
}

fs.mkdirSync(path.dirname(jsOutputPath), { recursive: true });
fs.writeFileSync(jsOutputPath, `window.IconifyIcons = ${JSON.stringify(output, null, 2)};`);
console.log(`Iconified ${Object.keys(output).length} icon(s) to SVGs.`);
