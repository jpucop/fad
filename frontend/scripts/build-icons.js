// scripts/build-icons.js
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { parseIconSet } from '@iconify/utils';

import logos from '@iconify-json/logos/icons.json';
import mdi from '@iconify-json/mdi/icons.json'; // Add more sets as needed

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlPath = path.join(__dirname, '../index.html');
const jsOutputPath = path.join(__dirname, '../dist/js/icons.js');

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

// Map of collection => [icon names]
const collectionMap = new Map();

for (const name of icons) {
  const [collection, icon] = name.split(':');
  if (!collection || !icon) continue;
  if (!collectionMap.has(collection)) {
    collectionMap.set(collection, []);
  }
  collectionMap.get(collection).push(icon);
}

// Registry of known sets (manually extendable)
const sets = {
  logos,
  mdi
};

const output = {};

for (const [collection, names] of collectionMap.entries()) {
  const set = sets[collection];
  if (!set) {
    console.warn(`⚠️ Icon set "${collection}" not loaded. Skipping...`);
    continue;
  }

  const parsed = parseIconSet(set);
  for (const name of names) {
    const icon = parsed.resolve(name);
    if (icon) {
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${icon.attributes.viewBox}">${icon.body}</svg>`;
      output[`${collection}:${name}`] = svg;
    } else {
      console.warn(`⚠️ Icon "${collection}:${name}" not found.`);
    }
  }
}

fs.mkdirSync(path.dirname(jsOutputPath), { recursive: true });
fs.writeFileSync(jsOutputPath, `window.IconifyIcons = ${JSON.stringify(output, null, 2)};`);

console.log(`✅ Built ${Object.keys(output).length} icons into dist/js/icons.js`);
