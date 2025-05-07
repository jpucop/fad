import fs from 'fs';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

const source = resolve(__dirname, '../node_modules/alpinejs/dist/cdn.min.js');
const dest = resolve(__dirname, '../dist/js/alpine.min.js');

if (!fs.existsSync(dest)) {
  fs.mkdirSync(directoryPath);
}

fs.copyFile(source, dest, err => {
  if (err) {
    console.error('failed to copy alpine js:', err);
    process.exit(1);
  }
  console.log('cdn min alpine file copied to js/alpine.min.js');
});
