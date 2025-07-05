import esbuild from 'esbuild';
import { globSync } from 'glob';
import fs from 'fs/promises';
import path from 'path';
import { cleanupSVG, parseColors, runSVGO, SVG } from '@iconify/tools';
import { getIconData, iconToSVG } from '@iconify/utils';
import { optimize } from 'svgo';
import { fileURLToPath } from 'url';
import chokidar from 'chokidar';

// Load configuration from config.json
const baseDir = path.dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(await fs.readFile(path.join(baseDir, 'config.json'), 'utf8'));

// Paths from config.json
const srcPath = path.resolve(baseDir, config.paths.src);
const distPath = path.resolve(baseDir, config.paths.dist);
const backendPath = path.resolve(baseDir, config.paths.backend);
const spritePath = path.join(srcPath, config.src.sprite);
const imgPath = path.join(srcPath, config.src.imgDir);
const iconifyPath = path.join(baseDir, config.paths.iconify);

// Configuration
const CONFIG = {
  build: {
    isProduction: process.env.env === 'prod',
    minify: process.env.env === 'prod',
    sourcemap: process.env.env !== 'prod',
    js: config.build.js,
    alpine: config.build.alpine,
  },
  paths: { src: srcPath, dist: distPath, backend: backendPath },
  src: {
    js: globSync(`${srcPath}/*.js`).map(path.basename),
    css: globSync(`${srcPath}/*.css`).map(path.basename),
    html: globSync(`${srcPath}/*.html`).map(path.basename),
    static: globSync(`${srcPath}/*.{ico,png,jpg,jpeg,gif}`).map(path.basename),
    sprite: config.src.sprite,
    img: [{ dir: config.src.imgDir, exclude: /\.svg$/ }],
  },
  iconConfig: config.iconConfig,
};

// Utility Functions
async function cleanDist() {
  await fs.rm(distPath, { recursive: true, force: true });
  await fs.mkdir(distPath, { recursive: true });
  console.log(`✅ Cleaned ${distPath}`);
}

async function copyFiles(src, dest, filter = null) {
  const stat = await fs.stat(src).catch(() => null);
  if (!stat) return;
  if (stat.isDirectory()) {
    await fs.mkdir(dest, { recursive: true });
    const files = (await fs.readdir(src)).filter(f => !filter || !filter.test(f));
    await Promise.all(files.map(f => copyFiles(path.join(src, f), path.join(dest, f))));
  } else {
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.copyFile(src, dest);
    console.log(`✅ Copied ${path.basename(src)} to ${dest}`);
  }
}

async function copyStatic() {
  if (!await fs.stat(imgPath).catch(() => false)) await fs.mkdir(imgPath, { recursive: true });
  if (!await fs.stat(spritePath).catch(() => false)) await validateSprite();
  const items = [CONFIG.src.sprite, ...CONFIG.src.img, ...CONFIG.src.static];
  await Promise.all(items.map(item => {
    const file = typeof item === 'string' ? item : item.dir;
    const src = path.join(srcPath, file);
    const dest = path.join(distPath, file);
    const filter = typeof item === 'object' && item.exclude ? item.exclude : null;
    return copyFiles(src, dest, filter);
  }));
}

async function buildCss() {
  const entryPoints = CONFIG.src.css.map(f => path.join(srcPath, f));
  if (!entryPoints.length) return;
  await esbuild.build({
    entryPoints,
    outdir: distPath,
    bundle: true,
    minify: CONFIG.build.minify,
    sourcemap: CONFIG.build.sourcemap,
    loader: { '.css': 'css' },
    plugins: [{
      name: 'tailwind',
      setup(build) {
        build.onLoad({ filter: /\.css$/ }, async args => {
          const css = await fs.readFile(args.path, 'utf8');
          const result = await require('postcss')([
            require('@tailwindcss/postcss')({
              content: [...CONFIG.src.html, ...CONFIG.src.js].map(f => path.join(srcPath, f)),
              darkMode: 'class',
              theme: { extend: {} },
              plugins: [],
            }),
            require('autoprefixer'),
            ...(CONFIG.build.isProduction ? [require('cssnano')({ preset: 'default' })] : []),
          ]).process(css, { from: args.path, to: path.join(distPath, path.basename(args.path)) });
          return { contents: result.css, loader: 'css' };
        });
      },
    }],
  });
  console.log(`✅ Compiled ${CONFIG.src.css.length} CSS files`);
}

async function buildJs() {
  const jsConfig = CONFIG.build.js;
  const entryPoints = (jsConfig.bundleAlpine ? CONFIG.src.js : CONFIG.src.js.filter(f => f !== CONFIG.build.alpine.dev.filename && f !== CONFIG.build.alpine.min.filename))
    .map(f => path.join(srcPath, f))
    .filter(f => fs.statSync(f).catch(() => false));
  if (!entryPoints.length) {
    console.warn('⚠️ No JS files found for bundling');
    return;
  }
  if (!jsConfig.bundleAlpine) {
    const alpineSrc = path.join(srcPath, CONFIG.build.isProduction ? CONFIG.build.alpine.min.filename : CONFIG.build.alpine.dev.filename);
    const alpineDest = path.join(distPath, CONFIG.build.alpine.output);
    const alpineModule = path.join(baseDir, config.paths.iconify, CONFIG.build.alpine[CONFIG.build.isProduction ? 'min' : 'dev'].modulePath);
    if (!await fs.stat(alpineSrc).catch(() => false) && await fs.stat(alpineModule).catch(() => false)) {
      await fs.copyFile(alpineModule, alpineSrc);
      console.log(`✅ Created ${path.basename(alpineSrc)} from node_modules`);
    }
    if (await fs.stat(alpineSrc).catch(() => false)) {
      await fs.copyFile(alpineSrc, alpineDest);
      console.log(`✅ Copied ${path.basename(alpineSrc)} to ${CONFIG.build.alpine.output}`);
    }
  }
  await esbuild.build({
    entryPoints,
    outdir: distPath,
    bundle: true,
    minify: CONFIG.build.minify,
    sourcemap: CONFIG.build.sourcemap,
    format: 'iife',
    target: 'es2018',
  });
  console.log(`✅ Bundled ${entryPoints.length} JS files into ${jsConfig.output}`);
}

async function processHtml() {
  const iconRegex = /<span\s+([^>]*)class\s*=\s*['"]([^'"]*icon[^'"]*)['"]([^>]*)>(.*?)<\/span>/gi;
  await Promise.all(CONFIG.src.html.map(async file => {
    const src = path.join(srcPath, file);
    const dest = path.join(distPath, file);
    let html = await fs.readFile(src, 'utf8');
    let replacements = 0;
    html = html.replace(iconRegex, (match, preAttrs, classValue, postAttrs, content) => {
      const classes = classValue.trim().split(/\s+/);
      if (!classes.includes('icon')) return match;
      const iconClass = classes.find(cls => CONFIG.iconConfig.validateRegex.test(cls));
      if (!iconClass) return match;
      const attrs = `${preAttrs || ''} ${postAttrs || ''}`.trim().split(/\s+/).filter(a => a && !a.startsWith('class=')).join(' ');
      replacements++;
      return `<span class="${classValue}" ${attrs}><svg class="icon-inner" aria-hidden="true"><use href="/sprite.svg#${iconClass}"></use></svg></span>`;
    });
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.writeFile(dest, html);
    console.log(`✅ Processed ${file} (${replacements} icon spans)`);
  }));
}

async function copyToBackend() {
  if (!await fs.stat(backendPath).catch(() => false)) {
    console.warn(`⚠️ Backend path not found: ${backendPath}`);
    return;
  }
  await copyFiles(distPath, backendPath);
}

// Sprite Generation
const svgoSpriteConfig = {
  plugins: [
    { name: 'removeDimensions' },
    { name: 'removeAttrs', params: { attrs: ['fill'] } },
    { name: 'convertTransform' },
    { name: 'cleanupNumericValues', params: { floatPrecision: 0 } },
    { name: 'removeUselessStrokeAndFill' },
    { name: 'mergePaths' },
    { name: 'removeXMLNS' },
  ],
};

async function extractIconRefs() {
  const matches = new Set();
  for (const file of CONFIG.src.html) {
    const html = await fs.readFile(path.join(srcPath, file), 'utf8').catch(() => '');
    for (const span of html.match(CONFIG.iconConfig.spanRegex) || []) {
      const classMatch = span.match(/class="([^"]*)"/);
      if (classMatch) {
        const iconClass = classMatch[1].split(/\s+/).find(cls => CONFIG.iconConfig.validateRegex.test(cls));
        if (iconClass) matches.add(iconClass);
      }
    }
  }
  return Array.from(matches);
}

async function generateSprite(iconClasses) {
  const symbols = [];
  for (const ref of iconClasses) {
    try {
      if (ref.startsWith('i-')) {
        const [, pkg, name] = ref.match(/^i-([a-z0-9]+)-([a-z0-9]+(?:-[a-z0-9]+)*)$/);
        const iconSet = JSON.parse(await fs.readFile(path.join(iconifyPath, `${pkg}/icons.json`)));
        const iconData = getIconData(iconSet, name);
        if (!iconData) throw new Error(`Icon not found: ${name}`);
        const svgObj = iconToSVG(iconData, { height: '1em', width: 'auto' });
        const svg = new SVG(`<svg viewBox="${svgObj.attributes.viewBox || '0 0 24 24'}" xmlns="http://www.w3.org/2000/svg">${svgObj.body}</svg>`);
        cleanupSVG(svg);
        parseColors(svg, { defaultColor: 'currentColor', callback: (_, colorStr) => colorStr === 'none' ? colorStr : 'currentColor' });
        runSVGO(svg);
        symbols.push(`<symbol id="${ref}" viewBox="${svgObj.attributes.viewBox || '0 0 24 24'}">${svg.getBody()}</symbol>`);
      } else if (ref.startsWith('l-')) {
        const name = ref.slice(2);
        const svgPath = path.join(imgPath, `${name}.svg`);
        let svg = await fs.readFile(svgPath, 'utf8').catch(() => { throw new Error(`Local icon not found: ${svgPath}`); });
        svg = svg.replace(/<\?xml[^?]*\?>\s*/, '');
        const optimizedSvg = optimize(svg, svgoSpriteConfig).data;
        const viewBox = optimizedSvg.match(/viewBox="([^"]+)"/)?.[1] || '0 0 24 24';
        const content = optimizedSvg.replace(/^<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '').trim();
        if (!content) throw new Error(`No valid SVG content in ${svgPath}`);
        symbols.push(`<symbol id="${ref}" viewBox="${viewBox}">${content}</symbol>`);
      }
    } catch (err) {
      console.error(`❌ Error processing ${ref}: ${err.message}`);
    }
  }
  const spriteContent = `<svg xmlns="http://www.w3.org/2000/svg" style="display:none">\n${symbols.join('\n')}\n</svg>`;
  await fs.mkdir(path.dirname(spritePath), { recursive: true });
  await fs.writeFile(spritePath, symbols.length ? spriteContent : '<svg></svg>');
  console.log(`✅ Sprite generated: ${spritePath} (${symbols.length} symbols)`);
}

async function validateSprite() {
  if (!CONFIG.src.html.length || !CONFIG.src.html.some(f => f.toLowerCase() === 'index.html')) {
    throw new Error(`❌ No index.html found in ${srcPath}`);
  }
  const iconClasses = await extractIconRefs();
  const spriteContent = await fs.readFile(spritePath, 'utf8').catch(() => '');
  const symbolIds = new Set([...spriteContent.matchAll(CONFIG.iconConfig.symbolRegex)].map(m => m[1]));
  const missingIcons = iconClasses.filter(id => !symbolIds.has(id));
  const unusedIcons = [...symbolIds].filter(id => !iconClasses.includes(id));
  if (missingIcons.length || unusedIcons.length || !spriteContent) {
    console.warn(`⚠️ Sprite issues: ${missingIcons.length} missing, ${unusedIcons.length} unused`);
    if (missingIcons.length) console.warn(`⚠️ Missing: ${missingIcons.join(', ')}`);
    if (unusedIcons.length) console.warn(`⚠️ Unused: ${unusedIcons.join(', ')}`);
    await generateSprite(iconClasses);
  } else {
    console.log('✅ Sprite validation passed');
  }
}

async function cleanLocalSvgs() {
  const files = (await fs.readdir(imgPath).catch(() => [])).filter(f => f.endsWith('.svg'));
  if (!files.length) return console.log('ℹ️ No SVGs found in src/img/');
  for (const file of files) {
    const filePath = path.join(imgPath, file);
    let svg = await fs.readFile(filePath, 'utf8').replace(/<\?xml[^?]*\?>\s*/, '').replace(/<!DOCTYPE[^>]*>\s*/, '');
    const icon = new SVG(svg);
    cleanupSVG(icon);
    parseColors(icon, { defaultColor: 'currentColor', callback: (_, colorStr) => colorStr === 'none' ? colorStr : 'currentColor' });
    const optimized = optimize(icon.toMinifiedString(), { plugins: ['preset-default', { name: 'removeViewBox', active: false }, { name: 'cleanupNumericValues', params: { floatPrecision: 3 } }] });
    await fs.writeFile(filePath, optimized.data);
    console.log(`✅ Cleaned ${file}`);
  }
}

// Main Build Function
async function build(watch = false, deploy = false) {
  console.log(`Building... watch: ${watch}, deploy: ${deploy}`);
  try {
    if (deploy) return await copyToBackend();
    await cleanDist();
    await cleanLocalSvgs();
    await copyStatic();
    await buildCss();
    await buildJs();
    await processHtml();
    console.log('✅ Build completed');
    if (watch) {
      console.log('👀 Watching for changes...');
      const watcher = chokidar.watch([`${srcPath}/*.{js,css,html,ico,png,jpg,jpeg,gif,webp,avif,woff,woff2,json}`], { ignoreInitial: true });
      watcher.on('all', async (event, file) => {
        console.log(`🔄 Detected ${event}: ${file}`);
        try {
          if (file.endsWith('.css')) await buildCss();
          if (file.endsWith('.js')) await buildJs();
          if (file.endsWith('.html')) await processHtml();
          if (CONFIG.src.static.includes(path.basename(file))) await copyStatic();
          console.log('✅ Incremental build completed');
        } catch (err) {
          console.error(`❌ Incremental build failed: ${err.message}`);
        }
      });
    }
  } catch (err) {
    console.error(`❌ Build failed: ${err.message}`);
    process.exit(1);
  }
}

// Run Build
const isWatchMode = process.argv.includes('--watch');
const isDeploy = process.argv.includes('--deploy');
build(isWatchMode, isDeploy).then(() => console.log('done'));