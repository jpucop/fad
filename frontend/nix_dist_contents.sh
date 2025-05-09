#!/bin/sh
set -eu

# rm all dist/ contents
echo "🧹 Cleaning dist/ directory..."
rm -rf dist/

# install
if [ ! -d node_modules ]; then
  echo "📦 Installing dependencies..."
  npm install
fi

# build
# echo "🚀 Running build..."
# npm run build
