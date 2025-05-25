dump_json_py() {
  local start_dir="${1:-.}"

  if [[ ! -d "$start_dir" ]]; then
    printf 'dump_json: "%s" is not a directory\n' "$start_dir" >&2
    return 1
  fi

  find "$start_dir" -type f -name '*.json' -print0 |
    xargs -0 -n1 sh -c '
      for f; do
        printf "\n=== %s ===\n" "$f"
        cat "$f"
      done
    ' _

  find "$start_dir" -type f -name '*.py' -print0 |
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
