import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Config class to encapsulate input parameters
class Config {
  constructor() {
    this.dirname = path.dirname(fileURLToPath(import.meta.url));
    this.srcHtmlPath = path.join(this.dirname, '../src/index.html');
    this.distHtmlPath = path.join(this.dirname, '../dist/index.html');
    this.spritePath = path.join(this.dirname, '../dist/icons/icons.svg'); // Updated to icons.svg
    this.iconsJsonPath = path.join(this.dirname, '../dist/icons.json');
    this.spriteUrl = 'icons/icons.svg'; // URL for XHR loader
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

  for (const [iconName] of Object.entries(iconsData)) {
    const [prefix, name] = iconName.split('-');
    const spanRegex = new RegExp(
      `<span\\s+class="([^"]*\\bi-${prefix}-${name}\\b[^"]*)"[^>]*>(.*?)</span>`,
      'g'
    );

    updatedHtml = updatedHtml.replace(spanRegex, (match, classNames) => {
      const cleanedClasses = classNames
        .split(/\s+/)
        .filter(cls => cls !== `i-${prefix}-${name}`)
        .join(' ');
      return `<svg class="icon ${cleanedClasses}" aria-hidden="true"><use href="#${prefix}-${name}"></use></svg>`;
    });
  }

  return updatedHtml;
}

// Generate sprite loader script
function generateSpriteLoader(spriteUrl) {
  return `
<script>
(function() {
  const xhr = new XMLHttpRequest();
  xhr.open('GET', '${spriteUrl}', true);
  xhr.onload = function() {
    if (xhr.status === 200) {
      const div = document.createElement('div');
      div.style.display = 'none';
      div.innerHTML = xhr.responseText;
      document.body.insertBefore(div, document.body.firstChild);
    }
  };
  xhr.send();
})();
</script>`;
}

// Main function
async function injectIcons() {
  try {
    const config = new Config();
    config.validate();

    // Load files
    const html = fs.readFileSync(config.srcHtmlPath, 'utf8');
    const iconsData = JSON.parse(fs.readFileSync(config.iconsJsonPath, 'utf8'));

    // Replace icon spans
    let updatedHtml = replaceIconSpans(html, iconsData);

    // Inject sprite loader
    const spriteScript = generateSpriteLoader(config.spriteUrl);
    if (!updatedHtml.includes('</head>')) {
      throw new Error('❌ No </head> tag found in HTML — cannot inject sprite loader.');
    }
    updatedHtml = updatedHtml.replace('</head>', `${spriteScript}\n</head>`);

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