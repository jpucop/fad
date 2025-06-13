import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';
import esbuild from 'esbuild';
import postcss from 'postcss';
import cssnano from 'cssnano';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const srcPath = path.join(__dirname, '../src');
const distPath = path.join(__dirname, '../dist');
const spritePath = path.join(srcPath, 'icons.svg');
const distSpritePath = path.join(distPath, 'icons/icons.svg');
const indexHtmlPath = path.join(srcPath, 'index.html');
const distHtmlPath = path.join(distPath, 'index.html');
const minify = process.env.MINIFY === 'true';

console.log(`🛠️ Building project (minify: ${minify})`);

// Copy static assets
function copyStatic() {
  const imgSrc = path.join(srcPath, 'img');
  const imgDist = path.join(distPath, 'img');
  fs.mkdirSync(imgDist, { recursive: true });
  const files = fs.readdirSync(imgSrc).filter(f => !f.endsWith('.svg'));
  for (const file of files) {
    fs.copyFileSync(path.join(imgSrc, file), path.join(imgDist, file));
    console.log(`✅ Copied ${file} to ${imgDist}`);
  }
}

// Compile Tailwind CSS
async function buildCss() {
  const cssSrc = path.join(srcPath, 'css', 'styles.css');
  const cssDist = path.join(distPath, 'css');
  fs.mkdirSync(cssDist, { recursive: true });
  try {
    execSync(`npx tailwindcss -i ${cssSrc} -o ${path.join(cssDist, 'styles.css')} ${minify ? '--minify' : ''}`, { stdio: 'inherit' });
    if (minify) {
      const cssContent = fs.readFileSync(path.join(cssDist, 'styles.css'), 'utf8');
      const result = await postcss([cssnano]).process(cssContent, { from: undefined });
      fs.writeFileSync(path.join(cssDist, 'styles.css'), result.css, 'utf8');
    }
    console.log(`✅ Compiled Tailwind CSS to ${cssDist}/styles.css`);
  } catch (err) {
    throw new Error(`CSS build failed: ${err.message}`);
  }
}

// Compile JS with Alpine.js
async function buildJs() {
  const jsDist = path.join(distPath, 'js');
  fs.mkdirSync(jsDist, { recursive: true });
  await esbuild.build({
    entryPoints: [path.join(srcPath, 'js', 'app.js')],
    bundle: true,
    outfile: path.join(jsDist, 'app.js'),
    minify,
    format: 'esm',
    external: [],
    loader: { '.js': 'jsx' },
  });
  console.log(`✅ Compiled JS to ${jsDist}/app.js`);
}

// Process HTML
function processHtml() {
  let html = fs.readFileSync(indexHtmlPath, 'utf8');
  if (fs.existsSync(spritePath)) {
    const spriteContent = fs.readFileSync(spritePath, 'utf8');
    html = html.replace('</head>', `${spriteContent}</head>`);
    fs.mkdirSync(path.dirname(distSpritePath), { recursive: true });
    fs.copyFileSync(spritePath, distSpritePath);
    console.log(`✅ Embedded sprite and copied to ${distSpritePath}`);
  } else {
    console.warn(`⚠️ No sprite at ${spritePath}, skipping embed`);
  }
  html = html.replace(
    /<i\s+class="([^"]*?\b(i|l)-[a-z0-9-]+[^"]*?)"><\/i>/g,
    (match, className, prefix) => `<svg class="${className}"><use href="#${prefix}-${className.match(/(i|l)-([a-z0-9-]+(?:-[a-z0-9]+)*)/)[2]}"></use></svg>`
  );
  fs.writeFileSync(distHtmlPath, html, 'utf8');
  console.log(`✅ Processed HTML to ${distHtmlPath}`);
}

// Main
async function build() {
  try {
    fs.mkdirSync(distPath, { recursive: true });
    copyStatic();
    await buildCss();
    await buildJs();
    processHtml();
    console.log('✅ Build completed');
  } catch (err) {
    console.error(`❌ Build failed: ${err.message}`);
    process.exit(1);
  }
}

build();