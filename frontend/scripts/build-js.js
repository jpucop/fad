import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Config class to encapsulate paths
class Config {
  constructor() {
    this.dirname = path.dirname(fileURLToPath(import.meta.url));
    this.srcDir = path.join(this.dirname, '..', 'src'); // Project src/
    this.distDir = path.join(this.dirname, '..', 'dist', 'js'); // Project dist/js/
    this.nodeModulesDir = path.join(this.dirname, '..', 'node_modules'); // Project node_modules/
    this.alpineSrc = path.join(this.nodeModulesDir, 'alpinejs', 'dist', 'cdn.min.js');
    this.alpineDest = path.join(this.distDir, 'alpine.js');
    this.appSrc = path.join(this.srcDir, 'js', 'app.js');
    this.appDest = path.join(this.distDir, 'app.js');
  }

  // Validate source files
  validate() {
    if (!fs.existsSync(this.alpineSrc)) {
      throw new Error(`❌ Alpine.js source file not found: ${this.alpineSrc}`);
    }
    if (!fs.existsSync(this.appSrc)) {
      throw new Error(`❌ App.js source file not found: ${this.appSrc}`);
    }
  }
}

// Copy files with error handling
function copyFile(src, dest) {
  fs.copyFileSync(src, dest);
  console.log(`✅ Copied ${path.basename(src)} to ${path.relative(path.join(__dirname, '..'), dest)}`);
}

// Main function
function buildJs() {
  try {
    const config = new Config();

    // Create output directory
    fs.mkdirSync(config.distDir, { recursive: true });

    // Validate files
    config.validate();

    // Copy files
    copyFile(config.alpineSrc, config.alpineDest);
    copyFile(config.appSrc, config.appDest);

    console.log('✅ JavaScript build complete: dist/js/');
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}

// Run
buildJs();