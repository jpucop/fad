// build-icons.js

import {
  cleanupSVG,
  isEmptyColor,
  parseColors,
  runSVGO,
  SVG,
} from '@iconify/tools';
import { getIconData } from '@iconify/utils';
import { iconToSVG } from '@iconify/utils/lib/svg/build';
import fs from 'fs';
import { createRequire } from 'module';
import path from 'path';
import process from 'process';
import { fileURLToPath } from 'url';

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Mode class
class Mode {
  constructor(val, formalName) {
    this.val = val;
    this.formalName = formalName;
  }
  toString() {
    return this.formalName;
  }
  isSprite() {
    return this.val === 's';
  }
  genIconSprite(iconsJson, spriteContent, config) {
    try {
      fs.writeFileSync(path.join(config.outputDir, config.outputSpriteName), spriteContent, 'utf8');
      console.log(`✅ Wrote ${config.outputSpriteName} with ${Object.keys(iconsJson).length} symbols`);
      console.log(`📄 Sprite markup: <svg xmlns="${config.svgNs}" ...><symbol id="prefix-name" viewBox="...">...</symbol>...</svg>`);
      return true;
    } catch (err) {
      console.error(`❌ Failed to write ${config.outputSpriteName}: ${err.message}`);
      return false;
    }
  }
  genIndividualSvgIcons(iconsJson, config) {
    const fileNames = [];
    let success = true;
    for (const [iconName, { viewBox, body }] of Object.entries(iconsJson)) {
      const fileName = `${iconName}.svg`;
      try {
        const rawSVG = `<svg viewBox="${viewBox}" xmlns="${config.svgNs}">${body}</svg>`;
        const svg = new SVG(rawSVG);
        cleanupSVG(svg);
        parseColors(svg, {
          defaultColor: 'currentColor',
          callback: (attr, colorStr, color) => !color || isEmptyColor(color) ? colorStr : 'currentColor',
        });
        runSVGO(svg);
        fs.writeFileSync(path.join(config.outputDir, fileName), svg.toMinifiedString(), 'utf8');
        fileNames.push(fileName);
      } catch (err) {
        console.error(`❌ Failed to write ${fileName}: ${err.message}`);
        success = false;
      }
    }
    if (success) {
      console.log(`✅ Wrote ${fileNames.length} SVGs: ${fileNames.join(', ')}`);
      console.log(`📄 Individual SVG markup: <svg xmlns="${config.svgNs}" viewBox="...">...</svg>`);
    }
    return success;
  }
  static #S = new Mode('s', 'svg sprite');
  static #I = new Mode('i', 'individual svgs');
  static fromString(val) {
    const mode = val === 'i' ? Mode.#I : Mode.#S;
    if (val && val !== 's' && val !== 'i') console.warn(`⚠️ Invalid mode "${val}", defaulting to "s" (svg sprite)`);
    return mode;
  }
}

// Config class
class Config {
  constructor({
    iconPrefix = 'i-',
    outputSpriteName = 'icons.svg',
    iconHeight = '1em',
    defaultIconFile = path.join(__dirname, '../src/icons/default-icon.svg'),
    mode = Mode.fromString(process.argv[2]),
    htmlFile = path.join(__dirname, '../src/index.html'),
    outputDir = path.join(__dirname, '../dist/icons'),
    outputJson = path.join(__dirname, '../dist/icons.json'),
    svgNs = 'http://www.w3.org/2000/svg',
    spriteSvgOpen = `<svg xmlns="http://www.w3.org/2000/svg" style="display:none;" aria-hidden="true">\n`,
    spriteSvgClose = '</svg>\n',
  } = {}) {
    this.iconPrefix = iconPrefix;
    this.iconRegex = new RegExp(`\\b${iconPrefix}([a-z0-9]+)-([a-z0-9]+(?:-[a-z0-9]+)*)\\b`, 'g');
    this.outputSpriteName = outputSpriteName;
    this.iconHeight = iconHeight;
    this.defaultIconFile = defaultIconFile;
    this.mode = mode;
    this.htmlFile = htmlFile;
    this.outputDir = outputDir;
    this.outputJson = outputJson;
    this.svgNs = svgNs;
    this.spriteSvgOpen = spriteSvgOpen;
    this.spriteSvgClose = spriteSvgClose;
  }
}

const config = new Config();

// CLI toggle
console.log(`🔧 Mode: ${config.mode}`);

// Load HTML
const html = (() => {
  try {
    return fs.readFileSync(config.htmlFile, 'utf8');
  } catch (err) {
    console.error(`❌ Failed to read HTML file "${config.htmlFile}": ${err.message}`);
    process.exit(1);
  }
})();

// Extract icon usage
const iconMap = {};
for (const [, prefix, name] of html.matchAll(config.iconRegex)) {
  (iconMap[prefix] ||= new Set()).add(name);
}
const totalIcons = Object.values(iconMap).reduce((sum, set) => sum + set.size, 0);
console.log(`🔍 Found ${totalIcons} icons: ${Object.entries(iconMap).map(([p, s]) => `${p}(${s.size})`).join(', ')}`);

// Ensure output directory exists
try {
  fs.mkdirSync(config.outputDir, { recursive: true });
} catch (err) {
  console.error(`❌ Failed to create output directory "${config.outputDir}": ${err.message}`);
  process.exit(1);
}

// Load default icon
const defaultIcon = (() => {
  try {
    const svg = new SVG(fs.readFileSync(config.defaultIconFile, 'utf8'));
    const viewBox = svg.viewBox.toString();
    const body = svg.getBody();
    return { viewBox, body };
  } catch (err) {
    console.error(`❌ Failed to read default icon file "${config.defaultIconFile}": ${err.message}`);
    process.exit(1);
  }
})();

// Scan and retain unique icon refs
const iconsJson = {};
let spriteContent = config.spriteSvgOpen;

for (const [prefix, icons] of Object.entries(iconMap)) {
  const iconSetPath = resolveIconSetPath(prefix);
  if (!iconSetPath) {
    console.warn(`⚠️ Skipping prefix "${prefix}": no icon set found in @iconify-json/${prefix}`);
    continue;
  }

  const iconSet = (() => {
    try {
      return JSON.parse(fs.readFileSync(iconSetPath, 'utf8'));
    } catch (err) {
      console.error(`❌ Failed to read icon set for prefix "${prefix}": ${err.message}`);
      return null;
    }
  })();
  if (!iconSet) continue;

  for (const name of icons) {
    const iconName = `${config.iconPrefix}${prefix}-${name}`;
    console.log(`Processing icon: ${iconName}`); // Debug logging
    const isDefault = false;
    const svgObj = (() => {
      const data = getIconData(iconSet, name);
      if (!data) {
        console.warn(`⚠️ Missing icon "${iconName}" in @iconify-json/${prefix}, using default icon`);
        return { attributes: { viewBox: defaultIcon.viewBox }, body: defaultIcon.body, isDefault: true };
      }
      return iconToSVG(data, { height: config.iconHeight });
    })();

    iconsJson[iconName] = { viewBox: svgObj.attributes.viewBox, body: svgObj.body, isDefault: svgObj.isDefault || isDefault };
    if (config.mode.isSprite()) {
      spriteContent += `  <symbol id="${iconName}" viewBox="${svgObj.attributes.viewBox}">${svgObj.body}</symbol>\n`;
    }
  }
}

// Write output
if (config.mode.isSprite()) {
  spriteContent += config.spriteSvgClose;
  if (!config.mode.genIconSprite(iconsJson, spriteContent, config)) process.exit(1);
} else if (!config.mode.genIndividualSvgIcons(iconsJson, config)) {
  process.exit(1);
}

// Write metadata JSON
try {
  fs.writeFileSync(config.outputJson, JSON.stringify(iconsJson, null, 2), 'utf8');
  console.log(`✅ Wrote dist/: ${path.basename(config.outputJson)} with ${Object.keys(iconsJson).length} icons`);
} catch (err) {
  console.error(`❌ Failed to write ${path.basename(config.outputJson)}: ${err.message}`);
  process.exit(1);
}

// Resolve icon set path
function resolveIconSetPath(prefix) {
  try {
    return require.resolve(`@iconify-json/${prefix}/icons.json`);
  } catch (err) {
    console.warn(`⚠️ Cannot resolve icon set: @iconify-json/${prefix}`);
    return null;
  }
}
