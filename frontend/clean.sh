#!/bin/sh
set -e

rm -rf node_modules package-lock.json
npm install
npx tailwindcss --version              # should work
npx iconify --help                     # should work
npm run build                          # should compile CSS and icons
