import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';
import esbuild from 'esbuild';

const BUILD_ENV = process.env.env === 'prod' ? 'prod' : 'dev';
console.log(`BUILD_ENV: ${BUILD_ENV}`);
const isProduction = BUILD_ENV === 'prod';

// Icon-related regexes for clarity
const iconConfig = {
  // Matches icon classes like i-home or l-settings in class attributes
  classRegex: /(?:l-|i-)([a-z0-9-]+)(?=\b|$)/,
  // Validates full icon class (e.g., i-home)
  validateRegex: /^(l-|i-)[a-z0-9-]+$/,
  // Matches <span> tags with icon class
  spanRegex: /<span\s+[^>]*class="[^"]*icon[^"]*"[^>]*>/g,
};

const CONFIG = {
  build: {
    env: BUILD_ENV,
    minify: isProduction,
    sourcemap: !isProduction, // No sourcemaps in production
  },
  paths: {
    dirname: path.dirname(fileURLToPath(import.meta.url)),
    srcDir: '../src',
    distDir: '../dist',
    backendDir: process.env.BACKEND_DIR || '../../backend/app/static', // Configurable backend path
  },
  src: {
    js: ['app.js', 'alpine.js'],
    css: ['styles.css'],
    html: ['index.html'],
    svg: ['sprite.svg'],
    img: [{ dir: 'img', exclude: /\.svg$/ }],
  },
};

// Derived paths
const srcPath = path.join(CONFIG.paths.dirname, CONFIG.paths.srcDir);
const distPath = path.join(CONFIG.paths.dirname, CONFIG.paths.distDir);
const backendPath = path.join(CONFIG.paths.dirname, CONFIG.paths.backendDir);

// Ensure Alpine.js exists in src/
const alpineSrc = path.join(srcPath, 'alpine.js');
const alpineNodeModules = path.join(CONFIG.paths.dirname, '../node_modules/alpinejs/dist/cdn.js');
if (!fs.existsSync(alpineSrc) && fs.existsSync(alpineNodeModules)) {
  fs.copyFileSync(alpineNodeModules, alpineSrc);
  console.log(`✅ Copied non-minified Alpine.js to ${alpineSrc}`);
}

function validateSprite() {
  const spritePath = path.join(srcPath, 'sprite.svg');
  if (!fs.existsSync(spritePath)) {
    throw new Error('sprite.svg not found');
  }
  const spriteContent = fs.readFileSync(spritePath, 'utf8');
  
  const spans = fs.readFileSync(path.join(srcPath, 'index.html'), 'utf8')
    .match(iconConfig.spanRegex) || [];
  
  const iconClasses = new Set();
  for (const span of spans) {
    const classMatch = span.match(/class="([^"]*)"/);
    if (classMatch) {
      const classes = classMatch[1].split(/\s+/);
      const iconClass = classes.find(cls => iconConfig.validateRegex.test(cls));
      if (iconClass && classes.includes('icon')) iconClasses.add(iconClass);
    }
  }
  for (const iconClass of iconClasses) {
    if (!spriteContent.includes(`id="${iconClass}"`)) {
      console.warn(`⚠️ Symbol ${iconClass} not found in sprite.svg`);
    }
  }
}

function validate() {
  const allFiles = [
    ...CONFIG.src.js,
    ...CONFIG.src.css,
    ...CONFIG.src.html,
    ...CONFIG.src.svg,
    ...CONFIG.src.img.map(item => item.dir),
  ];
  const missing = [];
  for (const file of allFiles) {
    const src = path.join(srcPath, file);
    if (!fs.existsSync(src)) {
      if (file === 'img') fs.mkdirSync(src, { recursive: true });
      else missing.push(file);
    }
  }
  if (missing.length) {
    throw new Error(`Missing files: ${missing.join(', ')}`);
  }
  validateSprite();
}

function cleanDist() {
  if (fs.existsSync(distPath)) {
    fs.rmSync(distPath, { recursive: true, force: true });
    console.log(`🧹 Cleaned ${distPath}`);
  }
  fs.mkdirSync(distPath, { recursive: true });
}

function copyStatic() {
  const staticItems = [...CONFIG.src.svg, ...CONFIG.src.img];
  for (const item of staticItems) {
    const file = typeof item === 'string' ? item : item.dir;
    const src = path.join(srcPath, file);
    const dest = path.join(distPath, file);
    if (!fs.existsSync(src)) continue;

    const stat = fs.statSync(src);
    if (stat.isDirectory()) {
      fs.mkdirSync(dest, { recursive: true });
      const files = fs.readdirSync(src).filter(f => {
        if (item.include) return item.include.test(f);
        return !item.exclude?.test(f);
      });
      for (const f of files) {
        fs.copyFileSync(path.join(src, f), path.join(dest, f));
        console.log(`✅ Copied ${f} to ${dest}`);
      }
    } else {
      fs.copyFileSync(src, dest);
      console.log(`✅ Copied ${file} to ${dest}`);
    }
  }
}

function copyToBackend() {
  fs.mkdirSync(backendPath, { recursive: true });
  const files = fs.readdirSync(distPath);
  for (const file of files) {
    const src = path.join(distPath, file);
    const dest = path.join(backendPath, file);
    if (fs.statSync(src).isDirectory()) {
      fs.mkdirSync(dest, { recursive: true });
      const subFiles = fs.readdirSync(src);
      for (const f of subFiles) {
        fs.copyFileSync(path.join(src, f), path.join(dest, f));
        console.log(`✅ Copied ${f} to ${dest}`);
      }
    } else {
      fs.copyFileSync(src, dest);
      console.log(`✅ Copied ${file} to ${dest}`);
    }
  }
}

function buildCss() {
  for (const file of CONFIG.src.css) {
    const src = path.join(srcPath, file);
    const dest = path.join(distPath, file);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    try {
      execSync(
        `npx @tailwindcss/cli -i ${src} -o ${dest} ${CONFIG.build.minify ? '--minify' : ''}`,
        { stdio: 'inherit' }
      );
      console.log(`✅ Compiled CSS ${file} to ${dest}`);
    } catch (err) {
      throw new Error(`CSS build failed for ${file}: ${err.message}`);
    }
  }
}

async function buildJs() {
  for (const file of CONFIG.src.js) {
    const src = path.join(srcPath, file);
    const dest = path.join(distPath, file);
    if (!fs.existsSync(src)) continue; // Skip missing JS files (e.g., if alpine.js isn't needed)
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    await esbuild.build({
      entryPoints: [src],
      bundle: true,
      outfile: dest,
      minify: CONFIG.build.minify,
      sourcemap: CONFIG.build.sourcemap,
      format: 'iife',
      globalName: file === 'app.js' ? 'app' : undefined, // Only app.js gets global name
      loader: { '.js': 'jsx' },
      external: file === 'app.js' ? ['alpinejs'] : [], // Exclude alpinejs only for app.js
    });
    console.log(`✅ Compiled JS ${file} to ${dest}`);
  }
}

function replaceIconSpans(html) {
  let updatedHtml = html;
  let replacements = 0;

  const spans = html.match(iconConfig.spanRegex) || [];
  console.log(`🔍 Found ${spans.length} potential icon spans`);

  for (const span of spans) {
    const classMatch = span.match(/class="([^"]*)"/);
    if (!classMatch) continue;
    const classes = classMatch[1].split(/\s+/);
    if (!classes.includes('icon')) continue;
    const iconClass = classes.find(cls => iconConfig.validateRegex.test(cls));
    if (!iconClass) continue;

    const symbolId = iconClass; // e.g., i-home

    const attrMatch = span.match(/<span\s+([^>]*)>/)[1];
    const attrs = attrMatch
      .split(/\s+/)
      .filter(attr => !attr.startsWith('class='))
      .join(' ');

    const otherClasses = classes.filter(cls => cls !== iconClass && cls !== 'icon');
    const newClasses = ['icon', ...otherClasses].join(' ');

    const replacement = `<svg class="${newClasses}" ${attrs} aria-hidden="true"><use href="/sprite.svg#${symbolId}"></use></svg>`;

    const escapedSpan = span.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(escapedSpan, 'g');
    updatedHtml = updatedHtml.replace(regex, replacement);
    console.log(`🔄 Replaced span for ${symbolId}: ${span}`);
    replacements++;
  }

  console.log(`🔄 Total replaced ${replacements} icon spans`);
  return updatedHtml;
}

function processHtml() {
  for (const file of CONFIG.src.html) {
    const src = path.join(srcPath, file);
    const dest = path.join(distPath, file);
    let html = fs.readFileSync(src, 'utf8');
    html = replaceIconSpans(html);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, html, 'utf8');
    console.log(`✅ Processed HTML ${file} to ${dest}`);
  }
}

async function build() {
  try {
    cleanDist();
    validate();
    copyStatic();
    buildCss();
    await buildJs();
    processHtml();
    copyToBackend();
    console.log('✅ Build completed');
  } catch (err) {
    console.error(`❌ Build failed: ${err.message}`);
    process.exit(1);
  }
}

build();