import fs from 'fs';
import { execSync } from 'child_process';

const html = fs.readFileSync('./index.html', 'utf8');

const iconRegex = /data-icon="([^"]+)"/g;
const icons = new Set();

let match;
while ((match = iconRegex.exec(html))) {
  icons.add(match[1]);
}

if (icons.size === 0) {
  console.log('No icons found.');
  process.exit(0);
}

const iconList = [...icons].join(' ');

// Ensure js/ directory exists
fs.mkdirSync('./js', { recursive: true });

console.log(`Bundling icons: ${[...icons].join(', ')}`);
execSync(`iconify build --output js/icons.js ${iconList}`, { stdio: 'inherit' });
