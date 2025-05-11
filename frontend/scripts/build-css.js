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
      './src/js/*.js'
    ],
    darkMode: 'class',
    theme: {
      extend: {
        colors: {
          primary: '#6ba1b7', // Muted cyan-blue (baseline)
          secondary: '#00A3E0', // UC Blue
          accent: '#FFC107', // UC Gold
          warning: '#E57373', // Soft red
          neutral: {
            light: '#F5F6F5', // Off-white
            mid: '#A8B1A6', // Light gray
            dark: '#333333', // Dark gray
          },
        },
      },
    },
    plugins: []
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