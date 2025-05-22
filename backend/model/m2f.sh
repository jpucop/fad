###############################################################################
# dump_json – recursively print every *.json file under a path.
#   • Shows a header "=== path/to/file.json ===" before each file’s contents
#   • Adds a blank line between files for readability
#
#   Usage:  dump_json [DIRECTORY]
#           dump_json           # defaults to "."
#           dump_json /var/log  # any starting directory
###############################################################################
dump_json() {
  local start_dir="${1:-.}"

  if [[ ! -d "$start_dir" ]]; then
    printf 'dump_json: "%s" is not a directory\n' "$start_dir" >&2
    return 1
  fi

  # Use find+xargs with NUL delimiters → robust against weird filenames
  find "$start_dir" -type f -name '*.json' -print0 |
    xargs -0 -n1 sh -c '
      for f; do
        printf "\n=== %s ===\n" "$f"
        cat "$f"
      done
    ' _
}

# If you saved this in a file, source it:
#   source ./json_dump.sh
#
# Then run:
#   dump_json           # from current dir
#   dump_json ~/data    # from specific dir
