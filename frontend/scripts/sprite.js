import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { SVG, cleanupSVG, parseColors } from '@iconify/tools';
import { getIconData } from '@iconify/utils';
import { execSync } from 'child_process';

class Config {
  constructor() {
    this.dirname = path.dirname(fileURLToPath(import.meta.url));
    this.srcPath = path.join(this.dirname, '../src');
    this.distPath = path.join(this.dirname, '../dist');
    this.imgPath = path.join(this.srcPath, 'img');
    this.indexHtmlPath = path.join(this.srcPath, 'index.html');
    this.spritePath = path.join(this.srcPath, 'sprite.svg');
    this.distSpritePath = path.join(this.distPath, 'sprite.svg');
  }

  validate() {
    if (!fs.existsSync(this.imgPath)) fs.mkdirSync(this.imgPath, { recursive: true });
    if (!fs.existsSync(this.distPath)) fs.mkdirSync(this.distPath, { recursive: true });
    if (!fs.existsSync(this.indexHtmlPath)) throw new Error('index.html not found: ' + this.indexHtmlPath);
  }
}

function needsRebuild(config) {
  try {
    const diff = execSync('git diff --name-only HEAD', { encoding: 'utf8' });
    if (diff.includes('src/img/') || diff.includes('src/index.html')) {
      console.log('📌 Changes detected in img/ or index.html');
      return true;
    }
    if (!fs.existsSync(config.spritePath)) {
      console.log('📌 No sprite found');
      return true;
    }
    const spriteMtime = fs.statSync(config.spritePath).mtimeMs;
    if (fs.statSync(config.indexHtmlPath).mtimeMs > spriteMtime) {
      console.log('📌 index.html is newer');
      return true;
    }
    const files = fs.readdirSync(config.imgPath).filter(f => f.endsWith('.svg'));
    for (const file of files) {
      if (fs.statSync(path.join(config.imgPath, file)).mtimeMs > spriteMtime) {
        console.log('📌 ' + file + ' is newer');
        return true;
      }
    }
    console.log('ℹ️ No changes, copying sprite');
    return false;
  } catch (err) {
    console.warn('⚠️ Git diff failed, rebuilding: ' + err.message);
    return true;
  }
}

function getIconifyIcons(config) {
  const html = fs.readFileSync(config.indexHtmlPath, 'utf8');
  const regex = /i-([a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*)/g;
  const icons = new Set();
  let match;
  while ((match = regex.exec(html))) {
    icons.add(match[1]);
  }
  return [...icons];
}

async function processLocalSvg(file, config) {
  try {
    const svgContent = fs.readFileSync(path.join(config.imgPath, file), 'utf8');
    const svg = new SVG(svgContent);
    cleanupSVG(svg);
    parseColors(svg, { defaultColor: 'currentColor' });
    const name = 'l-' + path.basename(file, '.svg');
    return { id: name, content: svg.toMinifiedString() };
  } catch (err) {
    console.error('❌ Error processing ' + file + ': ' + err.message);
    return null;
  }
}

async function processIconifyIcon(name, collection) {
  try {
    const iconName = name.replace(/^mdi-/, '');
    console.log('🔍 Processing Iconify icon: ' + name + ' (key: ' + iconName + ')');
    const iconData = getIconData(collection, iconName);
    if (!iconData) {
      throw new Error('Icon ' + iconName + ' not found in mdi collection');
    }
    const svgContent = `<svg viewBox="0 0 ${iconData.width || 24} ${iconData.height || 24}">${iconData.body}</svg>`;
    const svg = new SVG(svgContent);
    cleanupSVG(svg);
    parseColors(svg, { defaultColor: 'currentColor' });
    return { id: 'i-' + name, content: svg.toMinifiedString() };
  } catch (err) {
    console.error('❌ Error processing ' + name + ': ' + err.message);
    return null;
  }
}

async function generateSprite(config) {
  const iconifyJsonPath = path.join(config.dirname, '../node_modules/@iconify-json/mdi/icons.json');
  if (!fs.existsSync(iconifyJsonPath)) {
    throw new Error('Iconify JSON file not found: ' + iconifyJsonPath);
  }
  const mdiIcons = JSON.parse(fs.readFileSync(iconifyJsonPath, 'utf8'));
  console.log('📄 Loaded mdiIcons with ' + Object.keys(mdiIcons.icons).length + ' icons');

  const localIcons = fs.readdirSync(config.imgPath).filter(f => f.endsWith('.svg'));
  const iconifyIcons = getIconifyIcons(config);
  console.log('📋 ' + localIcons.length + ' local SVGs: ' + localIcons.join(', '));
  console.log('📋 ' + iconifyIcons.length + ' Iconify icons: ' + iconifyIcons.join(', '));

  const symbols = [];
  const usedIds = new Set();

  for (const file of localIcons) {
    const result = await processLocalSvg(file, config);
    if (result && !usedIds.has(result.id)) {
      symbols.push('<symbol id="' + result.id + '" ' + result.content.replace(/^<svg/, '').replace(/<\/svg>$/, '') + '</symbol>');
      usedIds.add(result.id);
    }
  }

  for (const name of iconifyIcons) {
    const result = await processIconifyIcon(name, mdiIcons);
    if (result && !usedIds.has(result.id)) {
      symbols.push('<symbol id="' + result.id + '" ' + result.content.replace(/^<svg/, '').replace(/<\/svg>$/, '') + '</symbol>');
      usedIds.add(result.id);
    }
  }

  const spriteContent = symbols.length ? '<svg style="display:none">' + symbols.join('') + '</svg>' : '<svg></svg>';
  fs.writeFileSync(config.spritePath, spriteContent, 'utf8');
  fs.writeFileSync(config.distSpritePath, spriteContent, 'utf8');
  console.log('✅ Sprite generated: ' + config.spritePath + ', ' + config.distSpritePath);
}

function copySprite(config) {
  if (fs.existsSync(config.spritePath)) {
    fs.copyFileSync(config.spritePath, config.distSpritePath);
    console.log('✅ Copied sprite to ' + config.distSpritePath);
  } else {
    console.warn('⚠️ No sprite at ' + config.spritePath + ', run "npm run sprite"');
  }
}

async function buildSprite() {
  try {
    const config = new Config();
    config.validate();
    if (needsRebuild(config)) {
      await generateSprite(config);
    } else {
      copySprite(config);
    }
    console.log('✅ Sprite build completed');
  } catch (err) {
    console.error('❌ Sprite build failed: ' + err.message);
    process.exit(1);
  }
}

buildSprite();