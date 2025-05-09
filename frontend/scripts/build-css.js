import { readFileSync, writeFileSync } from 'fs';
import postcss from 'postcss';
import tailwindcss from '@tailwindcss/postcss';

const inputCss = readFileSync('./css/styles.css', 'utf8');

const result = await postcss([
  tailwindcss({
    content: [
      './index.html', // Add more HTML/JS if needed
      'js/fad.js'
    ],
    theme: {
      
    },
    corePlugins: {},
    plugins: [],
  }),
]).process(inputCss, {
  from: './css/styles.css',
  to: './dist/css/styles.css',
});

writeFileSync('./dist/css/styles.css', result.css);
console.log('✅ dist/css/styles.css generated');
