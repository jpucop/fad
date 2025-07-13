const { execSync, spawn } = require("child_process");
const path = require("path");
const { config: dotenvConfig } = require("dotenv");
dotenvConfig(); // Load .env for backend settings

const fs = require("fs");
const { build: frontendBuild, watch: frontendWatch } = require("./frontend/build.js");

const baseDir = __dirname;
const frontendDir = path.join(baseDir, "frontend");
const backendDir = path.join(baseDir, "backend");
const appDir = path.join(backendDir, "app");
const modelDir = path.join(backendDir, "model");

function runCommand(command, options = {}) {
  try {
    execSync(command, { stdio: "inherit", ...options });
  } catch (error) {
    console.error(`❌ Command failed: ${command}`);
    process.exit(1);
  }
}

async function resolveConfig() {
  const baseDir = path.dirname(fileURLToPath(import.meta.url));
  try {
    console.log("📋 Loading app.config.json...");
    const rawConfigContent = await fs
      .readFile(path.join(baseDir, "app.config.json"), "utf8")
      .then(content => cleanString(content))
      .then(JSON.parse);
    const packageJsonContent = await fs
      .readFile(path.join(baseDir, "package.json"), "utf8")
      .then(content => cleanString(content))
      .then(JSON.parse)
      .catch(() => ({}));
    const srcPath = path.join(frontendDir, rawConfigContent.paths.src);

    const inputs = {
      html: globSync(rawConfigContent.patterns.html, {
        cwd: srcPath,
        nodir: true,
      }).map((f) => f),
      css: globSync(rawConfigContent.patterns.css, { cwd: srcPath, nodir: true }).map(
        (f) => f
      ),
      js: globSync(rawConfigContent.patterns.js, { cwd: srcPath, nodir: true }).map(
        (f) => f
      ),
      static: globSync(rawConfigContent.patterns.static, {
        cwd: srcPath,
        nodir: true,
        ignore: "components/**",
      }).map((f) => f),
    };

    const config = {
      ...rawConfigContent,
      prod: process.argv.includes("--prod"),
      watch: process.argv.includes("--watch"),
      deploy: process.argv.includes("--deploy"),
      inputs,
      js: {
        ...rawConfigContent.js,
        alpineVersion:
          packageJsonContent.dependencies?.alpinejs ||
          packageJsonContent.devDependencies?.alpinejs ||
          "unknown",
      },
      getSrcPath: () => srcPath,
      getDistPath: () => path.join(frontendDir, rawConfigContent.paths.dist),
      getComponentsPath: () => path.join(srcPath, rawConfigContent.paths.components),
      getCssConfig: () => ({
        files: inputs.css.map((f) => path.join(srcPath, f)),
        output: path.join(frontendDir, rawConfigContent.paths.dist, rawConfigContent.css.filename),
        tailwindcss: rawConfigContent.css.tailwindcss,
      }),
      getJsConfig: async () => {
        const packageJsonRaw = stripBOM(
          await fs.readFile(path.join(baseDir, "package.json"), "utf8")
        );
        console.log("Raw package.json content (BOM stripped):", packageJsonRaw);
        const packageJson = JSON.parse(packageJsonRaw);
        return {
          alpineVersion:
            packageJson.dependencies?.alpinejs ||
            packageJson.devDependencies?.alpinejs ||
            "unknown",
          files: inputs.js
            .filter((f) => !f.includes("alpine-") && !f.includes("alpine.min-"))
            .map((f) => path.join(srcPath, f)),
          output: path.join(frontendDir, rawConfigContent.paths.dist, rawConfigContent.js.filename),
        };
      },
      getHtmlConfig: () => ({
        files: inputs.html.map((f) => path.join(srcPath, f)),
      }),
      getSpriteConfig: () => ({
        filename: rawConfigContent.sprite.filename,
        output: path.join(srcPath, rawConfigContent.sprite.filename),
        containerElement: rawConfigContent.sprite.containerElement,
        containerClass: rawConfigContent.sprite.containerClass,
        svgTemplate: rawConfigContent.sprite.svgTemplate,
        symbol: rawConfigContent.sprite.symbol,
      }),
      svgo: {
        sprite: {
          plugins: [
            { name: "removeDimensions" },
            { name: "removeAttrs", params: { attrs: ["fill"] } },
            { name: "convertTransform" },
            { name: "cleanupNumericValues", params: { floatPrecision: 0 } },
            { name: "removeUselessStrokeAndFill" },
            { name: "mergePaths" },
            { name: "removeXMLNS" },
          ],
        },
        clean: {
          plugins: [
            "preset-default",
            { name: "removeViewBox", active: false },
            { name: "cleanupNumericValues", params: { floatPrecision: 3 } },
          ],
        },
      },
    };

    console.log(
      `✅ Config loaded: ${inputs.html.length} HTML, ${inputs.css.length} CSS, ${inputs.js.length} JS, ${inputs.static.length} static`
    );
    return config;
  } catch (err) {
    throw new Error(`Failed to load config: ${err.message}`);
  }
}

function stripBOM(content) {
  return content.replace(/^\uFEFF/, "");
}

function cleanString(content) {
  const invisibleChars = [
    /\uFEFF/g, /\u00A0/g, /\u200B/g, /\u200C/g, /\u200D/g, /\u2028/g, /\u2029/g,
    /[\u0000-\u001F\u007F]/g,
  ];
  let cleaned = content;
  invisibleChars.forEach(regex => {
    cleaned = cleaned.replace(regex, '');
  });
  cleaned = cleaned.replace(/[^\x00-\x7F]/g, ' ');
  return cleaned;
}

async function setupBackend() {
  console.log("Activating backend environment...");
  const venvPath = path.join(baseDir, "venv");
  if (process.platform === "win32") {
    runCommand(`${venvPath}\\Scripts\\activate.bat && pip install -r ${backendDir}/requirements.txt`, { shell: true });
  } else {
    runCommand(`source ${venvPath}/bin/activate && pip install -r ${backendDir}/requirements.txt`, { shell: true });
  }
  console.log("✅ Backend dependencies installed");
}

async function buildFrontend(isProd = false) {
  console.log(`Building frontend${isProd ? " (production)" : ""}...`);
  process.env.NODE_ENV = isProd ? "production" : "development";
  const config = await resolveConfig();
  config.prod = isProd; // Override prod flag if needed
  await frontendBuild(config);
  console.log("✅ Frontend built");
}

async function validateAssets() {
  console.log("Validating app static web files...");
  const staticPath = path.join(appDir, "static");
  if (!fs.existsSync(staticPath) || fs.readdirSync(staticPath).length === 0) {
    console.error("❌ No app static assets found.");
    process.exit(1);
  }
  console.log("Validating app models...");
  const modelsPath = path.join(appDir, "models");
  if (!fs.existsSync(modelsPath) || fs.readdirSync(modelsPath).length === 0) {
    console.error("❌ No app models found.");
    process.exit(1);
  }
  console.log("✅ Assets and models validated");
}

async function runDevServer(options = {}) {
  console.log("Starting development server...");
  const pids = [];

  if (options.watch) {
    console.log("👀 Starting frontend watch mode...");
    const config = await resolveConfig();
    await frontendWatch(config); // Honor frontend/build.js:watch
  } else {
    // Fallback to npm watch if watch not explicitly requested
    console.log("Starting frontend watch via npm...");
    const frontendWatchProcess = spawn("npm", ["run", "watch"], { cwd: frontendDir, stdio: "inherit", detached: true });
    pids.push(frontendWatchProcess.pid);
  }

  // Start model watch with gen_app_models.py
  console.log("Starting model watch...");
  const modelWatch = spawn("watchfiles", ["--filter", "*.{json,py}", "python", "gen_app_models.py", "--mode", "all", "."], {
    cwd: modelDir,
    stdio: "inherit",
    shell: true,
    detached: true,
  });
  pids.push(modelWatch.pid);

  // Verify Uvicorn and start FastAPI
  console.log("Verifying Uvicorn installation...");
  runCommand("python -c \"import uvicorn\"", { cwd: appDir });
  console.log("Starting FastAPI server...");
  const backendServer = spawn("uvicorn", ["main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"], {
    cwd: appDir,
    stdio: "inherit",
    shell: true,
    detached: true,
  });
  pids.push(backendServer.pid);

  process.on("SIGINT", () => {
    console.log("Stopping processes...");
    pids.forEach((pid) => process.kill(-pid, "SIGTERM"));
    process.exit();
  });

  if (!options.watch) {
    await new Promise(() => {});
  }
}

if (require.main === module) {
  const args = process.argv.slice(2);
  if (args[0] === "build") {
    setupBackend().then(() => buildFrontend(args.includes("--prod")));
  } else if (args[0] === "run") {
    setupBackend().then(() => {
      validateAssets().then(() => runDevServer({ watch: args.includes("--watch") }));
    });
  } else {
    console.log("Usage: node build.js [build|run] [--prod] [--watch]");
    process.exit(1);
  }
}