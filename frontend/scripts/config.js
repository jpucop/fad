import { globSync } from 'glob';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const BUILD_ENV = process.env.env === 'prod' ? 'prod' : 'dev';
const isProduction = BUILD_ENV === 'prod';
const baseDir = path.dirname(fileURLToPath(import.meta.url));
console.log('baseDir:', baseDir);

// Helper to resolve paths relative to baseDir
const resolvePath = (relativePath) => path.resolve(baseDir, relativePath);

// Log resolved src path
const srcPath = resolvePath('../src');
console.log('Resolved src path:', srcPath);

// Detect Windows platform
const isWindows = process.platform === 'win32';
console.log('Running on Windows:', isWindows);

// Dynamically discover source files
const srcFiles = {
  js: globSync(path.join(srcPath, '*.js').replace(/\\/g, '/')).map(file => path.basename(file)),
  css: globSync(path.join(srcPath, '*.css').replace(/\\/g, '/')).map(file => path.basename(file)),
  html: fs.readdirSync(srcPath)
    .filter(file => file.toLowerCase().endsWith('.html'))
    .map(file => path.basename(file)), // Use basename to get clean filenames
  static: globSync(path.join(srcPath, '*.{ico,png,jpg,jpeg,gif}').replace(/\\/g, '/')).map(file => path.basename(file)),
  sprite: 'sprite.svg',
  img: [
    {
      dir: 'img',
      exclude: /\.svg$/, // Exclude SVGs in img directory
    },
  ],
};
console.log('Glob pattern for html (reference only):', path.join(srcPath, '*.html').replace(/\\/g, '/'));
console.log('html sources:', srcFiles.html);
console.log('Raw files in src:', fs.readdirSync(srcPath));
console.log('Resolved HTML paths:', srcFiles.html.map(file => path.join(srcPath, file)));

export const CONFIG = {
  build: {
    env: BUILD_ENV,
    isProduction,
    minify: isProduction,
    sourcemap: !isProduction,
    js: {
      bundleAlpine: true,
      output: 'app.js',
    },
    alpine: {
      output: 'alpine.js',
      dev: {
        filename: 'alpine.js',
        modulePath: 'alpinejs/dist/cdn.js',
      },
      min: {
        filename: 'alpine.min.js',
        modulePath: 'alpinejs/dist/cdn.min.js',
      },
    },
  },
  paths: {
    base: baseDir,
    src: srcPath,
    dist: resolvePath('../dist'),
    backend: resolvePath('../../backend/app/static'),
  },
  src: srcFiles,
  iconConfig: {
    classRegex: /(?:i-[a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*|l-[a-z0-9-]+)(?=\b|$)/,
    validateRegex: /^(i-[a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*|l-[a-z0-9-]+)$/,
    spanRegex: /<span\s+[^>]*class="[^"]*icon[^"]*"[^>]*>/g,
    symbolRegex: /<symbol\s+id="([^"]+)"/g,
  },
};