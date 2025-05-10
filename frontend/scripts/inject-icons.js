import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlPath = path.join(__dirname, '../src/index.html');
const distHtmlPath = path.join(__dirname, '../dist/index.html');
const spritePath = path.join(__dirname, '../dist/icons/sprite.svg');
const iconsJsonPath = path.join(__dirname, '../dist/icons.json');

// === Fail fast if prerequisites missing ===
if (!fs.existsSync(spritePath)) {
  console.error('❌ Missing sprite.svg. Run build-icons first.');
  process.exit(1);
}

if (!fs.existsSync(iconsJsonPath)) {
  console.error('❌ Missing icons.json. Run build-icons first.');
  process.exit(1);
}

// === Load files ===
const html = fs.readFileSync(htmlPath, 'utf8');
const iconsData = JSON.parse(fs.readFileSync(iconsJsonPath, 'utf8'));

// === Replace icon <span> with <svg><use href="#..."> ===
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

// === Inject XHR loader script before </head> ===
const spriteScript = `
<script>
(function() {
  const xhr = new XMLHttpRequest();
  xhr.open('GET', 'icons/sprite.svg', true);
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

if (!updatedHtml.includes('</head>')) {
  console.error('❌ No </head> tag found in HTML — cannot inject sprite loader.');
  process.exit(1);
}

updatedHtml = updatedHtml.replace('</head>', `${spriteScript}\n</head>`);

// === Write output ===
fs.mkdirSync(path.dirname(distHtmlPath), { recursive: true });
fs.writeFileSync(distHtmlPath, updatedHtml, 'utf8');

console.log(`✅ Replaced icon spans and injected sprite loader into dist/index.html`);
