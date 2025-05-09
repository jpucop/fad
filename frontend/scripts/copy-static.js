import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, '..');
const dist = path.join(root, 'dist');

// Only these paths will be copied
const items = ['favicon.ico', 'img'];

// Ensure dist exists
fs.mkdirSync(dist, { recursive: true });

// Recursive directory copy
function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

// Copy each declared item
for (const item of items) {
  const srcPath = path.join(root, item);
  const destPath = path.join(dist, item);
  const stat = fs.statSync(srcPath);

  if (stat.isDirectory()) {
    copyDir(srcPath, destPath);
  } else {
    fs.copyFileSync(srcPath, destPath);
  }
}

console.log('✅ Static files copied to dist');