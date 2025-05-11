/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/index.html',
    './src/js/*.js',
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

  ]
};
