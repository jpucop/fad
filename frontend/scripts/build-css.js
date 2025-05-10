import { readFileSync, writeFileSync } from 'fs';
import postcss from 'postcss';
import tailwindcss from '@tailwindcss/postcss';

const inputCss = readFileSync('./src/css/styles.css', 'utf8');

const result = await postcss([
  tailwindcss({
    // TODO: verify
    // IMPT: we need to base this on dist'd version of index.html where we assume the requisite icons are injected
    content: [
      './dist/*.html',
      './src/js/*.js'
    ],
    theme: {
      
    },
    corePlugins: {

    },
    plugins: [

    ],
  }),
]).process(inputCss, {
  from: './src/css/styles.css',
  to: './dist/css/styles.css',
});

writeFileSync('./dist/css/styles.css', result.css);
console.log('✅ dist/css/styles.css generated.');
