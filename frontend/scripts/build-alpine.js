import fs from 'fs';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
console.log("__dirname: " + __dirname);

const source = resolve(__dirname, '../node_modules/alpinejs/dist/cdn.min.js');
const distDir = resolve(__dirname, '../dist/js');
const dest = resolve(__dirname, distDir, 'alpine.min.js');

if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir);
}

fs.copyFile(source, dest, err => {
  if (err) {
    console.error('failed to copy minified alpine js to dist/js', err);
    process.exit(1);
  }
  console.log('created minified dist/js/alpine.min.js');
});
