import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { SVG, cleanupSVG, parseColors } from '@iconify/tools';
import { getIconData } from '@iconify/utils';
import { execSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const imgPath = path.join(__dirname, '../src/img');
const indexHtmlPath = path.join(__dirname, '../src/index.html');
const spritePath = path.join(__dirname, '../src/icons.svg');
const distSpritePath = path.join(__dirname, '../dist/icons/icons.svg');

console.log(`🛠️ Building sprite: ${spritePath}`);

// Validate paths
function validatePaths() {
  if (!fs.existsSync(imgPath)) {
    fs.mkdirSync(imgPath, { recursive: true });
  }
  if (!fs.existsSync(path.dirname(distSpritePath))) {
    fs.mkdirSync(path.dirname(distSpritePath), { recursive: true });
  }
  if (!fs.existsSync(indexHtmlPath)) {
    throw new Error(`index.html not found at ${indexHtmlPath}`);
  }
}

// Check if rebuild is needed
function needsRebuild() {
  try {
    const diff = execSync('git diff --name-only HEAD', { encoding: 'utf8' });
    if (diff.includes('src/img/') || diff.includes('src/index.html')) {
      console.log('📌 Changes detected in img/ or index.html');
      return true;
    }
    if (!fs.existsSync(spritePath)) {
      console.log('📌 No sprite found');
      return true;
    }
    const spriteMtime = fs.statSync(spritePath).mtimeMs;
    if (fs.statSync(indexHtmlPath).mtimeMs > spriteMtime) {
      console.log('📌 index.html is newer');
      return true;
    }
    const files = fs.readdirSync(imgPath).filter(f => f.endsWith('.svg'));
    for (const file of files) {
      if (fs.statSync(path.join(imgPath, file)).mtimeMs > spriteMtime) {
        console.log(`📌 ${file} is newer`);
        return true;
      }
    }
    console.log('ℹ️ No changes, copying sprite');
    return false;
  } catch (err) {
    console.warn(`⚠️ Git diff failed, rebuilding: ${err.message}`);
    return true;
  }
}

// Get Iconify icons from index.html
function getIconifyIcons() {
  const html = fs.readFileSync(indexHtmlPath, 'utf8');
  const regex = /i-([a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*)/g;
  const icons = new Set();
  let match;
  while ((match = regex.exec(html))) {
    icons.add(match[1]);
  }
  return [...icons];
}

// Process local SVG
async function processLocalSvg(file) {
  try {
    const svgContent = fs.readFileSync(path.join(imgPath, file), 'utf8');
    const svg = new SVG(svgContent);
    cleanupSVG(svg);
    parseColors(svg, { defaultColor: 'currentColor' });
    const name = `l-${path.basename(file, '.svg')}`;
    return { id: name, content: svg.toMinifiedString() };
  } catch (err) {
    console.error(`❌ Error processing ${file}: ${err.message}`);
    return null;
  }
}

// Process Iconify icon
async function processIconifyIcon(name) {
  try {
    const [prefix, icon] = name.split('-', 2);
    const iconData = getIconData(prefix, icon);
    if (!iconData) {
      throw new Error(`Icon ${name} not found`);
    }
    const svg = new SVG(iconData);
    cleanupSVG(svg);
    parseColors(svg, { defaultColor: 'currentColor' });
    return { id: `i-${name}`, content: svg.toMinifiedString() };
  } catch (err) {
    console.error(`❌ Error processing ${name}: ${err.message}`);
    return null;
  }
}

// Generate sprite
async function generateSprite() {
  const localIcons = fs.readdirSync(imgPath).filter(f => f.endsWith('.svg'));
  const iconifyIcons = getIconifyIcons();
  console.log(`📋 ${localIcons.length} local SVGs: ${localIcons.join(', ')}`);
  console.log(`📋 ${iconifyIcons.length} Iconify icons: ${iconifyIcons.join(', ')}`);

  const symbols = [];
  const usedIds = new Set();

  for (const file of localIcons) {
    const result = await processLocalSvg(file);
    if (result && !usedIds.has(result.id)) {
      symbols.push(`<symbol id="${result.id}" ${result.content.replace(/^<svg/, '').replace(/<\/svg>$/, '')}</symbol>`);
      usedIds.add(result.id);
    }
  }

  for (const name of iconifyIcons) {
    const result = await processIconifyIcon(name);
    if (result && !usedIds.has(result.id)) {
      symbols.push(`<symbol id="${result.id}" ${result.content.replace(/^<svg/, '').replace(/<\/svg>$/, '')}</symbol>`);
      usedIds.add(result.id);
    }
  }

  const spriteContent = symbols.length ? `<svg style="display:none">${symbols.join('')}</svg>` : '<svg></svg>';
  fs.writeFileSync(spritePath, spriteContent, 'utf8');
  fs.writeFileSync(distSpritePath, spriteContent, 'utf8');
  console.log(`✅ Sprite generated: ${spritePath} and ${distSpritePath}`);
}

// Copy existing sprite
function copySprite() {
  if (fs.existsSync(spritePath)) {
    fs.copyFileSync(spritePath, distSpritePath);
    console.log(`✅ Copied sprite to ${distSpritePath}`);
  } else {
    console.warn(`⚠️ No sprite at ${spritePath}, run 'npm run sprite'`);
  }
}

// Main
async function buildSprite() {
  try {
    validatePaths();
    if (needsRebuild()) {
      await generateSprite();
    } else {
      copySprite();
    }
    console.log('✅ Sprite build completed');
  } catch (err) {
    console.error(`❌ Sprite build failed: ${err.message}`);
    process.exit(1);
  }
}

buildSprite();