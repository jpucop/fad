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

// mode class
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
      console.log(`✅ wrote ${config.outputSpriteName} with ${Object.keys(iconsJson).length} symbols`);
      console.log(`📄 sprite markup: <svg xmlns="${config.svgNs}" ...><symbol id="prefix-name" viewBox="...">...</symbol>...</svg>`);
      return true;
    } catch (err) {
      console.warn(`⚠️ failed to write ${config.outputSpriteName}: ${err.message}`);
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
        console.warn(`⚠️ failed to write ${fileName}: ${err.message}`);
        success = false;
      }
    }
    if (success) {
      console.log(`✅ wrote ${fileNames.length} svgs: ${fileNames.join(', ')}`);
      console.log(`📄 individual svg markup: <svg xmlns="${config.svgNs}" viewBox="...">...</svg>`);
    }
    return success;
  }
  static #S = new Mode('s', 'svg sprite');
  static #I = new Mode('i', 'individual svgs');
  static fromString(val) {
    const mode = val === 'i' ? Mode.#I : Mode.#S;
    if (val && val !== 's' && val !== 'i') console.warn(`⚠️ invalid mode "${val}", defaulting to "s" (svg sprite)`);
    return mode;
  }
}

// config class
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

// cli toggle
console.log(`🔧 mode: ${config.mode}`);

// load html
const html = (() => {
  try {
    return fs.readFileSync(config.htmlFile, 'utf8');
  } catch (err) {
    console.warn(`⚠️ failed to read html file "${config.htmlFile}": ${err.message}`);
    process.exit(1);
  }
})();

// extract icon usage
const iconMap = {};
for (const [, prefix, name] of html.matchAll(config.iconRegex)) {
  (iconMap[prefix] ||= new Set()).add(name);
}
console.log(`🔍 found ${Object.values(iconMap).reduce((sum, set) => sum + set.size, 0)} icons: ${Object.entries(iconMap).map(([p, s]) => `${p}(${s.size})`).join(', ')}`);

// ensure output dir exists
try {
  fs.mkdirSync(config.outputDir, { recursive: true });
} catch (err) {
  console.warn(`⚠️ failed to create output directory "${config.outputDir}": ${err.message}`);
  process.exit(1);
}

// load default icon
const defaultIcon = (() => {
  try {
    const svg = new SVG(fs.readFileSync(config.defaultIconFile, 'utf8'));
    const viewBox = svg.viewBox.toString();
    const body = svg.getBody();
    return { viewBox, body };
  } catch (err) {
    console.warn(`⚠️ failed to read default icon file "${config.defaultIconFile}": ${err.message}`);
    process.exit(1);
  }
})();

// scan and retain unique icon refs in given input sources
const iconsJson = {};
let spriteContent = config.spriteSvgOpen;

for (const [prefix, icons] of Object.entries(iconMap)) {
  const iconSetPath = resolveIconSetPath(prefix);
  if (!iconSetPath) {
    console.warn(`⚠️ skipping prefix "${prefix}": no icon set found`);
    continue;
  }

  const iconSet = (() => {
    try {
      return JSON.parse(fs.readFileSync(iconSetPath, 'utf8'));
    } catch (err) {
      console.warn(`⚠️ failed to read icon set for prefix "${prefix}": ${err.message}`);
      return null;
    }
  })();
  if (!iconSet) continue;

  for (const name of icons) {
    const iconName = `${config.iconPrefix}${prefix}-${name}`;
    const isDefault = false;
    const svgObj = (() => {
      const data = getIconData(iconSet, name);
      if (!data) {
        console.warn(`⚠️ missing icon: ${iconName}, using default icon`);
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

// write output
if (config.mode.isSprite()) {
  spriteContent += config.spriteSvgClose;
  if (!config.mode.genIconSprite(iconsJson, spriteContent, config)) process.exit(1);
} else if (!config.mode.genIndividualSvgIcons(iconsJson, config)) {
  process.exit(1);
}

// write metadata json
try {
  fs.writeFileSync(config.outputJson, JSON.stringify(iconsJson, null, 2), 'utf8');
  console.log(`✅ wrote dist/: ${path.basename(config.outputJson)}`);
} catch (err) {
  console.warn(`⚠️ failed to write ${path.basename(config.outputJson)}: ${err.message}`);
  process.exit(1);
}

// resolve icon set path
function resolveIconSetPath(prefix) {
  try {
    return require.resolve(`@iconify-json/${prefix}/icons.json`);
  } catch (err) {
    console.warn(`⚠️ cannot resolve icon set: ${prefix}`);
    return null;
  }
}