/** 
 * @type { import('tailwindcss').Config } 
 */

export default {
  content: [
    './src/**/*.{html,js}', 
    './dist/index.html'
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          primary: '#123456',
          secondary: '#abcdef',
        }
      }
    }
  },
  darkMode: 'class',
}