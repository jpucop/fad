import { exec } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Optional path resolving, if needed
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const inputFile = './css/styles.css';
const outputFile = './dist/css/styles.css';

if (!fs.existsSync(inputFile)) {
  console.error(`❌ Input file not found: ${inputFile}`);
  process.exit(1);
}

const command = `npx tailwindcss -i ${inputFile} -o ${outputFile}`;

exec(command, (error, stdout, stderr) => {
  if (error) {
    console.error(`❌ Error running Tailwind build: ${error.message}`);
    process.exit(1);
  }
  if (stderr) {
    console.warn(`⚠️ Warnings: ${stderr}`);
  }
  console.log(`✅ Tailwind build complete: ${stdout}`);
});
