import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import * as esbuild from 'esbuild';

// Config class to encapsulate paths
class Config {
  constructor() {
    this.dirname = path.dirname(fileURLToPath(import.meta.url));
    this.srcDir = path.join(this.dirname, '..', 'src');
    this.distDir = path.join(this.dirname, '..', 'dist', 'js');
    this.appSrc = path.join(this.srcDir, 'js', 'app.js');
    this.appDest = path.join(this.distDir, 'app.js');
  }

  // Validate source file
  validate() {
    if (!fs.existsSync(this.appSrc)) {
      throw new Error(`❌ App.js source file not found: ${this.appSrc}`);
    }
  }
}

// Main function
async function buildJs() {
  try {
    const config = new Config();

    // Validate source file
    config.validate();

    // Create output directory
    fs.mkdirSync(config.distDir, { recursive: true });

    // Run esbuild
    await esbuild.build({
      entryPoints: [config.appSrc],
      bundle: true,
      minify: true,
      outfile: config.appDest,
      format: 'iife', // For browser compatibility with Alpine.js
      globalName: 'app', // Optional, ensures global scope
      sourcemap: false, // Set to true for debugging
    });

    console.log(`✅ Bundled and minified ${path.basename(config.appSrc)} to ${path.relative(path.join(config.dirname, '..'), config.appDest)}`);
  } catch (error) {
    console.error(`❌ Build failed: ${error.message}`);
    process.exit(1);
  }
}

// Run
buildJs();