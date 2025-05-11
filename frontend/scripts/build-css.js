import tailwindcss from '@tailwindcss/postcss';
import autoprefixer from 'autoprefixer';
import { mkdirSync, readFileSync, writeFileSync } from 'fs';
import path from 'path';
import postcss from 'postcss';

// Create output directory if it doesn't exist
const outputDir = './dist/css';
mkdirSync(outputDir, { recursive: true });

// Read input CSS
const inputCss = readFileSync('./src/css/styles.css', 'utf8');

// Process with PostCSS and Tailwind
const result = await postcss([
  tailwindcss({
    content: [
      './src/index.html',
      './src/js/*.js',
      // Remove './dist/index.html' unless it exists before build
    ],
    darkMode: 'class',
    theme: {
      extend: {
        colors: {
          primary: '#1a56db',
          secondary: '#7e22ce'
        },
      },
    },
    plugins: [
      // Add plugins if needed, e.g.:
      // require('@tailwindcss/forms'),
      // require('@tailwindcss/typography'),
    ],
  }),
  autoprefixer,
]).process(inputCss, {
  from: './src/css/styles.css',
  to: './dist/css/styles.css'
});

// Write result
const outputPath = path.join(outputDir, 'styles.css');
writeFileSync(outputPath, result.css);

console.log('✅ dist/css/styles.css generated.');