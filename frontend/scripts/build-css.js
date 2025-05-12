#!/usr/bin/env node
import { execSync } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

// Derive __dirname
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Define input and output paths
const inputFile = path.resolve(__dirname, '../src/css/styles.css');
const outputFile = path.resolve(__dirname, '../dist/css/styles.css');

// Tailwind 4 CSS CLI command
const command = `npx @tailwindcss/cli -i ${inputFile} -o ${outputFile}`;

try {
  console.log('Building Tailwind CSS...');
  const outputDir = path.dirname(outputFile);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }
  execSync(command, { stdio: 'inherit' });
  console.log(`✅ Successfully built CSS: ${outputFile}`);
} catch (error) {
  console.error(`❌ Failed to build CSS: ${error.message}`);
  process.exit(1);
}