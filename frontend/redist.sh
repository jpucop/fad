#!/bin/sh
set -eu

# Clean up previous build output
echo "🧹 Cleaning dist/ directory..."
rm -rf dist/

# Ensure dependencies are installed
if [ ! -d node_modules ]; then
  echo "📦 Installing dependencies..."
  npm install
fi

# Build the project
echo "🚀 Running build..."
npm run build
