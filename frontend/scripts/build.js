import tailwindcss from '@tailwindcss/postcss';
import autoprefixer from 'autoprefixer';
import cssnano from 'cssnano';
import esbuild from 'esbuild';
import fs from 'fs';
import path from 'path';
import postcss from 'postcss';
import { CONFIG } from './config.js';
import { validateSprite } from './sprite.js';

// Resolve paths
const srcPath = path.join(CONFIG.paths.dirname, CONFIG.paths.srcDir);
const distPath = path.join(CONFIG.paths.dirname, CONFIG.paths.distDir);
const backendPath = path.join(CONFIG.paths.dirname, CONFIG.paths.backendDir);

function cleanDist() {
  if (fs.existsSync(distPath)) {
    fs.rmSync(distPath, { recursive: true, force: true });
    console.log(`✅ Cleaned ${distPath}`);
  }
  fs.mkdirSync(distPath, { recursive: true });
}

function validate() {
  const allFiles = [
    ...CONFIG.src.js,
    ...CONFIG.src.css,
    ...CONFIG.src.html,
    CONFIG.src.sprite,
    ...CONFIG.src.img.map(item => item.dir),
    ...CONFIG.src.static,
  ];
  const missing = [];

  for (const file of allFiles) {
    const fullPath = path.join(srcPath, file);
    if (!fs.existsSync(fullPath)) {
      if (file === 'img') {
        fs.mkdirSync(fullPath, { recursive: true });
        console.log(`✅ Created missing directory: ${fullPath}`);
      } else if (file !== CONFIG.src.sprite) {
        missing.push(file);
      }
    }
  }

  if (missing.length) throw new Error(`❌ Missing files: ${missing.join(', ')}`);
  validateSprite();
}

function copyPath(src, dest, filterFn = null) {
  if (!fs.existsSync(src)) return;
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    fs.mkdirSync(dest, { recursive: true });
    const files = fs.readdirSync(src).filter(f => !filterFn || filterFn(f));
    for (const f of files) {
      fs.copyFileSync(path.join(src, f), path.join(dest, f));
      console.log(`✅ Copied ${f} to ${dest}`);
    }
  } else {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(src, dest);
    console.log(`✅ Copied ${path.basename(src)} to ${dest}`);
  }
}

function copyStatic() {
  const items = [CONFIG.src.sprite, ...CONFIG.src.img, ...CONFIG.src.static];
  for (const item of items) {
    const file = typeof item === 'string' ? item : item.dir;
    const src = path.join(srcPath, file);
    const dest = path.join(distPath, file);
    const filter = typeof item === 'object' && item.exclude ? f => !item.exclude.test(f) : null;
    copyPath(src, dest, filter);
  }
}

async function buildCss() {
  const tailwindConfig = {
    content: [
      ...CONFIG.src.html.map(file => path.join(srcPath, file)),
      ...CONFIG.src.js.map(file => path.join(srcPath, file)),
    ],
    darkMode: 'class',
    theme: { extend: {} },
    plugins: [],
  };

  const plugins = [
    tailwindcss(tailwindConfig),
    autoprefixer,
    ...(CONFIG.build.isProduction ? [cssnano({ preset: 'default' })] : []),
  ];

  const processor = postcss(plugins);

  for (const file of CONFIG.src.css) {
    const srcFile = path.join(srcPath, file);
    const destFile = path.join(distPath, file);
    const inputCss = fs.readFileSync(srcFile, 'utf8');

    try {
      const result = await processor.process(inputCss, { from: srcFile, to: destFile });
      fs.mkdirSync(path.dirname(destFile), { recursive: true });
      fs.writeFileSync(destFile, result.css);
      console.log(`✅ Compiled CSS ${file}`);
    } catch (err) {
      throw new Error(`❌ CSS build failed for ${file}: ${err.message}`);
    }
  }
}
function buildJs() {
  const alpineSrc = path.join(srcPath, CONFIG.build.alpineFilename);
  const alpineModule = CONFIG.paths.alpineModulePath;
  const alpineDest = path.join(distPath, CONFIG.build.alpineFilename);

  // Copy Alpine.js
  if (!fs.existsSync(alpineSrc) && fs.existsSync(alpineModule)) {
    fs.copyFileSync(alpineModule, alpineSrc);
    console.log(`✅ Created ${CONFIG.build.alpineFilename} in src from node_modules`);
  }

  if (fs.existsSync(alpineSrc)) {
    fs.copyFileSync(alpineSrc, alpineDest);
    console.log(`✅ Copied ${CONFIG.build.alpineFilename} to dist`);
  }

  // Copy app.js
  const appSrc = path.join(srcPath, 'app.js');
  const appDest = path.join(distPath, 'app.js');
  if (fs.existsSync(appSrc)) {
    fs.copyFileSync(appSrc, appDest);
    console.log(`✅ Copied app.js to dist`);
  } else {
    console.log('⚠️ app.js not found in src');
  }
}

function replaceIconSpans(html) {
  let updatedHtml = html;
  let replacements = 0;

  const matches = html.match(CONFIG.iconConfig.spanRegex) || [];
  console.log(`✅ Found ${matches.length} icon spans`);

  for (const span of matches) {
    const classAttr = span.match(/class="([^"]*)"/);
    if (!classAttr) continue;

    const classes = classAttr[1].split(/\s+/);
    if (!classes.includes('icon')) continue;

    const iconClass = classes.find(cls => CONFIG.iconConfig.validateRegex.test(cls));
    if (!iconClass) continue;

    const attrsMatch = span.match(/<span\s+([^>]*)>/);
    if (!attrsMatch) continue;

    const attrs = attrsMatch[1]
      .split(/\s+/)
      .filter(attr => !attr.startsWith('class='))
      .join(' ');

    const newClasses = ['icon', ...classes.filter(c => c !== 'icon' && c !== iconClass)].join(' ');
    const replacement = `<svg class="${newClasses}" ${attrs} aria-hidden="true"><use href="/sprite.svg#${iconClass}"></use></svg>`;

    updatedHtml = updatedHtml.replace(span, replacement);
    replacements++;
  }

  console.log(`✅ Replaced ${replacements} icon spans`);
  return updatedHtml;
}

function processHtml() {
  for (const file of CONFIG.src.html) {
    const src = path.join(srcPath, file);
    const dest = path.join(distPath, file);
    const html = fs.readFileSync(src, 'utf8');
    const updatedHtml = replaceIconSpans(html);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, updatedHtml, 'utf8');
    console.log(`✅ Processed HTML ${file}`);
  }
}

function copyToBackend() {
  fs.mkdirSync(backendPath, { recursive: true });
  const items = fs.readdirSync(distPath);
  for (const item of items) {
    const src = path.join(distPath, item);
    const dest = path.join(backendPath, item);
    const stat = fs.statSync(src);
    if (stat.isDirectory()) {
      copyPath(src, dest);
    } else {
      fs.copyFileSync(src, dest);
      console.log(`✅ Copied ${item} to backend`);
    }
  }
}

async function build() {
  try {
    cleanDist();
    validate();
    copyStatic();
    await buildCss();
    buildJs();
    processHtml();
    copyToBackend();
    console.log('✅ Build completed');
  } catch (err) {
    console.error(`❌ Build failed: ${err.message}`);
    process.exit(1);
  }
}

build();
