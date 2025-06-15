import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { SVG, cleanupSVG, parseColors } from '@iconify/tools';
import { optimize } from 'svgo';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const imgPath = path.join(__dirname, '../src/img');

console.log(`🛠️ Cleaning SVGs in: ${imgPath}`);

// SVGO config (conservative to preserve precision)
const svgoConfig = {
  plugins: [
    'preset-default',
    { name: 'removeViewBox', active: false },
    { name: 'cleanupNumericValues', params: { floatPrecision: 3 } },
  ],
};

// Validate directory
function validateDir() {
  if (!fs.existsSync(imgPath)) {
    console.warn(`⚠️ Directory not found: ${imgPath}, creating it`);
    fs.mkdirSync(imgPath, { recursive: true });
    return false;
  }
  return true;
}

// Clean and optimize SVG
async function cleanSvg(filePath) {
  try {
    console.log(`🔄 Processing: ${path.basename(filePath)}`);
    let svgContent = fs.readFileSync(filePath, 'utf8')
      .replace(/<\?xml[^?]*\?>\s*/, '')
      .replace(/<!DOCTYPE[^>]*>\s*/, '');

    // Iconify cleanup
    const svg = new SVG(svgContent);
    cleanupSVG(svg);
    parseColors(svg, {
      defaultColor: 'currentColor',
      callback: (attr, colorStr, color) => color && color !== 'none' ? 'currentColor' : colorStr,
    });

    // SVGO optimization
    const svgoResult = optimize(svg.toMinifiedString(), svgoConfig);
    if (!svgoResult.data.includes('<svg')) {
      throw new Error('Invalid SVG after SVGO');
    }

    fs.writeFileSync(filePath, svgoResult.data, 'utf8');
    console.log(`✅ Cleaned and optimized: ${path.basename(filePath)}`);
  } catch (err) {
    console.error(`❌ Error cleaning ${path.basename(filePath)}: ${err.message}`);
  }
}

// Main
async function cleanSvgs() {
  try {
    if (!validateDir()) {
      console.log('ℹ️ No img directory, nothing to clean');
      return;
    }
    const files = fs.readdirSync(imgPath).filter(f => f.endsWith('.svg'));
    if (files.length === 0) {
      console.log('ℹ️ No SVGs found in src/img/');
      return;
    }
    console.log(`📋 Found ${files.length} SVGs: ${files.join(', ')}`);
    for (const file of files) {
      await cleanSvg(path.join(imgPath, file));
    }
    console.log('✅ All SVGs cleaned');
  } catch (err) {
    console.error(`❌ Cleaning failed: ${err.message}`);
    process.exit(1);
  }
}
