import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';
import esbuild from 'esbuild';

// Configuration
const CONFIG = {
  minify: process.env.MINIFY === 'true', // Minify output if env var is set
  dirname: path.dirname(fileURLToPath(import.meta.url)),
  srcDir: '../src',
  distDir: '../dist',
  files: [
    'index.html',
    'app.js',
    'styles.css',
    'sprite.svg',
    'favicon.ico',
    { dir: 'img', exclude: /\.svg$/ },
  ],
  regexes: {
    // Matches <span class="... [l-|i-]{icon-name} ..." [attributes]></span>
    iconSpan: (prefix, name) =>
      `<span\\s+([^>]*class="[^"]*\\b${prefix}${name}\\b[^"]*"[^>]*)>(.*?)</span>`,
    // Detects all spans with l- or i- prefixed classes
    iconClass: /<span\s+[^>]*class="[^"]*\b(l-|i-)[a-z0-9-]+(?=\b[^"]*)"[^>]*>/g,
    // Extracts prefix and name from class
    extractIcon: /(l-|i-)([a-z0-9-]+)(?=\b|$)/,
  },
};

// Derived paths
const srcPath = path.join(CONFIG.dirname, CONFIG.srcDir);
const distPath = path.join(CONFIG.dirname, CONFIG.distDir);

function validate() {
  for (const item of CONFIG.files) {
    const file = typeof item === 'string' ? item : item.dir;
    const src = path.join(srcPath, file);
    if (!fs.existsSync(src)) {
      if (file === 'img') fs.mkdirSync(src, { recursive: true });
      else throw new Error(`${file} not found: ${src}`);
    }
  }
}

function copyStatic() {
  fs.mkdirSync(distPath, { recursive: true });
  for (const item of CONFIG.files) {
    const file = typeof item === 'string' ? item : item.dir;
    const src = path.join(srcPath, file);
    const dest = path.join(distPath, file);
    if (!fs.existsSync(src)) continue;

    const stat = fs.statSync(src);
    if (stat.isDirectory()) {
      fs.mkdirSync(dest, { recursive: true });
      const files = fs.readdirSync(src).filter(f => !item.exclude?.test(f));
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

function buildCss() {
  const src = path.join(srcPath, 'styles.css');
  const dest = path.join(distPath, 'styles.css');
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  try {
    execSync(
      `npx @tailwindcss/cli -i ${src} -o ${dest} ${CONFIG.minify ? '--minify' : ''}`,
      { stdio: 'inherit' }
    );
    console.log(`✅ Compiled CSS to ${dest}`);
  } catch (err) {
    throw new Error(`CSS build failed: ${err.message}`);
  }
}

async function buildJs() {
  const src = path.join(srcPath, 'app.js');
  const dest = path.join(distPath, 'app.js');
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  await esbuild.build({
    entryPoints: [src],
    bundle: true,
    outfile: dest,
    minify: CONFIG.minify,
    format: 'iife',
    globalName: 'app',
    sourcemap: false,
    loader: { '.js': 'jsx' },
  });
  console.log(`✅ Compiled JS to ${dest}`);
}

function replaceIconSpans(html) {
  let updatedHtml = html;
  let replacements = 0;

  // Log HTML sample for debugging
  console.log(`🔍 Input HTML sample: ${html.slice(0, 500)}`);

  // Find all spans with potential icon classes
  const spans = html.match(CONFIG.regexes.iconClass) || [];
  console.log(`🔍 Found ${spans.length} potential icon spans`);

  const iconClasses = new Set();
  for (const span of spans) {
    const classMatch = span.match(CONFIG.regexes.extractIcon);
    if (classMatch) {
      const [, prefix, name] = classMatch;
      iconClasses.add(`${prefix}${name}`);
    }
  }
  console.log(`🔍 Detected icon classes: ${[...iconClasses].join(', ')}`);

  for (const iconKey of iconClasses) {
    console.log(`🔍 Processing icon: ${iconKey}`);
    const match = iconKey.match(CONFIG.regexes.extractIcon);
    if (!match) {
      console.warn(`⚠️ Invalid icon format: ${iconKey}`);
      continue;
    }
    const [, prefix, name] = match;
    const symbolId = `${prefix}${name}`;
    const regexPattern = CONFIG.regexes.iconSpan(prefix, name);
    const regex = new RegExp(regexPattern, 'gs'); // 's' flag for multiline
    console.log(`🔧 Regex for ${symbolId}: ${regexPattern}`);

    let matchCount = 0;
    updatedHtml = updatedHtml.replace(regex, (match, attributes, content) => {
      matchCount++;
      const classMatch = attributes.match(/class="([^"]*)"/);
      const classNames = classMatch ? classMatch[1] : '';
      const classList = classNames
        .split(/\s+/)
        .filter(cls => cls && cls !== symbolId);
      if (!classList.includes('icon')) classList.unshift('icon');
      const cleanedClasses = classList.length > 0 ? classList.join(' ') : 'icon';
      console.log(`🔄 Replacing span for ${symbolId}: ${match}`);
      return `<svg class="${cleanedClasses}" aria-hidden="true"><use href="/sprite.svg#${symbolId}"></use></svg>`;
    });
    console.log(`🔄 Replaced ${matchCount} spans for ${symbolId}`);
    replacements += matchCount;
  }

  console.log(`🔄 Total replaced ${replacements} icon spans`);
  return updatedHtml;
}

function processHtml() {
  const src = path.join(srcPath, 'index.html');
  const dest = path.join(distPath, 'index.html');
  let html = fs.readFileSync(src, 'utf8');
  html = replaceIconSpans(html);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, html, 'utf8');
  console.log(`✅ Processed HTML to ${dest}`);
}

async function build() {
  try {
    validate();
    copyStatic();
    buildCss();
    await buildJs();
    processHtml();
    console.log('✅ Build completed');
  } catch (err) {
    console.error(`❌ Build failed: ${err.message}`);
    process.exit(1);
  }
}

build();