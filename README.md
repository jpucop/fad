# FAD - FastAPI AWS Dashboard

Financial Applications UCOP group aggregate dashboard widget.

## backend

### scripts for handy

```sh

concat_json_files() {
  local output_file="$1"
  local search_dir="${2:-.}"  # Default to current directory if not specified
  
  # Clear output file if it exists, or create new
  : > "$output_file"
  
  # Find all .json files and process them
  find "$search_dir" -type f -name "*.json" | while read -r json_file; do
    # Append filename as header
    echo "=== $json_file ===" >> "$output_file"
    # Append file contents
    cat "$json_file" >> "$output_file"
    # Add newline separator
    echo "" >> "$output_file"
  done
}

# deps by pip
pip freeze > requirements.txt
pip-compile requirements.in
pip-compile requirements-test.in

ptree() { 
  tree -I "venv|.git|.gitignore|.gitmodules"
}

```

### pydantic - generate models for app

By convention, have a **generate.py** file that creates all pydantic model definitions for the runtime of this web app 
models/init/ 1st level sub-dirs are to be the org and group business wise isolated in their model structures.

## frontend

## AWS Tags

**UCOP FinApps Group:**
- ucop:group FinApps
- ucop:application fad
- ucop:environment dev
- ucop:createdBy jkirton@ucop.edu

## FinApps AWS Accounts List

```sh
[default]
region = us-west-2
output = json
# finapps-dev
[872008829419_rw]
# finapps-prod
[836626524524_rw]
# fis-dev
[999860890886_rw]
# fis-prod
[702425941516_rw]
# fdw-dev
[613074250484_rw]
# fdw-prod
[280181752709_rw]
# mf-dev
[627602613099_rw]
# mf-prod
[261032852138_rw]
# ppers-poc
[586982855061_full]
# ppersdev
[030333339593_rw]
# ppersprod
[503759735250_rw]
# ucop-setdev
[469462193597_rw]
```
