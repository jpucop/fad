import { globSync } from 'glob';
import path from 'path';
import { fileURLToPath } from 'url';

const BUILD_ENV = process.env.env === 'prod' ? 'prod' : 'dev';
const isProduction = BUILD_ENV === 'prod';
const baseDir = path.dirname(fileURLToPath(import.meta.url));

// Helper to resolve paths relative to baseDir
const resolvePath = (relativePath) => path.resolve(baseDir, relativePath);

// Dynamically discover source files using glob patterns (top-level only)
const srcFiles = {
  js: globSync(resolvePath('../src/*.js')).map(file => path.relative(resolvePath('../src'), file)),
  css: globSync(resolvePath('../src/*.css')).map(file => path.relative(resolvePath('../src'), file)),
  html: globSync(resolvePath('../src/*.html')).map(file => path.relative(resolvePath('../src'), file)),
  static: globSync(resolvePath('../src/*.{ico,png,jpg,jpeg,gif,webp,avif,woff,woff2,json}')).map(file => path.relative(resolvePath('../src'), file)),
  sprite: 'sprite.svg',
  img: [
    {
      dir: 'img',
      exclude: /\.svg$/, // Exclude SVGs in img directory
    },
  ],
};

export const CONFIG = {
  build: {
    env: BUILD_ENV,
    isProduction,
    minify: isProduction,
    sourcemap: !isProduction,
    js: {
      bundleAlpine: true, // Include alpine.js in app.js bundle by default
      output: 'app.js', // Bundled JS output file
    },
    alpine: {
      output: 'alpine.js', // Separate alpine.js output if not bundled
      dev: {
        filename: 'alpine.js',
        modulePath: 'alpinejs/dist/cdn.js', // Use require.resolve in build.js
      },
      min: {
        filename: 'alpine.min.js',
        modulePath: 'alpinejs/dist/cdn.min.js',
      },
    },
  },
  paths: {
    base: baseDir,
    src: resolvePath('../src'),
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