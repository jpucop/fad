import tailwindcss from '@tailwindcss/postcss'; // Use the PostCSS plugin
import autoprefixer from 'autoprefixer'; // Explicitly import autoprefixer
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
      './src/js/**/*.js', // Match all JS files
    ],
    darkMode: 'class', // or 'media'
    theme: {
      extend: {
        colors: {
          primary: '#1a56db',
          secondary: '#7e22ce',
        },
      },
    },
    plugins: [],
  }),
  autoprefixer,
]).process(inputCss, {
  from: './src/css/styles.css',
  to: './dist/css/styles.css',
});

// Write result
const outputPath = path.join(outputDir, 'styles.css');
writeFileSync(outputPath, result.css);

console.log('✅ dist/css/styles.css generated.');