#!/bin/bash

# Name: clean.sh
# Description: Deletes node_modules/, package-lock.json, and/or dist/ dir contents.
# Usage: ./clean.sh [node|dist|all]
# Defaults to 'node' if no argument is provided.

set -e

# Resolve script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Read argument (default to 'node' if not supplied)
TARGET="${1:-node}"

case "$TARGET" in
  node)
    echo "Removing node_modules/ and package-lock.json..."
    rm -rf "$SCRIPT_DIR/node_modules"
    rm -f "$SCRIPT_DIR/package-lock.json"
    ;;

  dist)
    echo "Removing contents of dist/..."
    if [ -d "$SCRIPT_DIR/dist" ]; then
      rm -rf "$SCRIPT_DIR/dist"/*
    else
      echo "No dist/ directory found at $SCRIPT_DIR"
    fi
    ;;

  all)
    echo "Removing node_modules/, package-lock.json, and contents of dist/..."
    rm -rf "$SCRIPT_DIR/node_modules"
    rm -f "$SCRIPT_DIR/package-lock.json"
    if [ -d "$SCRIPT_DIR/dist" ]; then
      rm -rf "$SCRIPT_DIR/dist"/*
    fi
    ;;

  *)
    echo "Invalid argument: $TARGET"
    echo "Usage: $0 [node|dist|all]"
    exit 1
    ;;
esac

echo "Done."
