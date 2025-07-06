import { globSync } from 'glob';
import fs from 'fs/promises';
import path from 'path';
import { cleanupSVG, parseColors, runSVGO, SVG } from '@iconify/tools';
import { getIconData, iconToSVG } from '@iconify/utils';
import { optimize } from 'svgo';
import { fileURLToPath } from 'url';
import chokidar from 'chokidar';
import postcss from 'postcss';
import tailwindcss from '@tailwindcss/postcss';
import autoprefixer from 'autoprefixer';
import cssnano from 'cssnano';

// Global error handling for uncaught errors
process.on('uncaughtException', (err) => {
  console.error(`❌ Uncaught Exception: ${err.message}`);
  console.error(err.stack);
  process.exit(1);
});
process.on('unhandledRejection', (err) => {
  console.error(`❌ Unhandled Rejection: ${err.message}`);
  console.error(err.stack);
  process.exit(1);
});

async function resolveConfig(args = {}) {
  const baseDir = path.dirname(fileURLToPath(import.meta.url));
  try {
    console.log('📋 Loading config.json...');
    const rawConfig = await fs.readFile(path.join(baseDir, 'config.json'), 'utf8').then(JSON.parse).catch(err => {
      throw new Error(`Failed to load config.json: ${err.message}`);
    });
    console.log('✅ config.json loaded');
    return {
      ...rawConfig,
      prod: args.prod || process.env.env === 'prod',
      watch: args.watch || process.argv.includes('--watch'),
      deploy: args.deploy || process.argv.includes('--deploy'),
      svgo: {
        sprite: {
          plugins: [
            { name: 'removeDimensions' },
            { name: 'removeAttrs', params: { attrs: ['fill'] } },
            { name: 'convertTransform' },
            { name: 'cleanupNumericValues', params: { floatPrecision: 0 } },
            { name: 'removeUselessStrokeAndFill' },
            { name: 'mergePaths' },
            { name: 'removeXMLNS' },
          ],
        },
        clean: {
          plugins: [
            'preset-default',
            { name: 'removeViewBox', active: false },
            { name: 'cleanupNumericValues', params: { floatPrecision: 3 } },
          ],
        },
      },
    };
  } catch (err) {
    console.error(`❌ resolveConfig failed: ${err.message}`);
    throw err;
  }
}

async function cleanDist(config) {
  const distPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.dist);
  try {
    console.log(`📋 Cleaning ${config.paths.dist}...`);
    await fs.rm(distPath, { recursive: true, force: true });
    await fs.mkdir(distPath, { recursive: true });
    console.log(`✅ Cleaned ${config.paths.dist}`);
  } catch (err) {
    console.error(`❌ cleanDist failed: ${err.message}`);
    throw err;
  }
}

async function copyFiles(src, dest) {
  try {
    if (!(await fs.stat(src).catch(() => false))) {
      console.warn(`⚠️ Source file not found: ${src}`);
      return;
    }
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.copyFile(src, dest);
    console.log(`✅ Copied ${path.basename(src)}`);
  } catch (err) {
    console.error(`❌ copyFiles failed for ${src}: ${err.message}`);
  }
}

async function copyStatic(config) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  const distPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.dist);
  const spritePath = path.join(srcPath, config.sprite.filename);
  const spriteDistPath = path.join(distPath, config.sprite.filename);
  try {
    console.log('📋 Copying static files...');
    const staticFiles = globSync(`${srcPath}/**/*.{ico,png,jpg,jpeg,gif}`).map(f => path.relative(srcPath, f));
    await Promise.all([
      ...staticFiles.map(f => copyFiles(path.join(srcPath, f), path.join(distPath, f))),
      copyFiles(spritePath, spriteDistPath),
    ]);
    console.log('✅ Static files copied');
  } catch (err) {
    console.error(`❌ copyStatic failed: ${err.message}`);
    throw err;
  }
}

async function buildCss(config) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  const distPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.dist);
  try {
    console.log('📋 Processing CSS files...');
    const cssFiles = globSync(`${srcPath}/**/*.css`).map(f => path.relative(srcPath, f));
    await Promise.all(cssFiles.map(async file => {
      const src = path.join(srcPath, file);
      const dest = path.join(distPath, file);
      if (!await fs.stat(src).catch(() => false)) {
        console.warn(`⚠️ CSS file not found: ${src}`);
        return;
      }
      const css = await fs.readFile(src, 'utf8');
      const plugins = [tailwindcss({ content: globSync(`${srcPath}/**/*.html`).map(f => path.join(srcPath, path.relative(srcPath, f))) }), autoprefixer];
      if (config.prod) plugins.push(cssnano({ preset: 'default' }));
      const result = await postcss(plugins).process(css, { from: src, to: dest });
      await fs.mkdir(path.dirname(dest), { recursive: true });
      await fs.writeFile(dest, result.css);
      console.log(`✅ Processed ${file}`);
    }));
    console.log('✅ CSS processing completed');
  } catch (err) {
    console.error(`❌ buildCss failed: ${err.message}`);
    throw err;
  }
}

async function buildJs(config) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  const distPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.dist);
  const nodeModulesPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.node_modules);
  try {
    console.log('📋 Processing JS files...');
    const jsFiles = globSync(`${srcPath}/**/*.js`).map(f => path.relative(srcPath, f));
    const alpineSrc = path.join(nodeModulesPath, config.js.alpine[config.prod ? 'nodeModulePathMin' : 'nodeModulePath']);
    const alpineDest = path.join(srcPath, 'alpine.js');
    if (await fs.stat(alpineSrc).catch(() => false)) await copyFiles(alpineSrc, alpineDest);
    await Promise.all(jsFiles.map(f => copyFiles(path.join(srcPath, f), path.join(distPath, f))));
    console.log('✅ JS processing completed');
  } catch (err) {
    console.error(`❌ buildJs failed: ${err.message}`);
    throw err;
  }
}

async function processHtml(config) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  const distPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.dist);
  const iconRegex = new RegExp(config.sprite.scan, 'gi');
  try {
    console.log('📋 Processing HTML files...');
    const htmlFiles = globSync(`${srcPath}/**/*.html`).map(f => path.relative(srcPath, f));
    if (!htmlFiles.includes(config.paths.index)) {
      console.warn(`⚠️ index.html not found in HTML files: ${htmlFiles.join(', ') || 'none'}`);
    }
    await Promise.all(htmlFiles.map(async file => {
      const src = path.join(srcPath, file);
      const dest = path.join(distPath, file);
      let html = await fs.readFile(src, 'utf8').catch(() => '');
      if (!html) {
        console.warn(`⚠️ Failed to read ${file}`);
        return;
      }
      let replacements = 0;
      html = html.replace(iconRegex, (match) => {
        const classMatch = match.match(/class=(["'])(.*?)\1/);
        if (!classMatch) return match;
        const classes = classMatch[2].trim().split(/\s+/);
        if (!classes.includes('icon')) return match;
        const iconClass = classes.find(cls => new RegExp(config.sprite.validate).test(cls));
        if (!iconClass) return match;
        const attrs = match.replace(/class=(["']).*?\1/, '').trim();
        replacements++;
        return `<span class="${classMatch[2]}" ${attrs}><svg class="icon-inner" aria-hidden="true"><use href="/${config.sprite.filename}#${iconClass}"></use></svg></span>`;
      });
      await fs.mkdir(path.dirname(dest), { recursive: true });
      await fs.writeFile(dest, html);
      console.log(`✅ Processed ${file} (${replacements} icons)`);
    }));
    console.log('✅ HTML processing completed');
  } catch (err) {
    console.error(`❌ processHtml failed: ${err.message}`);
    throw err;
  }
}

async function copyToDeploy(config) {
  const distPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.dist);
  const deployPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.deploy);
  try {
    console.log('📋 Deploying to static...');
    if (!await fs.stat(deployPath).catch(() => false)) {
      console.warn(`⚠️ Deploy path not found: ${config.paths.deploy}`);
      return;
    }
    await copyFiles(distPath, deployPath);
    console.log(`✅ Deployed to ${config.paths.deploy}`);
  } catch (err) {
    console.error(`❌ copyToDeploy failed: ${err.message}`);
    throw err;
  }
}

async function extractIconRefs(config) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  try {
    console.log('📋 Extracting icon references...');
    const htmlFiles = globSync(`${srcPath}/**/*.html`).map(f => path.relative(srcPath, f));
    const matches = new Set();
    for (const file of htmlFiles) {
      const html = await fs.readFile(path.join(srcPath, file), 'utf8').catch(() => '');
      if (!html) {
        console.warn(`⚠️ Failed to read ${file}`);
        continue;
      }
      for (const span of html.match(new RegExp(config.sprite.scan, 'g')) || []) {
        const classMatch = span.match(/class="([^"]*)"/);
        if (classMatch) {
          const classes = classMatch[1].split(/\s+/);
          const iconClass = classes.find(cls => new RegExp(config.sprite.validate).test(cls));
          if (iconClass && classes.includes('icon')) matches.add(iconClass);
        }
      }
    }
    const refs = Array.from(matches);
    const iconifyRefs = refs.filter(r => r.startsWith('i-'));
    const localRefs = refs.filter(r => r.startsWith('l-'));
    console.log(`✅ Found ${refs.length} icon refs in ${htmlFiles.length} HTML files:`);
    console.log(`  - Iconify (${iconifyRefs.length}): ${iconifyRefs.join(', ') || 'none'}`);
    console.log(`  - Local (${localRefs.length}): ${localRefs.join(', ') || 'none'}`);
    return refs;
  } catch (err) {
    console.error(`❌ extractIconRefs failed: ${err.message}`);
    throw err;
  }
}

async function loadIconSet(config, pkg) {
  const iconifyPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.node_modules, '@iconify-json');
  try {
    const iconSetPath = path.join(iconifyPath, `${pkg}/icons.json`);
    const raw = await fs.readFile(iconSetPath, 'utf8').catch(() => { throw new Error(`Iconify package not found: ${iconSetPath}`); });
    const json = JSON.parse(raw);
    if (!json.icons) throw new Error(`Invalid icon set: ${pkg}`);
    return json;
  } catch (err) {
    console.error(`❌ loadIconSet failed for ${pkg}: ${err.message}`);
    throw err;
  }
}

function calculateViewBox(svgContent) {
  try {
    const pathRegex = /d="([^"]+)"/g;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    let match;
    while ((match = pathRegex.exec(svgContent)) !== null) {
      const coords = match[1].match(/[\d.-]+/g)?.map(Number) || [];
      for (let i = 0; i < coords.length; i += 2) {
        const x = coords[i];
        const y = coords[i + 1];
        if (!isNaN(x) && !isNaN(y)) {
          minX = Math.min(minX, x);
          minY = Math.min(minY, y);
          maxX = Math.max(maxX, x);
          maxY = Math.max(maxY, y);
        }
      }
    }
    if (minX === Infinity || minY === Infinity || maxX === -Infinity || maxY === -Infinity) return '0 0 24 24';
    const padding = 10;
    const width = maxX - minX;
    const height = maxY - minY;
    return `${minX - padding} ${minY - padding} ${width + 2 * padding} ${height + 2 * padding}`;
  } catch (err) {
    console.error(`❌ calculateViewBox failed: ${err.message}`);
    return '0 0 24 24';
  }
}

async function generateSprite(config, iconClasses) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  const spritePath = path.join(srcPath, config.sprite.filename);
  try {
    console.log('📋 Generating sprite...');
    const symbols = [];
    for (const ref of iconClasses) {
      try {
        if (ref.startsWith('i-')) {
          const [, pkg, name] = ref.match(/^i-([a-z0-9]+)-([a-z0-9]+(?:-[a-z0-9]+)*)$/);
          const iconSet = await loadIconSet(config, pkg);
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
          const svgPath = path.join(srcPath, 'img', `${name}.svg`);
          let svg = await fs.readFile(svgPath, 'utf8').catch(() => { throw new Error(`Local icon not found: ${svgPath}`); });
          svg = svg.replace(/<\?xml[^?]*\?>\s*/, '');
          const optimizedSvg = optimize(svg, config.svgo.sprite).data;
          const viewBox = optimizedSvg.match(/viewBox="([^"]+)"/)?.[1] || calculateViewBox(optimizedSvg);
          const content = optimizedSvg.replace(/^<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '').trim();
          if (!content) throw new Error(`No valid SVG content in ${svgPath}`);
          symbols.push(`<symbol id="${ref}" viewBox="${viewBox}">${content}</symbol>`);
        }
      } catch (err) {
        console.error(`❌ Processing ${ref} failed: ${err.message}`);
      }
    }
    const spriteContent = `<svg xmlns="http://www.w3.org/2000/svg" style="display:none">${symbols.join('')}</svg>`;
    await fs.mkdir(path.dirname(spritePath), { recursive: true });
    await fs.writeFile(spritePath, spriteContent);
    console.log(`✅ Sprite generated: ${config.sprite.filename} (${symbols.length} symbols)`);
  } catch (err) {
    console.error(`❌ generateSprite failed: ${err.message}`);
    throw err;
  }
}

async function validateSprite(config) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  const spritePath = path.join(srcPath, config.sprite.filename);
  const indexPath = config.paths.index ? path.join(srcPath, config.paths.index) : null;
  try {
    console.log('📋 Validating sprite...');
    if (indexPath && !await fs.stat(indexPath).catch(() => false)) {
      throw new Error(`index.html not found at ${indexPath}`);
    }
    const iconClasses = await extractIconRefs(config);
    const spriteContent = await fs.readFile(spritePath, 'utf8').catch(() => '');
    const symbolIds = new Set([...spriteContent.matchAll(new RegExp(config.sprite.symbol, 'g'))].map(m => m[1]));
    const missingIcons = iconClasses.filter(id => !symbolIds.has(id));
    console.log(`✅ Sprite has ${symbolIds.size} symbols: ${[...symbolIds].join(', ') || 'none'}`);
    if (missingIcons.length || !spriteContent) {
      console.warn(`⚠️ Sprite issues: ${missingIcons.length} missing`);
      if (missingIcons.length) console.warn(`⚠️ Missing in sprite.svg: ${missingIcons.join(', ')}`);
      await generateSprite(config, iconClasses);
    } else {
      console.log('✅ Sprite validation passed');
    }
  } catch (err) {
    console.error(`❌ validateSprite failed: ${err.message}`);
    throw err;
  }
}

async function watch(config) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  try {
    console.log('👀 Watching for changes...');
    chokidar.watch([`${srcPath}/**/*.{js,css,html,ico,png,jpg,jpeg,gif}`], { ignoreInitial: true })
      .on('all', async (event, file) => {
        console.log(`🔄 Detected ${event}: ${path.relative(srcPath, file)}`);
        try {
          if (file.endsWith('.css')) await buildCss(config);
          if (file.endsWith('.js')) await buildJs(config);
          if (file.endsWith('.html')) await processHtml(config);
          if (globSync(`${srcPath}/**/*.{ico,png,jpg,jpeg,gif}`).map(f => path.relative(srcPath, f)).includes(path.relative(srcPath, file))) await copyStatic(config);
          await validateSprite(config);
          console.log('✅ Incremental build completed');
        } catch (err) {
          console.error(`❌ Incremental build failed: ${err.message}`);
        }
      });
  } catch (err) {
    console.error(`❌ watch failed: ${err.message}`);
    throw err;
  }
}

export async function cleanLocalSvgs() {
  const config = await resolveConfig();
  const imgPath = path.join(config.paths.srcPath, 'img');
  try {
    console.log('📋 Cleaning local SVGs...');
    const files = (await fs.readdir(imgPath).catch(() => [])).filter(f => f.endsWith('.svg'));
    if (!files.length) return console.log('ℹ️ No SVGs found in src/img/');
    for (const file of files) {
      const filePath = path.join(imgPath, file);
      let svg = await fs.readFile(filePath, 'utf8').replace(/<\?xml[^?]*\?>\s*/, '').replace(/<!DOCTYPE[^>]*>\s*/, '');
      const icon = new SVG(svg);
      cleanupSVG(icon);
      parseColors(icon, { defaultColor: 'currentColor', callback: (_, colorStr) => colorStr === 'none' ? colorStr : 'currentColor' });
      const optimized = optimize(icon.toMinifiedString(), config.svgo.clean);
      await fs.writeFile(filePath, optimized.data);
      console.log(`✅ Cleaned ${file}`);
    }
    console.log('✅ SVG cleaning completed');
  } catch (err) {
    console.error(`❌ cleanLocalSvgs failed: ${err.message}`);
    throw err;
  }
}

export async function build({ prod, watch, deploy } = {}) {
  const config = await resolveConfig({ prod, watch, deploy });
  try {
    console.log(`📋 Starting build... prod: ${config.prod}, watch: ${config.watch}, deploy: ${config.deploy}`);
    if (config.deploy) return await copyToDeploy(config);
    await cleanDist(config);
    await validateSprite(config);
    await copyStatic(config);
    await buildCss(config);
    await buildJs(config);
    await processHtml(config);
    console.log('✅ Build completed');
    if (config.watch) await watch(config);
  } catch (err) {
    console.error(`❌ build failed: ${err.message}`);
    console.error(err.stack);
    process.exit(1);
  }
}

export async function buildProd() { await build({ prod: true }); }
export async function buildWatch() { await build({ watch: true }); }
export async function buildDeploy() { await build({ deploy: true }); }

// Run
build();