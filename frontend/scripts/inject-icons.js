// inject-icons.js

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Config class to encapsulate input parameters
class Config {
  constructor() {
    this.dirname = path.dirname(fileURLToPath(import.meta.url));
    this.srcHtmlPath = path.join(this.dirname, '../src/index.html');
    this.distHtmlPath = path.join(this.dirname, '../dist/index.html');
    this.spritePath = path.join(this.dirname, '../dist/icons/icons.svg');
    this.iconsJsonPath = path.join(this.dirname, '../dist/icons.json');
    this.spriteUrl = '/dist/icons/icons.svg';
  }

  // Validate required files
  validate() {
    if (!fs.existsSync(this.srcHtmlPath)) {
      throw new Error('❌ Source HTML file not found: src/index.html');
    }
    if (!fs.existsSync(this.spritePath)) {
      throw new Error('❌ Sprite file not found. Run build:icons first.');
    }
    if (!fs.existsSync(this.iconsJsonPath)) {
      throw new Error('❌ Icons JSON file not found. Run build:icons first.');
    }
  }
}

// Replace <span> with <svg><use>
function replaceIconSpans(html, iconsData) {
  let updatedHtml = html;

  for (const iconName of Object.keys(iconsData)) {
    console.log(`Processing icon: ${iconName}`); // Debug logging
    // Extract prefix and name from iconName (e.g., 'i-mdi-cloud-outline' -> 'mdi', 'cloud-outline')
    const match = iconName.match(/^i-([a-z0-9]+)-([a-z0-9]+(?:-[a-z0-9]+)*)$/);
    if (!match) {
      console.warn(`⚠️ Invalid icon name format: ${iconName}`);
      continue;
    }
    const [, prefix, name] = match;

    // Regex to match <span> with the icon class
    const spanRegex = new RegExp(
      `<span\\s+class="([^"]*\\bi-${prefix}-${name}\\b[^"]*)"[^>]*>(.*?)</span>`,
      'g'
    );

    updatedHtml = updatedHtml.replace(spanRegex, (match, classNames) => {
      // Preserve all classes except the icon-specific class
      const cleanedClasses = classNames
        .split(/\s+/)
        .filter(cls => cls !== `i-${prefix}-${name}`)
        .join(' ');
      return `<svg class="icon ${cleanedClasses}" aria-hidden="true"><use href="#i-${prefix}-${name}"></use></svg>`;
    });
  }

  return updatedHtml;
}

async function injectIcons() {
  try {
    const config = new Config();
    config.validate();

    // Load files
    const html = fs.readFileSync(config.srcHtmlPath, 'utf8');
    const iconsData = JSON.parse(fs.readFileSync(config.iconsJsonPath, 'utf8'));

    // Replace icon spans
    let updatedHtml = replaceIconSpans(html, iconsData);

    // Write output
    fs.mkdirSync(path.dirname(config.distHtmlPath), { recursive: true });
    fs.writeFileSync(config.distHtmlPath, updatedHtml, 'utf8');

    console.log(`✅ Replaced icon spans and injected sprite loader into ${config.distHtmlPath}`);
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}

// Run
injectIcons();