// inject-icons.js

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Config class
class Config {
  constructor() {
    this.dirname = path.dirname(fileURLToPath(import.meta.url));
    this.srcHtmlPath = path.join(this.dirname, '../src/index.html');
    this.distHtmlPath = path.join(this.dirname, '../dist/index.html');
    this.spritePath = path.join(this.dirname, '../dist/icons/icons.svg');
    this.iconsJsonPath = path.join(this.dirname, '../dist/icons.json');
  }

  validate() {
    if (!fs.existsSync(this.srcHtmlPath)) {
      throw new Error(`❌ Source HTML not found: ${this.srcHtmlPath}`);
    }
    if (!fs.existsSync(this.spritePath)) {
      throw new Error(`❌ Sprite not found: ${this.spritePath}. Run build-icons.js first.`);
    }
    if (!fs.existsSync(this.iconsJsonPath)) {
      throw new Error(`❌ icons.json not found: ${this.iconsJsonPath}. Run build-icons.js first.`);
    }
  }
}

// Replace <span> with <svg><use>
function replaceIconSpans(html, iconsData) {
  let updatedHtml = html;
  let replacements = 0;

  for (const iconKey of Object.keys(iconsData)) {
    console.log(`🔍 Processing icon: ${iconKey}`);

    let regex = null;
    let symbolId = null;

    // Match Iconify icon: i-prefix-name
    const iconifyMatch = iconKey.match(/^i-([a-z0-9]+)-([a-z0-9-]+)$/);
    if (iconifyMatch) {
      const [, prefix, name] = iconifyMatch;
      symbolId = `i-${prefix}-${name}`;
      regex = new RegExp(
        `<span\\s+class="([^"]*\\bi-${prefix}-${name}\\b[^"]*)"[^>]*>(.*?)</span>`,
        'g'
      );
    } else {
      // Match local icon: l-name
      const localMatch = iconKey.match(/^l-([a-z0-9-]+)$/);
      if (localMatch) {
        const [, name] = localMatch;
        symbolId = `l-${name}`;
        regex = new RegExp(
          `<span\\s+class="([^"]*\\bl-${name}\\b[^"]*)"[^>]*>(.*?)</span>`,
          'g'
        );
      } else {
        console.warn(`⚠️ Invalid icon format: ${iconKey}`);
        continue;
      }
    }

    updatedHtml = updatedHtml.replace(regex, (match, classNames) => {
      // Filter out the icon-specific class and ensure 'icon' is added only once
      const classList = classNames
        .split(/\s+/)
        .filter(cls => cls && cls !== symbolId);
      if (!classList.includes('icon')) {
        classList.push('icon');
      }
      const cleanedClasses = classList.length > 0 ? classList.join(' ') : 'icon';
      replacements++;
      return `<svg class="${cleanedClasses}" aria-hidden="true"><use href="#${symbolId}"></use></svg>`;
    });
  }

  console.log(`🔄 Replaced ${replacements} icon spans`);
  return updatedHtml;
}

async function injectIcons() {
  try {
    const config = new Config();
    config.validate();

    const html = fs.readFileSync(config.srcHtmlPath, 'utf8');
    const iconsData = JSON.parse(fs.readFileSync(config.iconsJsonPath, 'utf8'));

    const updatedHtml = replaceIconSpans(html, iconsData);

    fs.mkdirSync(path.dirname(config.distHtmlPath), { recursive: true });
    fs.writeFileSync(config.distHtmlPath, updatedHtml, 'utf8');

    console.log(`✅ Generated ${config.distHtmlPath}`);
  } catch (error) {
    console.error(`❌ Error: ${error.message}`);
    process.exit(1);
  }
}

injectIcons();
