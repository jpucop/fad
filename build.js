import { cleanupSVG, parseColors, runSVGO, SVG } from "@iconify/tools";
import tailwindcss from "@tailwindcss/postcss";
import autoprefixer from "autoprefixer";
import * as cheerio from "cheerio";
import chokidar from "chokidar";
import cssnano from "cssnano";
import * as esbuild from "esbuild";
import { globSync } from "glob";
import { execSync, spawn, spawnSync } from "node:child_process";
import fs from "node:fs/promises";
import path, { dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import postcss from "postcss";
import { optimize } from "svgo";
import yargs from "yargs";
import { hideBin } from "yargs/helpers";

/*───────────────────────────────────────────────────────────*
 *  Globals                                                  *
 *───────────────────────────────────────────────────────────*/
const baseDir = dirname(fileURLToPath(import.meta.url));
const frontendDir = path.join(baseDir, "frontend");
const backendDir = path.join(baseDir, "backend");
const appDir = path.join(backendDir, "app");
const modelDir = path.join(backendDir, "model");

const INVISIBLE_RE =
  /[\p{Cc}\p{Cf}\u00A0\uFEFF\u2028\u2029\u200B\u200C]|\P{ASCII}/gu;

/*───────────────────────────────────────────────────────────*
 *  Error Handlers                                           *
 *───────────────────────────────────────────────────────────*/
process.on("uncaughtException", (err) => {
  console.error(`❌ Uncaught Exception: ${err.message}\n${err.stack}`);
  process.exit(1);
});
process.on("unhandledRejection", (err) => {
  console.error(`❌ Unhandled Rejection: ${err.message}\n${err.stack}`);
  process.exit(1);
});

/*───────────────────────────────────────────────────────────*
 *  Utility Helpers                                          *
 *───────────────────────────────────────────────────────────*/
const cleanString = (s) =>
  typeof s === "string" ? s.normalize("NFC").replace(INVISIBLE_RE, " ") : s;

const runSync = (cmd, opts = {}) => {
  try {
    execSync(cmd, { stdio: "inherit", ...opts });
  } catch {
    console.error(`❌ Command failed: ${cmd}`);
    process.exit(1);
  }
};

const run = (cmd, args, opts = {}) =>
  new Promise((res, rej) => {
    const p = spawn(cmd, args, { stdio: "inherit", ...opts });
    p.on("exit", (c, s) =>
      c === 0 ? res() : rej(new Error(`${cmd} exited ${c ?? `signal ${s}`}`))
    );
    p.on("error", rej);
  });

const resolvePath = (base, ...parts) => path.resolve(base, ...parts);
const matchesGlob = (file, pattern, cwd) =>
  globSync(pattern, { cwd }).includes(path.relative(cwd, file));

// log alias for logging object respecting hierarchy all the way down
const olog = (obj) => {
  console.log("-----");
  console.dir(
    JSON.parse(
      JSON.stringify(obj, (k, v) => (typeof v === 'function' ? '[Function]' : v))
    ),
    { depth: null, colors: true }
  );
  console.log("-----");
};

/*───────────────────────────────────────────────────────────*
 *  Config Resolver                                          *
 *───────────────────────────────────────────────────────────*/
async function resolveConfig(argv) {
  console.log("📋 Reading app.config.json…");

  let raw;
  try {
    raw = JSON.parse(
      cleanString(
        await fs.readFile(path.join(baseDir, "app.config.json"), "utf8")
      )
    );
  } catch (err) {
    throw new Error(`Failed to load app.config.json: ${err.message}`);
  }

  const {
    paths: { src, dist, components, node_modules, deploy },
    patterns,
    css: cssCfg,
    js: jsCfg,
    sprite,
    svgo = { sprite: { plugins: [] }, clean: { plugins: [] } },
  } = raw;

  const srcPath = resolvePath(baseDir, src);
  const distPath = resolvePath(baseDir, dist);
  const componentsPath = resolvePath(baseDir, components);
  const nodeModulesPath = resolvePath(baseDir, node_modules);
  const deployPath = resolvePath(baseDir, deploy);

  const globF = (p, o = {}) => globSync(p, { cwd: srcPath, nodir: true, ...o });

  const inputs = {
    html: globF(patterns.html),
    css: globF(patterns.css),
    js: globF(patterns.js),
    static: globF(patterns.static, { ignore: "components/**" }),
  };

  const rconfig = {
    prod: argv.prod || false,
    watch: argv.watch || false,
    deploy: argv.deploy || false,
    inputs,
    patterns,
    paths: { src, dist, components, node_modules, deploy },
    srcPath,
    distPath,
    componentsPath,
    nodeModulesPath,
    deployPath,

    cssConfig: () => ({
      files: inputs.css.map((f) => resolvePath(srcPath, f)),
      output: resolvePath(distPath, cssCfg.filename),
      tailwindcss: cssCfg.tailwindcss,
    }),
    htmlConfig: () => ({
      files: inputs.html.map((f) => resolvePath(srcPath, f)),
    }),
    spriteConfig: () => ({
      filename: sprite.filename,
      output: resolvePath(srcPath, sprite.filename),
      containerElement: sprite.containerElement,
      containerClass: sprite.containerClass,
      svgTemplate: sprite.svgTemplate,
      symbol: sprite.symbol,
    }),
    jsConfig: async () => {
      const pkgRaw = await fs.readFile(resolvePath(baseDir, "package.json"), "utf8");
      const pkg = JSON.parse(pkgRaw);
      const av = pkg.devDependencies?.alpinejs?.replace("^", "") || "3.14.1";

      const jsc = {
        files: inputs.js
          .filter((f) => !f.startsWith("alpine"))
          .map((f) => resolvePath(srcPath, f)),
        output: resolvePath(distPath, jsCfg.filename),
        alpineVersion: av,
        alpine: jsCfg.alpine
      };
      return jsc;
    },
    svgo
  };

  olog(rconfig);
  return rconfig;
}

/*───────────────────────────────────────────────────────────*
 *  Backend Setup                                            *
 *───────────────────────────────────────────────────────────*/
async function setupBackend() {
  console.log("🔧 Setting up backend venv and requirements.txt install/update..");
  const venvDir = resolvePath(baseDir, "venv");
  const pipPath =
    process.platform === "win32"
      ? resolvePath(venvDir, "Scripts", "pip.exe")
      : resolvePath(venvDir, "bin", "pip");
  const reqTxt = resolvePath(baseDir, "requirements.txt");

  for (const f of [pipPath, reqTxt]) {
    try {
      await fs.access(f);
    } catch {
      throw new Error(`Required file not found: ${path.basename(f)}`);
    }
  }

  const cmd =
    process.platform === "win32"
      ? `${resolvePath(venvDir, "Scripts", "activate.bat")} && pip install -r ${reqTxt}`
      : `source ${resolvePath(venvDir, "bin", "activate")} && pip install -r ${reqTxt}`;
  await run(cmd, [], { shell: true });
  console.log("✅ Backend setup complete");
}

/*───────────────────────────────────────────────────────────*
 *  Frontend Build Helpers                                   *
 *───────────────────────────────────────────────────────────*/
async function copyFiles(src, dest) {
  await fs.mkdir(path.dirname(dest), { recursive: true });
  await fs.copyFile(src, dest);
  console.log(`📄 Copied ${path.basename(dest)}`);
}

async function initAlpineJs(config) {
  const jsConfig = await config.jsConfig();
  const alpineVer = jsConfig.alpineVersion;

  Object.entries(jsConfig.alpine).forEach(([key, relPath]) => {
    const src = resolvePath(config.nodeModulesPath, relPath);
    const name =
      key === "minified_source"
        ? `alpine.min-${alpineVer}.js`
        : `alpine-${alpineVer}.js`;

    copyFiles(src, resolvePath(config.srcPath, name));
  });
}

async function cleanDist(config) {
  await fs.rm(config.distPath, { recursive: true, force: true });
  await fs.mkdir(config.distPath, { recursive: true });
  console.log("🧹 dist directory cleared");
}

async function extractIconRefs(config) {
  const htmlConfig = config.htmlConfig();
  const spriteConfig = config.spriteConfig();
  console.log("📋 Extracting icon references…");
  const matches = new Set();
  for (const file of htmlConfig.files) {
    const html = await fs.readFile(file, "utf8");
    const $ = cheerio.load(html, { decodeEntities: false });
    const selector = `${spriteConfig.containerElement}.${spriteConfig.containerClass}`;
    $(selector).each(function () {
      const classes = $(this).attr("class")?.split(/\s+/) || [];
      const iconIndex = classes.indexOf(spriteConfig.containerClass);
      if (iconIndex !== -1 && iconIndex + 1 < classes.length) {
        const iconClass = classes[iconIndex + 1];
        if (iconClass.startsWith("i-") || iconClass.startsWith("l-")) {
          matches.add(iconClass);
        }
      }
    });
  }
  console.log(`✅ Found ${matches.size} icon references`);
  return Array.from(matches);
}

async function generateSprite(config, iconClasses) {
  const spriteConfig = config.spriteConfig();
  const symbols = [];
  for (const ref of iconClasses) {
    try {
      const parts = ref.split("-");
      if (parts[0] === "i" && parts.length >= 3) {
        const pkg = parts[1];
        const name = parts.slice(2).join("-");
        const iconSet = await loadIconSet(config, pkg);
        const iconData = iconSet.icons[name]; // Simplified; assumes structure
        if (!iconData) continue;
        const svgObj = { body: iconData.body, attributes: { viewBox: "0 0 24 24" } }; // Placeholder
        const svg = new SVG(
          `<svg viewBox="${svgObj.attributes.viewBox}">${svgObj.body}</svg>`
        );
        cleanupSVG(svg);
        parseColors(svg, { defaultColor: "currentColor" });
        runSVGO(svg);
        symbols.push(
          `<symbol id="${ref}" viewBox="${svgObj.attributes.viewBox}">${svg.getBody()}</symbol>`
        );
      } else if (parts[0] === "l" && parts.length >= 2) {
        const name = parts.slice(1).join("-");
        const svgPath = resolvePath(config.srcPath, "img", `${name}.svg`);
        let svg = await fs.readFile(svgPath, "utf8").catch(() => "");
        if (!svg) continue;
        svg = svg.replace(/<\?xml[^?]*\?>\s*/, "");
        const optimizedSvg = optimize(svg, config.svgo.sprite).data;
        const viewBox = optimizedSvg.match(/viewBox="([^"]+)"/)?.[1] || "0 0 24 24";
        const content = optimizedSvg.replace(/^<svg[^>]*>/, "").replace(/<\/svg>\s*$/, "").trim();
        symbols.push(`<symbol id="${ref}" viewBox="${viewBox}">${content}</symbol>`);
      }
    } catch (err) {
      console.warn(`⚠️ Failed to process icon ${ref}: ${err.message}`);
    }
  }
  const spriteContent = `<svg xmlns="http://www.w3.org/2000/svg" style="display:none">${symbols.join("")}</svg>`;
  await fs.mkdir(path.dirname(spriteConfig.output), { recursive: true });
  await fs.writeFile(spriteConfig.output, spriteContent, "utf8");
  console.log(`✅ Sprite generated with ${symbols.length} symbols`);
}

async function loadIconSet(config, pkg) {
  const iconifyPath = resolvePath(config.nodeModulesPath, "@iconify-json");
  const iconSetPath = resolvePath(iconifyPath, `${pkg}`, "icons.json");
  try {
    const raw = await fs.readFile(iconSetPath, "utf8");
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(`Failed to load icon set ${pkg}: ${err.message}`);
  }
}

async function validateSprite(config) {
  const spriteConfig = config.spriteConfig();
  console.log("📋 Validating sprite…");
  const iconClasses = await extractIconRefs(config);
  const spriteContent = await fs.readFile(spriteConfig.output, "utf8").catch(() => "");
  const symbolIds = new Set(
    [...spriteContent.matchAll(new RegExp(spriteConfig.symbol, "g"))].map((m) => m[1])
  );
  const missing = iconClasses.filter((id) => !symbolIds.has(id));
  if (missing.length || !spriteContent) {
    console.warn(`⚠️ Sprite outdated: ${missing.length} icons missing`);
    await generateSprite(config, iconClasses);
  } else {
    console.log(`✅ Sprite valid with ${symbolIds.size} symbols`);
  }
}

async function copyStatic(config) {
  const spriteConfig = config.spriteConfig();
  const staticFiles = config.inputs.static.map((f) => ({
    src: resolvePath(config.srcPath, f),
    dest: resolvePath(config.distPath, f),
  }));
  await Promise.all([
    ...staticFiles.map(({ src, dest }) => copyFiles(src, dest)),
    copyFiles(spriteConfig.output, resolvePath(config.distPath, spriteConfig.filename)),
  ]);
  console.log("✅ Static files copied");
}

async function processHtml(config) {
  const htmlConfig = config.htmlConfig();
  const spriteConfig = config.spriteConfig();
  console.log("📋 Processing HTML…");
  await Promise.all(
    htmlConfig.files.map(async (src) => {
      const dest = resolvePath(config.distPath, path.relative(config.srcPath, src));
      let html = await fs.readFile(src, "utf8");
      const $ = cheerio.load(html, { decodeEntities: false });

      let imports = 0;
      const importPromises = [];
      $("*")
        .contents()
        .filter(function () {
          return this.type === "comment";
        })
        .each(function () {
          const comment = this.data.trim();
          const match = comment.match(/^\s*inject\[(components\/[^[\]]+\.html)\]\s*$/);
          if (match) {
            const componentFile = match[1].replace("components/", "");
            const componentPath = resolvePath(config.componentsPath, componentFile);
            importPromises.push(
              fs.readFile(componentPath, "utf8")
                .then((componentHtml) => {
                  if (!componentHtml.trim()) {
                    console.warn(`⚠️ Component ${match[1]} is empty`);
                    return;
                  }
                  console.log(`🔍 Injecting ${match[1]}: ${componentHtml.length} bytes`);
                  $(this).replaceWith(componentHtml);
                  imports++;
                })
                .catch((err) => {
                  console.warn(`⚠️ Failed to inject ${match[1]}: ${err.message}`);
                })
            );
          }
        });
      await Promise.all(importPromises);

      let replacements = 0;
      const selector = `${spriteConfig.containerElement}.${spriteConfig.containerClass}`;
      $(selector).each(function () {
        const $el = $(this);
        const classes = $el.attr("class")?.split(/\s+/) || [];
        const iconIndex = classes.indexOf(spriteConfig.containerClass);
        if (iconIndex !== -1 && iconIndex + 1 < classes.length) {
          const iconClass = classes[iconIndex + 1];
          if (iconClass.startsWith("i-") || iconClass.startsWith("l-")) {
            const svg = spriteConfig.svgTemplate
              .replace("{filename}", spriteConfig.filename)
              .replace("{iconClass}", iconClass);
            $el.append(svg);
            replacements++;
          }
        }
      });

      html = $.html();
      await fs.mkdir(path.dirname(dest), { recursive: true });
      await fs.writeFile(dest, html, "utf8");
      console.log(`✅ Processed ${path.basename(src)} (${replacements} icons, ${imports} imports)`);
    })
  );
  console.log("✅ HTML processing complete");
}

async function buildCss(config) {
  const { files, output, tailwindcss: twConfig = {} } = config.cssConfig?.() || {};

  if (!files?.length) {
    console.warn("⚠️ No CSS input files found.");
    return;
  }

  try {
    const processor = postcss([
      tailwindcss(twConfig),
      autoprefixer,
      ...(config.prod ? [cssnano({ preset: "default" })] : []),
    ]);

    const cssIn = await Promise.all(files.map((f) => fs.readFile(f, "utf8")));
    const result = await processor.process(cssIn.join("\n"), {
      from: files[0],
      to: output,
      map: { inline: false },
    });

    await fs.mkdir(path.dirname(output), { recursive: true });
    await fs.writeFile(output, result.css, "utf8");

    if (result.map) {
      await fs.writeFile(`${output}.map`, result.map.toString(), "utf8");
    }

    console.log(`✅ CSS compiled to ${path.basename(output)}`);
    return { outDir: path.dirname(output) };
  } catch (err) {
    throw new Error(`❌ Build CSS failed: ${err.message}`);
  }
}

async function buildJs(config) {
  const jsConfig = await config.jsConfig();
  if (!jsConfig.files.length) {
    console.warn("⚠️ No JS files found");
    return;
  }
  await esbuild.build({
    entryPoints: jsConfig.files,
    bundle: true,
    outfile: jsConfig.output,
    minify: config.prod,
    sourcemap: !config.prod,
    format: "iife",
    target: "es2018",
  });
  console.log(`✅ JS bundled to ${path.basename(jsConfig.output)}`);
}

async function copyToDeploy(config) {
  const files = globSync("**/*", { cwd: config.distPath, nodir: true }).map((f) => ({
    src: resolvePath(config.distPath, f),
    dest: resolvePath(config.deployPath, f),
  }));
  await Promise.all(files.map(({ src, dest }) => copyFiles(src, dest)));
  console.log(`✅ Deployed to ${config.paths.deploy}`);
}

async function buildByFileType(config, file) {
  const fileTypes = [
    {
      type: "html",
      pattern: config.patterns.html,
      tasks: [validateSprite, copyStatic, processHtml],
    },
    { type: "css", pattern: config.patterns.css, tasks: [buildCss] },
    {
      type: "js",
      pattern: config.patterns.js,
      tasks: [(file) => (file.includes("alpine-") ? null : buildJs)],
    },
    { type: "static", pattern: config.patterns.static, tasks: [copyStatic] },
  ];

  const matchedType = fileTypes.find(({ pattern }) =>
    matchesGlob(file, pattern, config.srcPath)
  );
  if (!matchedType) {
    console.log(`⚠️ No build tasks for ${path.relative(config.srcPath, file)}`);
    return;
  }

  console.log(`🔄 Building ${matchedType.type} for ${path.relative(config.srcPath, file)}`);
  for (const task of matchedType.tasks) {
    if (task) await task(config);
  }
  if (config.deploy) await copyToDeploy(config);
  console.log("✅ Incremental build complete");
}

async function cleanLocalSvgs(config) {
  const imgPath = resolvePath(config.srcPath, "img");
  const files = (await fs.readdir(imgPath)).filter((f) => f.endsWith(".svg"));
  for (const file of files) {
    const filePath = resolvePath(imgPath, file);
    let svg = await fs.readFile(filePath, "utf8").replace(/<\?xml[^?]*\?>\s*/, "");
    const icon = new SVG(svg);
    cleanupSVG(icon);
    parseColors(icon, { defaultColor: "currentColor" });
    const optimized = optimize(icon.toMinifiedString(), config.svgo.clean);
    await fs.writeFile(filePath, optimized.data, "utf8");
    console.log(`✅ Cleaned ${file}`);
  }
  console.log("✅ SVG cleaning complete");
}

async function frontendBuild(config) {
  console.log(`📋 Building frontend.. [prod: ${config.prod}]`);
  await initAlpineJs(config);
  await cleanDist(config);
  await validateSprite(config);
  await copyStatic(config);
  await processHtml(config);
  await buildCss(config);
  await buildJs(config);
  if (config.deploy) await copyToDeploy(config);
  console.log("✅ Frontend build complete");
}

/*───────────────────────────────────────────────────────────*
 *  Watch & Dev Server                                       *
 *───────────────────────────────────────────────────────────*/
async function frontendWatch(config) {
  const watcher = chokidar.watch(config.srcPath, { ignoreInitial: true });
  watcher.on("all", (_, f) => buildByFileType(config, f));
  console.log("👀 Frontend watcher running");
  return watcher;
}

async function runDevServer(config) {
  const frontendWatcher = await frontendWatch(config);

  const modelWatcher = spawn(
    "watchfiles",
    ["--filter", "*.{json,py}", "python", "gen_app_models.py", "--mode", "all", "."],
    { cwd: modelDir, stdio: "inherit", detached: true }
  );

  const py =
    process.platform === "win32"
      ? resolvePath(baseDir, "venv", "Scripts", "python.exe")
      : resolvePath(baseDir, "venv", "bin", "python");

  spawnSync(py, ["-c", "import uvicorn"], { cwd: appDir, stdio: "inherit" });

  const api = spawn(
    py,
    ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
    { cwd: appDir, stdio: "inherit", detached: true }
  );

  process.on("SIGINT", () => {
    frontendWatcher.close();
    [modelWatcher, api].forEach((p) => {
      try {
        process.kill(-p.pid); // Negative PID to kill process group
      } catch { }
    });
    console.log("🛑 Dev server stopped");
    process.exit(0);
  });

  await new Promise(() => { }); // Keep running
}

/*───────────────────────────────────────────────────────────*
 *  CLI                                                      *
 *───────────────────────────────────────────────────────────*/
yargs(hideBin(process.argv))
  .command("build", "Build the frontend and backend", {}, async (argv) => {
    const config = await resolveConfig(argv);
    await frontendBuild(config);
  })
  .command("watch", "Watch for frontend changes", {}, async (argv) => {
    await setupBackend();
    const config = await resolveConfig(argv);
    await frontendWatch(config);
  })
  .command("run", "Run the development server", {}, async (argv) => {
    await setupBackend();
    const config = await resolveConfig(argv);
    await runDevServer(config);
  })
  .command("clean-icons", "Clean local SVG files", {}, async (argv) => {
    await setupBackend();
    const config = await resolveConfig(argv);
    await cleanLocalSvgs(config);
  })
  .option("prod", { type: "boolean", description: "Production build" })
  .option("deploy", { type: "boolean", description: "Deploy the build" })
  .demandCommand(1, "Please specify a command: build, watch, run, or clean-icons")
  .strict()
  .help()
  .parse();

/*───────────────────────────────────────────────────────────*
 *  Main                                                     *
 *───────────────────────────────────────────────────────────*/
if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  // No default action; yargs handles command requirement
}