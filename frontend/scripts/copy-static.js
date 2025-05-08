import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const root = path.join(__dirname, '..');
const dist = path.join(root, 'dist');

// Files to copy
const files = ['index.html', 'js/fad.js'];
const dirs = ['img'];

// Ensure dist exists
fs.mkdirSync(dist, { recursive: true });

// Copy individual files
for (const file of files) {
  const src = path.join(root, file);
  const dest = path.join(dist, file);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
}

// Copy directories
function copyDir(srcDir, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  for (const entry of fs.readdirSync(srcDir, { withFileTypes: true })) {
    const srcPath = path.join(srcDir, entry.name);
    const destPath = path.join(destDir, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

for (const dir of dirs) {
  copyDir(path.join(root, dir), path.join(dist, dir));
}

console.log('Static files copied to dist/.');
