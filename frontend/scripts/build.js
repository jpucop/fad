import tailwindcss from '@tailwindcss/postcss';
import autoprefixer from 'autoprefixer';
import cssnano from 'cssnano';
import esbuild from 'esbuild';
import fs from 'fs';
import path from 'path';
import postcss from 'postcss';
import { CONFIG } from './config.js';
import { validateSprite } from './sprite.js';

const srcPath = CONFIG.paths.src;
const distPath = CONFIG.paths.dist;
const backendPath = CONFIG.paths.backend;

function cleanDist() {
  if (fs.existsSync(distPath)) {
    fs.rmSync(distPath, { recursive: true, force: true });
    console.log(`✅ Cleaned ${distPath}`);
  }
  fs.mkdirSync(distPath, { recursive: true });
}

function validate() {
  const indexHtml = CONFIG.src.html.find(file => file === 'index.html');
  if (indexHtml && !fs.existsSync(path.join(srcPath, indexHtml))) {
    throw new Error(`❌ Critical file missing: index.html`);
  }
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
  // Generate sprite.svg if missing
  const spriteSrc = path.join(srcPath, CONFIG.src.sprite);
  if (!fs.existsSync(spriteSrc)) {
    console.log(`⚠️ sprite.svg missing in src/, generating...`);
    validateSprite(); // Generates src/sprite.svg
  }

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
    content: [...CONFIG.src.html, ...CONFIG.src.js].map(file => path.join(srcPath, file)),
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

async function buildJs() {
  const jsConfig = CONFIG.build.js || { bundleAlpine: true, output: 'app.js' };
  const jsOutput = path.join(distPath, jsConfig.output);
  const jsFiles = jsConfig.bundleAlpine
    ? CONFIG.src.js
    : CONFIG.src.js.filter(
      file => file !== CONFIG.build.alpine.dev.filename && file !== CONFIG.build.alpine.min.filename
    );

  // Prepare Alpine.js if not bundled
  if (!jsConfig.bundleAlpine) {
    const alpineDevSrc = path.join(srcPath, CONFIG.build.alpine.dev.filename);
    const alpineMinSrc = path.join(srcPath, CONFIG.build.alpine.min.filename);
    const alpineDevModule = path.join(CONFIG.paths.base, '../node_modules', CONFIG.build.alpine.dev.modulePath);
    const alpineMinModule = path.join(CONFIG.paths.base, '../node_modules', CONFIG.build.alpine.min.modulePath);

    if (!fs.existsSync(alpineDevSrc) && fs.existsSync(alpineDevModule)) {
      fs.copyFileSync(alpineDevModule, alpineDevSrc);
      console.log(`✅ Created ${CONFIG.build.alpine.dev.filename} in src from node_modules`);
    }
    if (!fs.existsSync(alpineMinSrc) && fs.existsSync(alpineMinModule)) {
      fs.copyFileSync(alpineMinModule, alpineMinSrc);
      console.log(`✅ Created ${CONFIG.build.alpine.min.filename} in src from node_modules`);
    }

    const alpineSource = CONFIG.build.isProduction ? alpineMinSrc : alpineDevSrc;
    const alpineDest = path.join(distPath, CONFIG.build.alpine.output);
    if (fs.existsSync(alpineSource)) {
      fs.copyFileSync(alpineSource, alpineDest);
      console.log(`✅ Copied ${CONFIG.build.isProduction ? CONFIG.build.alpine.min.filename : CONFIG.build.alpine.dev.filename} to dist as ${CONFIG.build.alpine.output}`);
    } else {
      console.warn(`⚠️ Warning: ${CONFIG.build.isProduction ? CONFIG.build.alpine.min.filename : CONFIG.build.alpine.dev.filename} not found in src/`);
    }
  }

  // Bundle JS files
  const entryPoints = jsFiles.map(file => path.join(srcPath, file)).filter(fs.existsSync);
  if (entryPoints.length === 0) {
    console.warn(`⚠️ No JS files found for bundling; skipping JS build`);
    return;
  }

  // Create temporary entry file for bundling
  const tempEntryPath = path.join(distPath, 'temp-entry.js');
  const imports = entryPoints.map(file => `import "${path.relative(distPath, file).replace(/\\/g, '/')}";`).join('\n');
  fs.writeFileSync(tempEntryPath, imports);

  try {
    await esbuild.build({
      entryPoints: [tempEntryPath],
      bundle: true,
      outfile: jsOutput,
      minify: CONFIG.build.minify,
      sourcemap: CONFIG.build.sourcemap,
      format: 'iife',
      target: 'es2018',
    });
    console.log(`✅ Bundled JS into ${jsConfig.output}`);
  } catch (err) {
    throw new Error(`❌ JS build failed: ${err.message}`);
  } finally {
    if (fs.existsSync(tempEntryPath)) {
      fs.unlinkSync(tempEntryPath);
    }
  }
}

function replaceIconSpans(html) {
  let updatedHtml = html;
  let replacements = 0;

  const spanRegex = /<span\s+([^>]*)class\s*=\s*['"]([^'"]*icon[^'"]*)['"]([^>]*)>(.*?)<\/span>/gi;
  const matches = [...html.matchAll(spanRegex)];
  console.log(`✅ Found ${matches.length} icon spans`);

  for (const match of matches) {
    const [fullMatch, preAttrs, classValue, postAttrs, content] = match;
    const classes = classValue.trim().split(/\s+/);
    if (!classes.includes('icon')) continue;

    const iconClass = classes.find(cls => CONFIG.iconConfig.validateRegex.test(cls));
    if (!iconClass) continue;

    const attrs = `${preAttrs || ''} ${postAttrs || ''}`
      .trim()
      .split(/\s+/)
      .filter(attr => attr && !attr.startsWith('class='))
      .join(' ');

    const spanClasses = classes.join(' ');
    const svgTag = `<svg class="icon-inner" aria-hidden="true"><use href="/sprite.svg#${iconClass}"></use></svg>`;
    const replacement = `<span class="${spanClasses}" ${attrs}>${svgTag}</span>`;

    updatedHtml = updatedHtml.replace(fullMatch, replacement);
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
  if (!fs.existsSync(backendPath) || !fs.statSync(backendPath).isDirectory()) {
    console.warn(`⚠️ Backend path not found or invalid: ${backendPath}, skipping copy`);
    return;
  }

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

async function build(watch = false, deploy = false) {
  console.log(`building .. watch: ${watch}, deploy: ${deploy}`);
  try {
    if (deploy) {
      copyToBackend();
      return;
    }

    validate();
    cleanDist();
    copyStatic();
    await buildCss();
    await buildJs();
    processHtml();
    console.log('✅ Build completed');
  } catch (err) {
    console.error(`❌ Build failed: ${err.message}`);
    process.exit(1);
  }

  if (watch) {
    console.log('👀 Watching for changes...');
    const context = await esbuild.context({
      entryPoints: [path.join(distPath, 'temp-entry.js')],
      bundle: true,
      outfile: path.join(distPath, (CONFIG.build.js || { output: 'app.js' }).output),
      minify: CONFIG.build.minify,
      sourcemap: CONFIG.build.sourcemap,
      format: 'iife',
      target: 'es2018',
      write: false,
    });
    await context.watch();
    const { watch: chokidarWatch } = await import('chokidar');
    chokidarWatch([path.join(srcPath, '*.{js,css,html,ico,png,jpg,jpeg,gif,webp,avif,woff,woff2,json}')], {
      ignoreInitial: true,
    }).on('all', async (event, file) => {
      console.log(`🔄 Detected ${event}: ${file}`);
      try {
        if (file.endsWith('.js')) {
          const jsFiles = (CONFIG.build.js || { bundleAlpine: true }).bundleAlpine
            ? CONFIG.src.js
            : CONFIG.src.js.filter(
              f => f !== CONFIG.build.alpine.dev.filename && f !== CONFIG.build.alpine.min.filename
            );
          const entryPoints = jsFiles.map(f => path.join(srcPath, f)).filter(fs.existsSync);
          if (entryPoints.length > 0) {
            const tempEntryPath = path.join(distPath, 'temp-entry.js');
            const imports = entryPoints.map(f => `import "${path.relative(distPath, f).replace(/\\/g, '/')}";`).join('\n');
            fs.writeFileSync(tempEntryPath, imports);
            await context.rebuild();
            if (fs.existsSync(tempEntryPath)) fs.unlinkSync(tempEntryPath);
          }
        }
        if (file.endsWith('.css')) await buildCss();
        if (file.endsWith('.html')) processHtml();
        if (CONFIG.src.static.includes(path.relative(srcPath, file))) copyStatic();
        console.log('✅ Incremental build completed');
      } catch (err) {
        console.error(`❌ Incremental build failed: ${err.message}`);
      }
    });
  }
}

const isWatchMode = process.argv.includes('--watch');
const isDeploy = process.argv.includes('--deploy');
await build(isWatchMode, isDeploy);
console.log('done');