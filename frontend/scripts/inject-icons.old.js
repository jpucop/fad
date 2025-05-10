import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlPath = path.join(__dirname, '../index.html');
const distHtmlPath = path.join(__dirname, '../dist/index.html');
const iconsDataPath = path.join(__dirname, '../dist/icons.json');

// Read icons data
let iconsData;
try {
  iconsData = JSON.parse(fs.readFileSync(iconsDataPath, 'utf8'));
} catch (err) {
  console.error('❌ Error reading icons.json. Run build:icons first.');
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

// Generate SVG sprite
let sprite = '<svg style="display: none;" aria-hidden="true">\n';
const missingIcons = [];
for (const [iconName, icon] of Object.entries(iconsData)) {
  if (!icon.body) {
    missingIcons.push(iconName);
    continue;
  }
  sprite += `  <symbol id="mdi-${iconName}" viewBox="${icon.viewBox}">${icon.body}</symbol>\n`;
}
sprite += '</svg>\n';

if (missingIcons.length > 0) {
  console.warn(`⚠️ ${missingIcons.length} icons missing data:`, missingIcons);
}

// Replace <span> with <svg><use>
for (const iconName of Object.keys(iconsData)) {
  const spanRegex = new RegExp(
    `<span\\s+class="([^"]*\\bi-mdi-${iconName}\\b[^"]*)"[^>]*>(.*?)</span>`,
    'g'
  );
  html = html.replace(spanRegex, (match, classNames) => {
    const classes = classNames
      .split(/\s+/)
      .filter(cls => cls !== `i-mdi-${iconName}`)
      .join(' ');
    return `<svg class="icon ${classes}" aria-hidden="true"><use href="#mdi-${iconName}"></use></svg>`;
  });
}

// Inject sprite at placeholder
const placeholder = '<!-- SVG_SPRITE_PLACEHOLDER -->';
if (!html.includes(placeholder)) {
  console.error('❌ SVG sprite placeholder not found in index.html.');
  process.exit(1);
}
html = html.replace(placeholder, sprite);

// Write updated HTML
fs.mkdirSync(path.dirname(distHtmlPath), { recursive: true });
fs.writeFileSync(distHtmlPath, html);
console.log(`✅ Injected SVG sprite with ${Object.keys(iconsData).length - missingIcons.length} icons into dist/index.html`);