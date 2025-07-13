import { cleanupSVG, parseColors, runSVGO, SVG } from "@iconify/tools";
import { getIconData, iconToSVG } from "@iconify/utils";
import tailwindcss from "@tailwindcss/postcss";
import autoprefixer from "autoprefixer";
import * as cheerio from "cheerio";
import chokidar from "chokidar";
import cssnano from "cssnano";
import esbuild from "esbuild";
import fs from "fs/promises";
import { globSync } from "glob";
import path from "path";
import postcss from "postcss";
import { optimize } from "svgo";
import { fileURLToPath } from "url";

// Utility to centralize path resolution
const resolvePath = (base, ...parts) => path.resolve(base, ...parts);

// Utility to check if a file matches a glob pattern
const matchesGlob = (file, pattern, cwd) => {
  const relative = path.relative(cwd, file);
  return globSync(pattern, { cwd }).includes(relative);
};

export async function build(config) {
  try {
    console.log(`📋 Building ... [prod: ${config.prod}]`);
    await initAlpineJs(config);
    await cleanDist(config);
    await validateSprite(config);
    await copyStatic(config);
    await processHtml(config);
    await buildCss(config);
    await buildJs(config);
  } catch (err) {
    console.error(`❌ Build failed: ${err.message}\n${err.stack}`);
  }
}

// Global error handlers
process.on("uncaughtException", (err) => {
  console.error(`❌ Uncaught Exception: ${err.message}\n${err.stack}`);
  process.exit(1);
});
process.on("unhandledRejection", (err) => {
  console.error(`❌ Unhandled Rejection: ${err.message}\n${err.stack}`);
  process.exit(1);
});


async function extractIconRefs(config) {
  const htmlConfig = config.getHtmlConfig();
  const spriteConfig = config.getSpriteConfig();
  try {
    console.log("📋 Extracting icon refs...");
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
    console.log(`✅ Found ${matches.size} icon refs`);
    return Array.from(matches);
  } catch (err) {
    throw new Error(`Extract icon refs failed: ${err.message}`);
  }
}

async function validateSprite(config) {
  const spriteConfig = config.getSpriteConfig();
  try {
    console.log("📋 Validating sprite...");
    const iconClasses = await extractIconRefs(config);
    const spriteContent = await fs.readFile(spriteConfig.output, "utf8").catch(() => "");
    const symbolIds = new Set(
      [...spriteContent.matchAll(new RegExp(spriteConfig.symbol, "g"))].map(
        (m) => m[1]
      )
    );
    const missing = iconClasses.filter((id) => !symbolIds.has(id));
    if (missing.length || !spriteContent) {
      console.warn(`⚠️ Sprite outdated: ${missing.length} missing icons`);
      await generateSprite(config, iconClasses);
    } else {
      console.log(`✅ Sprite valid: ${symbolIds.size} symbols`);
    }
  } catch (err) {
    throw new Error(`Sprite validation failed: ${err.message}`);
  }
}

async function copyStatic(config) {
  const distPath = config.getDistPath();
  const spriteConfig = config.getSpriteConfig();
  try {
    const staticFiles = config.inputs.static.map((f) => ({
      src: resolvePath(config.getSrcPath(), f),
      dest: resolvePath(distPath, f),
    }));
    await Promise.all([
      ...staticFiles.map(({ src, dest }) => copyFiles(src, dest)),
      copyFiles(
        spriteConfig.output,
        resolvePath(distPath, spriteConfig.filename)
      ),
    ]);
    console.log("✅ Static files copied");
  } catch (err) {
    throw new Error(`Copy static failed: ${err.message}`);
  }
}

async function processHtml(config) {
  const htmlConfig = config.getHtmlConfig();
  const distPath = config.getDistPath();
  const spriteConfig = config.getSpriteConfig();
  const componentsPath = config.getComponentsPath();
  try {
    console.log("📋 Processing HTML...");
    await Promise.all(
      htmlConfig.files.map(async (src) => {
        const dest = resolvePath(
          distPath,
          path.relative(config.getSrcPath(), src)
        );
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
            const match = comment.match(
              /^\s*inject\[(components\/[^[\]]+\.html)\]\s*$/
            );
            if (match) {
              const componentFile = match[1].replace("components/", "");
              const componentPath = resolvePath(componentsPath, componentFile);
              importPromises.push(
                fs
                  .readFile(componentPath, "utf8")
                  .then((componentHtml) => {
                    if (!componentHtml.trim()) {
                      console.warn(`⚠️ Component ${match[1]} is empty`);
                      return;
                    }
                    console.log(
                      `🔍 Injecting ${match[1]}: ${componentHtml.length} bytes`
                    );
                    $(this).replaceWith(componentHtml);
                    imports++;
                  })
                  .catch((err) => {
                    console.warn(
                      `⚠️ Failed to inject ${match[1]}: ${err.message}`
                    );
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
        console.log(
          `✅ Processed ${path.basename(src)} ` + // Explicit space
            `(${replacements} icons, ${imports} imports)` // Explicit space before opening parenthesis
        );
      })
    );
    console.log("✅ HTML done");
  } catch (err) {
    throw new Error(`Process HTML failed: ${err.message}`);
  }
}

async function buildCss(config) {
  const cssConfig = config.getCssConfig();
  try {
    if (!cssConfig.files.length) {
      console.warn("⚠️ No CSS files found");
      return;
    }
    const processor = postcss([
      tailwindcss(cssConfig.tailwindcss),
      autoprefixer,
      ...(config.prod ? [cssnano({ preset: "default" })] : []),
    ]);
    const cssContent = await Promise.all(
      cssConfig.files.map((f) => fs.readFile(f, "utf8"))
    );
    const result = await processor.process(cssContent.join("\n"), {
      from: cssConfig.files[0],
      to: cssConfig.output,
    });
    await fs.mkdir(path.dirname(cssConfig.output), { recursive: true });
    await fs.writeFile(cssConfig.output, result.css, "utf8");
    if (result.map)
      await fs.writeFile(
        `${cssConfig.output}.map`,
        result.map.toString(),
        "utf8"
      );
    console.log(`✅ CSS compiled to ${path.basename(cssConfig.output)}`);
  } catch (err) {
    throw new Error(`Build CSS failed: ${err.message}`);
  }
}

async function buildJs(config) {
  const jsConfig = await config.getJsConfig();
  try {
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
  } catch (err) {
    throw new Error(`Build JS failed: ${err.message}`);
  }
}

async function copyToDeploy(config) {
  const distPath = config.getDistPath();
  const deployPath = resolvePath(
    path.dirname(fileURLToPath(import.meta.url)),
    config.paths.deploy
  );
  try {
    const files = globSync("**/*", { cwd: distPath, nodir: true }).map((f) => ({
      src: resolvePath(distPath, f),
      dest: resolvePath(deployPath, f),
    }));
    await Promise.all(files.map(({ src, dest }) => copyFiles(src, dest)));
    console.log(`✅ Deployed to ${config.paths.deploy}`);
  } catch (err) {
    throw new Error(`Deploy failed: ${err.message}`);
  }
}

async function buildByFileType(config, file) {
  const srcPath = config.getSrcPath();
  try {
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
      matchesGlob(file, pattern, srcPath)
    );
    if (!matchedType) {
      console.log(`⚠️ No build tasks for ${path.relative(srcPath, file)}`);
      return;
    }

    console.log(
      `🔄 Building ${matchedType.type} for ${path.relative(srcPath, file)}`
    );
    for (const task of matchedType.tasks) {
      if (task) await task(config);
    }
    if (config.deploy) await copyToDeploy(config);
    console.log("✅ Incremental build done");
  } catch (err) {
    console.error(`❌ Build failed for ${file}: ${err.message}`);
  }
}

export async function watch(config) {
  const srcPath = config.getSrcPath();
  try {
    console.log("👀 Watching for changes...");
    const watcher = chokidar.watch(srcPath, { ignoreInitial: true });
    watcher.on("all", async (event, file) => {
      console.log(`🔄 [${event}] ${path.relative(srcPath, file)}`);
      await buildByFileType(config, file);
    });
  } catch (err) {
    throw new Error(`Watch failed: ${err.message}`);
  }
}

async function copyFiles(src, dest) {
  try {
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.copyFile(src, dest);
    console.log(`✅ Copied ${path.basename(dest)}`);
  } catch (err) {
    console.warn(`⚠️ Copy failed for ${src}: ${err.message}`);
  }
}

async function initAlpineJs(config) {
  if (!config.paths?.node_modules) {
    throw new Error("config.paths.node_modules is not defined in config.json");
  }
  if (!config.js?.alpine?.dev_source || !config.js?.alpine?.minified_source) {
    throw new Error(
      "config.js.alpine.dev_source or config.js.alpine.minified_source is not defined in config.json"
    );
  }
  const nodeModulesPath = resolvePath(
    path.dirname(fileURLToPath(import.meta.url)),
    config.paths.node_modules
  );
  const alpineSrc = resolvePath(nodeModulesPath, config.js.alpine.dev_source);
  const alpineMinSrc = resolvePath(
    nodeModulesPath,
    config.js.alpine.minified_source
  );
  const version = config.js.alpineVersion;
  const alpineDest = resolvePath(config.getSrcPath(), `alpine-${version}.js`);
  const alpineMinDest = resolvePath(
    config.getSrcPath(),
    `alpine.min-${version}.js`
  );
  try {
    await copyFiles(alpineSrc, alpineDest);
    await copyFiles(alpineMinSrc, alpineMinDest);
    console.log("✅ Alpine.js initialized");
  } catch (err) {
    throw new Error(`Init Alpine failed: ${err.message}`);
  }
}

async function cleanDist(config) {
  const distPath = config.getDistPath();
  try {
    await fs.rm(distPath, { recursive: true, force: true });
    await fs.mkdir(distPath, { recursive: true });
    console.log("✅ dist contents deleted");
  } catch (err) {
    throw new Error(`Clean dist failed: ${err.message}`);
  }
}

async function generateSprite(config, iconClasses) {
  const spriteConfig = config.getSpriteConfig();
  try {
    const symbols = [];
    for (const ref of iconClasses) {
      try {
        const parts = ref.split("-");
        if (parts[0] === "i" && parts.length >= 3) {
          const pkg = parts[1];
          const name = parts.slice(2).join("-");
          const iconSet = await loadIconSet(config, pkg);
          const iconData = getIconData(iconSet, name);
          if (!iconData) continue;
          const svgObj = iconToSVG(iconData, { height: "1em", width: "auto" });
          const svg = new SVG(
            `<svg viewBox="${svgObj.attributes.viewBox || "0 0 24 24"}">${
              svgObj.body
            }</svg>`
          );
          cleanupSVG(svg);
          parseColors(svg, { defaultColor: "currentColor" });
          runSVGO(svg);
          symbols.push(
            `<symbol id="${ref}" viewBox="${
              svgObj.attributes.viewBox || "0 0 24 24"
            }">${svg.getBody()}</symbol>`
          );
        } else if (parts[0] === "l" && parts.length >= 2) {
          const name = parts.slice(1).join("-");
          const svgPath = resolvePath(
            config.getSrcPath(),
            "img",
            `${name}.svg`
          );
          let svg = await fs.readFile(svgPath, "utf8").catch(() => "");
          if (!svg) continue;
          svg = svg.replace(/<\?xml[^?]*\?>\s*/, "");
          const optimizedSvg = optimize(svg, config.svgo.sprite).data;
          const viewBox =
            optimizedSvg.match(/viewBox="([^"]+)"/)?.[1] || "0 0 24 24";
          const content = optimizedSvg
            .replace(/^<svg[^>]*>/, "")
            .replace(/<\/svg>\s*$/, "")
            .trim();
          symbols.push(
            `<symbol id="${ref}" viewBox="${viewBox}">${content}</symbol>`
          );
        }
      } catch (err) {
        console.warn(`⚠️ Failed to process icon ${ref}: ${err.message}`);
      }
    }
    const spriteContent = `<svg xmlns="http://www.w3.org/2000/svg" style="display:none">${symbols.join(
      ""
    )}</svg>`;
    await fs.mkdir(path.dirname(spriteConfig.output), { recursive: true });
    await fs.writeFile(spriteConfig.output, spriteContent, "utf8");
    console.log(`✅ Sprite generated: ${symbols.length} symbols`);
  } catch (err) {
    throw new Error(`Generate sprite failed: ${err.message}`);
  }
}

async function loadIconSet(config, pkg) {
  if (!config.paths?.node_modules) {
    throw new Error("config.paths.node_modules is not defined in config.json");
  }
  const iconifyPath = resolvePath(
    path.dirname(fileURLToPath(import.meta.url)),
    config.paths.node_modules,
    "@iconify-json"
  );
  const iconSetPath = resolvePath(iconifyPath, `${pkg}/icons.json`);
  try {
    const raw = await fs.readFile(iconSetPath, "utf8");
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(`Load icon set failed for ${pkg}: ${err.message}`);
  }
}

export async function cleanLocalSvgs(config) {
  const imgPath = resolvePath(config.getSrcPath(), "img");
  try {
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
    console.log("✅ SVG cleaning done");
  } catch (err) {
    throw new Error(`Clean SVGs failed: ${err.message}`);
  }
}

// Entry point
/*
(async () => {
  const config = await resolveConfig();
  if (process.argv.includes("--clean-icons")) {
    await cleanLocalSvgs(config);
  } else if (process.argv.includes("--watch")) {
    await watch(config);
  } else {
    await build(config);
  }
})();
*/

if (typeof module !== "undefined" && !module.parent) {
  throw new Error("This module should be imported and called with a config object by the root build.js");
}
module.exports = { build, watch, cleanLocalSvgs };