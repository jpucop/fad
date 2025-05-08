// scripts/build-js.js
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const root = path.join(__dirname, '..');
const jsDist = path.join(root, 'dist', 'js');

// Ensure output dir exists
fs.mkdirSync(jsDist, { recursive: true });

// File paths
const alpineSrc = path.join(root, 'node_modules', 'alpinejs', 'dist', 'cdn.min.js');
const alpineDest = path.join(jsDist, 'alpine.js');

const fadSrc = path.join(root, 'js', 'fad.js');
const fadDest = path.join(jsDist, 'app.js');

// Copy files
fs.copyFileSync(alpineSrc, alpineDest);
fs.copyFileSync(fadSrc, fadDest);

console.log('✅ Copied alpine.js and app.js to dist/js/');
