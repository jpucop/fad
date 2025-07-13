import { execSync, spawn } from "child_process";
import fs from "fs";
import { globSync } from "glob";
import path from "path";
import yargs from "yargs";
import { hideBin } from "yargs/helpers";
import {
  cleanLocalSvgs,
  build as frontendBuild,
  watch as frontendWatch,
} from "./frontend/build.js";

const baseDir = path.dirname(new URL(import.meta.url).pathname);
const frontendDir = path.join(baseDir, "frontend");
const backendDir = path.join(baseDir, "backend");
const appDir = path.join(backendDir, "app");
const modelDir = path.join(backendDir, "model");

function cleanString(content) {
  // Define invisible characters to remove
  const invisibleChars = [
    /\uFEFF/, // BOM
    /\u00A0/, // Non-breaking space
    /\u200B/, // Zero-width space
    /\u200C/, // Zero-width non-joiner
    /\u200D/, // Zero-width joiner
    /\u2028/, // Line separator
    /\u2029/, // Paragraph separator
    /[\u0000-\u001F\u007F]/, // Control characters (C0 controls and DEL)
  ].map((regex) => new RegExp(regex.source, "g"));

  // Remove all invisible characters
  let cleaned = content;
  invisibleChars.forEach((regex) => {
    cleaned = cleaned.replace(regex, "");
  });

  // Restrict to ASCII (U+0000–U+007F), replacing non-ASCII with a space or empty string
  // Use a space to preserve word boundaries, adjust to '' if strict ASCII-only is needed
  cleaned = cleaned.replace(/[^\x00-\x7F]/g, " ");

  return cleaned;
}

// Utility to run shell commands
function runCommand(cmd, opts = {}) {
  try {
    execSync(cmd, { stdio: "inherit", ...opts });
  } catch (e) {
    console.error(`❌ Failed: ${cmd}`);
    process.exit(1);
  }
}

// Load and resolve configuration
async function resolveConfig() {
  console.log("📋 Loading app.config.json...");
  const raw = await fs.promises
    .readFile(path.join(baseDir, "app.config.json"), "utf8")
    .then((content) => cleanString(content))
    .then(JSON.parse);

  const srcPath = path.join(frontendDir, raw.paths.src);

  const inputs = {
    html: globSync(raw.patterns.html, { cwd: srcPath, nodir: true }).map(
      (f) => f
    ),
    css: globSync(raw.patterns.css, { cwd: srcPath, nodir: true }).map(
      (f) => f
    ),
    js: globSync(raw.patterns.js, { cwd: srcPath, nodir: true }).map((f) => f),
    static: globSync(raw.patterns.static, {
      cwd: srcPath,
      nodir: true,
      ignore: "components/**",
    }).map((f) => f),
  };

  const config = {
    ...raw,
    prod: argv.prod,
    watch: argv.watch,
    deploy: argv.deploy,
    inputs,
    srcp: () => srcPath,
    distp: () => path.join(frontendDir, raw.paths.dist),
    componentsp: () => path.join(srcPath, raw.paths.components),
    newCssConfig: () => ({
      files: inputs.css.map((f) => path.join(srcPath, f)),
      output: path.join(frontendDir, raw.paths.dist, raw.css.filename),
      tailwindcss: raw.css.tailwindcss,
    }),
    newHtmlConfig: () => ({
      files: inputs.html.map((f) => path.join(srcPath, f)),
    }),
    newSpriteConfig: () => ({
      filename: raw.sprite.filename,
      output: path.join(srcPath, raw.sprite.filename),
      containerElement: raw.sprite.containerElement,
      containerClass: raw.sprite.containerClass,
      svgTemplate: raw.sprite.svgTemplate,
      symbol: raw.sprite.symbol,
    }),
    svgo: raw.svgo || { sprite: { plugins: [] }, clean: { plugins: [] } },
    newJsConfig: async () => {
      const pkg = JSON.parse(
        cleanString(fs.readFile(path.join(baseDir, "package.json"), "utf8"))
      );
      const alpineVersion =
        pkg.dependencies?.alpinejs ||
        pkg.devDependencies?.alpinejs ||
        "unknown";
      return {
        files: inputs.js
          .filter((f) => !f.includes("alpine-"))
          .map((f) => path.join(srcPath, f)),
        output: path.join(frontendDir, raw.paths.dist, raw.js.filename),
        alpineVersion: alpineVersion,
      };
    },
  };

  console.log(`✅ Config: ${JSON.stringify(config)}`);
  console.log(
    `✅ Loaded: ${inputs.html.length} HTML, ${inputs.css.length} CSS, ${inputs.js.length} JS, ${inputs.static.length} static`
  );
  return config;
}

// Set up backend environment
async function setupBackend() {
  console.log("🔧 Setting up backend...");
  const venv = path.join(baseDir, "venv");
  const cmd =
    process.platform === "win32"
      ? `${venv}\\Scripts\\activate.bat && pip install -r ${baseDir}/requirements.txt`
      : `source ${venv}/bin/activate && pip install -r ${baseDir}/requirements.txt`;
  runCommand(cmd, { shell: true });
  console.log("✅ Backend ready");
}

// Build frontend
async function buildFrontend(isProd = false) {
  console.log(`🏗️ Building frontend${isProd ? " (prod)" : ""}...`);
  process.env.NODE_ENV = isProd ? "production" : "development";
  const config = await resolveConfig();
  config.prod = isProd;
  await frontendBuild(config);
  console.log("✅ Frontend done");
}

// Run development server
async function runDevServer(config) {
  console.log("🚀 Starting dev server...");
  const pids = [];

  console.log("👀 Watching frontend...");
  await frontendWatch(config);

  console.log("👀 Watching model...");
  const modelWatch = spawn(
    "watchfiles",
    [
      "--filter",
      "*.{json,py}",
      "python",
      "gen_app_models.py",
      "--mode",
      "all",
      ".",
    ],
    {
      cwd: modelDir,
      stdio: "inherit",
      shell: true,
      detached: true,
    }
  );
  pids.push(modelWatch.pid);

  console.log("🔍 Checking Uvicorn...");
  runCommand('python -c "import uvicorn"', { cwd: appDir });
  console.log("🚀 Starting FastAPI...");
  const backendServer = spawn(
    "uvicorn",
    ["main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
    {
      cwd: appDir,
      stdio: "inherit",
      shell: true,
      detached: true,
    }
  );
  pids.push(backendServer.pid);

  process.on("SIGINT", () => {
    console.log("🛑 Stopping...");
    pids.forEach((pid) => process.kill(-pid));
    process.exit();
  });

  await new Promise(() => {});
}

// Define and type CLI arguments explicitly
const argv = yargs(hideBin(process.argv))
  .option("clean-icons", { type: "boolean", description: "Clean local SVGs" })
  .option("watch", { type: "boolean", description: "Watch for changes" })
  .option("prod", { type: "boolean", description: "Build for production" })
  .option("deploy", { type: "boolean", description: "Deploy the build" })
  .option("run", { type: "boolean", description: "Run dev server" }).argv;

// Main execution
if (new URL(import.meta.url).pathname === process.argv[1]) {
  (async () => {
    await setupBackend();
    const config = await resolveConfig();
    if (argv.cleanIcons) await cleanLocalSvgs(config);
    else if (argv.watch) await frontendWatch(config);
    else if (argv.run) await runDevServer(config);
    else await buildFrontend(argv.prod);
  })().catch((e) => {
    console.error(`❌ Error: ${e.message}`);
    process.exit(1);
  });
}
