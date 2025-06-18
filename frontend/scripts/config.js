import { fileURLToPath } from 'url';
import path from 'path';

const BUILD_ENV = process.env.env === 'prod' ? 'prod' : 'dev';
const isProduction = BUILD_ENV === 'prod';

export const CONFIG = {
build: {
    env: BUILD_ENV,
    isProduction,
    minify: isProduction,
    sourcemap: !isProduction,
    alpineOutput: 'alpine.js',
    alpineMinFilename: 'alpine.min.js',
    alpineDevFilename: 'alpine.js',
  },
  paths: {
    dirname: path.dirname(fileURLToPath(import.meta.url)),
    srcDir: '../src',
    distDir: '../dist',
    backendDir: '../../backend/app/static',
    alpineDevModulePath: '../node_modules/alpinejs/dist/cdn.js',
    alpineMinModulePath: '../node_modules/alpinejs/dist/cdn.min.js',
  },
  src: {
    js: ['app.js', 'alpine.js', 'alpine.min.js'],
    css: ['styles.css'],
    html: ['index.html'],
    img: [{ dir: 'img', exclude: /\.svg$/ }],
    sprite: 'sprite.svg',
    static: ['favicon.ico'], // Static files to copy
  },
  iconConfig: {
    classRegex: /(?:i-[a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*|l-[a-z0-9-]+)(?=\b|$)/, // Matches i-mdi-home, l-my-icon
    validateRegex: /^(i-[a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*|l-[a-z0-9-]+)$/, // Validates full icon class
    spanRegex: /<span\s+[^>]*class="[^"]*icon[^"]*"[^>]*>/g, // Matches icon spans
    symbolRegex: /<symbol\s+id="([^"]+)"/g, // Matches symbol IDs in sprite
  },
};