import { globSync } from 'glob';
import fs from 'fs/promises';
import path from 'path';
import { cleanupSVG, parseColors, runSVGO, SVG } from '@iconify/tools';
import { getIconData, iconToSVG } from '@iconify/utils';
import { optimize } from 'svgo';
import { fileURLToPath } from 'url';
import chokidar from 'chokidar';
import postcss from 'postcss';
import tailwindcss from '@tailwindcss/postcss'; // Correct PostCSS plugin per docs
import autoprefixer from 'autoprefixer';
import cssnano from 'cssnano';
import esbuild from 'esbuild';

// Entry point
export async function build({ prod, watch, deploy } = {}) {
  const config = await resolveConfig({ prod, watch, deploy });
  try {
    console.log(`📋 Starting build... prod: ${config.prod}, watch: ${config.watch}, deploy: ${config.deploy}`);
    await initAlpineJs(config);
    await cleanDist(config);
    await validateSprite(config);
    await copyStatic(config);
    await buildCss(config);
    await buildJs(config);
    await processHtml(config);
    if (config.deploy) await copyToDeploy(config);
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
export async function cleanIcons() {
  const config = await resolveConfig();
  await cleanLocalSvgs(config);
  console.log('✅ Icon cleaning completed');
}

// Global error handling
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
    const packageJson = await fs.readFile(path.join(baseDir, 'package.json'), 'utf8').then(JSON.parse).catch(() => ({}));
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
      paths: {
        ...rawConfig.paths,
        files: rawConfig.paths.files || {
          css: ['**/*.css'],
          html: ['index.html'],
          js: ['**/*.js'],
        },
      },
      sprite: {
        ...rawConfig.sprite,
        filename: rawConfig.sprite.filename || 'sprite.svg',
      },
      css: {
        ...rawConfig.css,
        filename: rawConfig.css.filename || 'styles.css',
      },
      js: {
        ...rawConfig.js,
        filename: rawConfig.js.filename || 'app.js',
      },
      build: {
        minify: rawConfig.prod || false,
        sourcemap: !rawConfig.prod,
      },
      package: {
        alpineVersion: packageJson.dependencies?.alpinejs || packageJson.devDependencies?.alpinejs,
      },
    };
  } catch (err) {
    console.error(`❌ resolveConfig failed: ${err.message}`);
    throw err;
  }
}

async function initAlpineJs(config) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  const nodeModulesPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.node_modules);
  const alpineSrc = path.join(nodeModulesPath, config.js.alpine.dev_source);
  const alpineMinSrc = path.join(nodeModulesPath, config.js.alpine.minified_source);
  try {
    console.log('📋 Initializing Alpine.js...');
    const nodeAlpinePkg = await fs.readFile(path.join(nodeModulesPath, 'alpinejs/package.json'), 'utf8')
      .then(JSON.parse)
      .catch(() => ({ version: null }));
    const version = nodeAlpinePkg.version || 'unknown';
    const alpineDest = path.join(srcPath, `alpine-${version}.js`);
    const alpineMinDest = path.join(srcPath, `alpine.min-${version}.js`);
    const expectedVersion = config.package.alpineVersion;

    const copyIfNeeded = async (src, dest, type) => {
      const srcExists = await fs.stat(src).catch(() => false);
      const destExists = await fs.stat(dest).catch(() => false);
      if (!srcExists) {
        console.warn(`⚠️ ${type} Alpine.js source not found: ${src}`);
        return;
      }
      if (!destExists || (expectedVersion && nodeAlpinePkg.version !== expectedVersion)) {
        await fs.mkdir(path.dirname(dest), { recursive: true });
        await fs.copyFile(src, dest);
        console.log(`✅ Copied ${type} Alpine.js to ${path.basename(dest)}`);
      }
    };

    await copyIfNeeded(alpineSrc, alpineDest, 'dev');
    await copyIfNeeded(alpineMinSrc, alpineMinDest, 'minified');
    console.log('✅ Alpine.js initialization completed');
  } catch (err) {
    console.error(`❌ initAlpineJs failed: ${err.message}`);
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

async function extractIconRefs(config) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  try {
    console.log('📋 Extracting icon references...');
    const htmlFiles = config.paths.files.html
      .flatMap(pattern => globSync(path.join(srcPath, pattern)))
      .map(f => path.relative(srcPath, f));
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
    console.log(`✅ Found ${matches.size} icon refs in ${htmlFiles.length} HTML files`);
    return Array.from(matches);
  } catch (err) {
    console.error(`❌ extractIconRefs failed: ${err.message}`);
    throw err;
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
  const mainHtmlPath = config.paths.mainHtml ? path.join(srcPath, config.paths.mainHtml) : null;
  try {
    console.log('📋 Validating sprite...');
    if (mainHtmlPath && !await fs.stat(mainHtmlPath).catch(() => false)) {
      throw new Error(`Main HTML file not found at ${mainHtmlPath}`);
    }
    const iconClasses = await extractIconRefs(config);
    const spriteContent = await fs.readFile(spritePath, 'utf8').catch(() => '');
    const symbolIds = new Set([...spriteContent.matchAll(new RegExp(config.sprite.symbol, 'g'))].map(m => m[1]));
    const missingIcons = iconClasses.filter(id => !symbolIds.has(id));
    const unusedIcons = [...symbolIds].filter(id => !iconClasses.includes(id));
    if (missingIcons.length || unusedIcons.length || !spriteContent) {
      console.warn(`⚠️ Sprite issues: ${iconClasses.length} refs in HTML, ${symbolIds.size} symbols in sprite.svg`);
      if (missingIcons.length) console.warn(`⚠️ Missing in sprite.svg: ${missingIcons.length} icons`);
      if (unusedIcons.length) console.warn(`⚠️ Unused in sprite.svg: ${unusedIcons.length} icons`);
      await generateSprite(config, iconClasses);
    } else {
      console.log(`✅ Sprite validation passed: ${iconClasses.length} refs, ${symbolIds.size} symbols`);
    }
  } catch (err) {
    console.error(`❌ validateSprite failed: ${err.message}`);
    throw err;
  }
}

async function copyStatic(config) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  const distPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.dist);
  const spritePath = path.join(srcPath, config.sprite.filename);
  const spriteDistPath = path.join(distPath, config.sprite.filename);
  try {
    console.log('📋 Copying static files...');
    const staticPatterns = ['**/*.{ico,png,jpg,jpeg,gif,webp,avif,woff,woff2,json}'];
    const staticFiles = staticPatterns
      .flatMap(pattern => globSync(path.join(srcPath, pattern)))
      .map(f => path.relative(srcPath, f));
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
  const dest = path.join(distPath, config.css.filename);
  try {
    console.log('📋 Processing CSS files...');
    console.log(`Looking for CSS files in: ${srcPath} with patterns: ${config.paths.files.css.join(', ')}`);
    const cssFiles = config.paths.files.css
      .flatMap(pattern => globSync(pattern, { cwd: srcPath }))
      .map(f => path.join(srcPath, f));
    console.log(`Found CSS files: ${cssFiles.length > 0 ? cssFiles.join(', ') : 'None'}`);
    if (!cssFiles.length) {
      console.warn(`⚠️ No CSS files found for patterns: ${config.paths.files.css.join(', ')}`);
      return;
    }
    const nodeAlpinePkg = await fs.readFile(path.join(path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.node_modules), 'alpinejs/package.json'), 'utf8')
      .then(JSON.parse)
      .catch(() => ({ version: null }));
    const version = nodeAlpinePkg.version || 'unknown';
    const tailwindConfig = {
      content: [
        ...config.paths.files.html.map(p => path.join(srcPath, p)),
        ...config.paths.files.js
          .flatMap(p => globSync(path.join(srcPath, p)))
          .filter(f => ![`alpine-${version}.js`, `alpine.min-${version}.js`].includes(path.basename(f)))
      ],
      darkMode: config.css.tailwindcss.darkMode || 'class',
      theme: config.css.tailwindcss.theme || { extend: {} },
      plugins: config.css.tailwindcss.plugins || [],
    };
    const processor = postcss([
      tailwindcss({ config: tailwindConfig }), // Per TailwindCSS docs
      autoprefixer,
      ...(config.prod ? [cssnano({ preset: 'default' })] : []),
    ]);
    for (const file of cssFiles) {
      const inputCss = await fs.readFile(file, 'utf8');
      const result = await processor.process(inputCss, { from: file, to: dest });
      await fs.mkdir(path.dirname(dest), { recursive: true });
      await fs.writeFile(dest, result.css);
      if (result.map) await fs.writeFile(`${dest}.map`, result.map.toString());
      console.log(`✅ Compiled CSS ${path.relative(srcPath, file)} to ${config.css.filename}`);
    }
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
    const nodeAlpinePkg = await fs.readFile(path.join(nodeModulesPath, 'alpinejs/package.json'), 'utf8')
      .then(JSON.parse)
      .catch(() => ({ version: null }));
    const version = nodeAlpinePkg.version || 'unknown';
    const jsFiles = config.paths.files.js
      .flatMap(pattern => globSync(path.join(srcPath, pattern)))
      .map(f => path.relative(srcPath, f))
      .filter(f => ![`alpine-${version}.js`, `alpine.min-${version}.js`].includes(path.basename(f)));
    const alpineSrc = path.join(srcPath, config.prod ? `alpine.min-${version}.js` : `alpine-${version}.js`);
    const alpineDest = path.join(distPath, config.js.alpine.output);

    // Copy Alpine.js
    if (await fs.stat(alpineSrc).catch(() => false)) {
      await copyFiles(alpineSrc, alpineDest);
    } else {
      console.warn(`⚠️ Alpine.js not found at ${alpineSrc}`);
    }

    // Bundle JS files with esbuild
    const entryPoints = [];
    for (const file of jsFiles) {
      const fullPath = path.join(srcPath, file);
      if (await fs.stat(fullPath).catch(() => false)) {
        entryPoints.push(fullPath);
      }
    }
    if (entryPoints.length === 0) {
      console.warn(`⚠️ No JS files found for bundling; skipping JS build`);
      return;
    }

    const tempEntryPath = path.join(distPath, 'temp-entry.js');
    const imports = entryPoints.map(file => `import "${path.relative(distPath, file).replace(/\\/g, '/')}";`).join('\n');
    await fs.writeFile(tempEntryPath, imports);

    try {
      await esbuild.build({
        entryPoints: [tempEntryPath],
        bundle: true,
        outfile: path.join(distPath, config.js.filename),
        minify: config.prod,
        sourcemap: !config.prod,
        format: 'iife',
        target: 'es2018',
      });
      console.log(`✅ Bundled JS into ${config.js.filename}`);
    } finally {
      if (await fs.stat(tempEntryPath).catch(() => false)) {
        await fs.unlink(tempEntryPath);
      }
    }
    console.log('✅ JS processing completed');
  } catch (err) {
    console.error(`❌ buildJs failed: ${err.message}`);
    throw err;
  }
}

async function processHtml(config) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  const distPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.dist);
  const iconRegex = new RegExp(config.sprite.scan, 'g');
  try {
    console.log('📋 Processing HTML files...');
    const htmlFiles = config.paths.files.html
      .flatMap(pattern => globSync(path.join(srcPath, pattern)))
      .map(f => path.relative(srcPath, f));
    if (!htmlFiles.includes(config.paths.mainHtml)) {
      console.warn(`⚠️ Main HTML file not found: ${config.paths.mainHtml}`);
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
        const attrs = match.replace(/class=(["']).*?\1/, '').replace(/^<span\s*/, '').replace(/>$/, '').trim();
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
    if (!await fs.stat(distPath).catch(() => false)) {
      console.warn(`⚠️ dist path not found: ${distPath}`);
      return;
    }
    if (!await fs.stat(deployPath).catch(() => false)) {
      console.warn(`⚠️ Deploy path not found: ${config.paths.deploy}`);
      return;
    }
    const files = globSync(`${distPath}/**/*`, { nodir: true }).map(f => ({
      src: f,
      dest: path.join(deployPath, path.relative(distPath, f)),
    }));
    await Promise.all(files.map(({ src, dest }) => copyFiles(src, dest)));
    console.log(`✅ Deployed to ${config.paths.deploy}`);
  } catch (err) {
    console.error(`❌ copyToDeploy failed: ${err.message}`);
    throw err;
  }
}

async function watch(config) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  try {
    console.log('👀 Watching for changes...');
    const patterns = [
      ...config.paths.files.css.map(p => path.join(srcPath, p)),
      ...config.paths.files.js.map(p => path.join(srcPath, p)),
      ...config.paths.files.html.map(p => path.join(srcPath, p)),
      path.join(srcPath, '**/*.{ico,png,jpg,jpeg,gif,webp,avif,woff,woff2,json}'),
    ];
    const watcher = chokidar.watch(patterns, { ignoreInitial: true });
    watcher.on('all', async (event, file) => {
      console.log(`🔄 Detected ${event}: ${path.relative(srcPath, file)}`);
      try {
        if (config.paths.files.css.some(p => globSync(path.join(srcPath, p)).includes(file))) {
          await buildCss(config);
        }
        if (config.paths.files.js.some(p => globSync(path.join(srcPath, p)).includes(file))) {
          await buildJs(config);
        }
        if (config.paths.files.html.some(p => globSync(path.join(srcPath, p)).includes(file))) {
          await copyStatic(config);
          await processHtml(config);
        }
        if (globSync(path.join(srcPath, '**/*.{ico,png,jpg,jpeg,gif,webp,avif,woff,woff2,json}')).includes(file)) {
          await copyStatic(config);
        }
        await validateSprite(config);
        if (config.deploy) await copyToDeploy(config);
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

async function copyFiles(src, dest) {
  try {
    if (!(await fs.stat(src).catch(() => false))) {
      console.warn(`⚠️ Source file not found: ${src}`);
      return;
    }
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.copyFile(src, dest);
    console.log(`✅ Copied ${path.basename(dest)}`);
  } catch (err) {
    console.error(`❌ copyFiles failed for ${src}: ${err.message}`);
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

export async function cleanLocalSvgs(config) {
  const srcPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), config.paths.src);
  const imgPath = path.join(srcPath, 'img');
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

// CLI handler
if (process.argv.includes('--clean-icons')) {
  cleanIcons();
} else if (process.argv.includes('--prod')) {
  buildProd();
} else if (process.argv.includes('--watch')) {
  buildWatch();
} else if (process.argv.includes('--deploy')) {
  buildDeploy();
} else {
  build();
}