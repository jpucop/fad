import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const inputFile = path.join(__dirname, '../css/styles.css');
const outputFile = path.join(__dirname, '../dist/css/styles.css');

if (!fs.existsSync(inputFile)) {
  console.error(`❌ Input file not found: ${inputFile}`);
  process.exit(1);
}

try {
  fs.mkdirSync(path.dirname(outputFile), { recursive: true });
  execSync(`npx tailwindcss -i "${inputFile}" -o "${outputFile}" `, { stdio: 'inherit' });
  console.log(`✅ Tailwind build complete: ${outputFile}`);
} catch (error) {
  console.error(`❌ Error running Tailwind build: ${error.message}`);
  process.exit(1);
}
