/** 
 * @type { import('tailwindcss').Config } 
 */

const { addIconSelectors } = require('@iconify/tailwind4');

export default {
  content: [
    './index.html',
    './js/*.js'
  ],
  plugins: [
    addIconSelectors(['mdi', 'logos']), // Include mdi and logos collections
  ],
}