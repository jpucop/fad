#!/usr/bin/env python3

"""
Model Generation Script

- Assumes raw JSON files are placed under model/schema/
- Categorizes files by filename prefixes: org_, group_, app
- Excludes specific files: app_snapshot.json, apps.json
- Generates Pydantic models from raw JSON, inferring types
- Outputs models to backend/app/models/{org,group,app}_models.py
- Requires datamodel-code-generator==0.31.2 and Pydantic==2.10.6
- Handles raw JSON with --input-file-type json
"""

import json
import logging
import os
from pathlib import Path
import subprocess
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Define project structure
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCHEMA_DIR = PROJECT_ROOT / "model" / "schema"
APP_MODELS_DIR = PROJECT_ROOT / "backend" / "app" / "models"

# Category mapping for JSON files
CATEGORY_MAP = {
    "org": ["org.json", "org_ucop.json"],
    "group": ["group.json", "group_finapps.json"],
    "app": ["app_main.json", "app_topo.json"],
}

# Files to exclude from processing
EXCLUDE_FILES = {"app_snapshot.json", "apps.json"}

def relpath(path: Path) -> str:
    """Return path relative to project root for logging."""
    return os.path.relpath(path, PROJECT_ROOT)

def collect_files_by_category():
    """Collect JSON files by category, excluding specified files."""
    files_by_category = {cat: [] for cat in CATEGORY_MAP}
    for json_file in sorted(SCHEMA_DIR.glob("*.json")):
        if json_file.name in EXCLUDE_FILES:
            continue
        for category, filenames in CATEGORY_MAP.items():
            if json_file.name in filenames:
                files_by_category[category].append(json_file)
                break
    return files_by_category

def combine_schemas(schema_files, combined_path, category):
    """Combine raw JSON files into a single schema for the category."""
    properties = {}
    required = []
    for json_file in schema_files:
        key = json_file.stem
        properties[key] = json.loads(json_file.read_text())  # Treat raw JSON as schema
        required.append(key)
    combined_schema = {
        "title": f"{category.capitalize()}CombinedSchema",
        "type": "object",
        "properties": properties,
        "required": required
    }
    combined_path.write_text(json.dumps(combined_schema, indent=2))
    logger.info(f"Combined {len(schema_files)} JSON files into {relpath(combined_path)} for category '{category}'")

def generate_models(schema_path: Path, output_file: Path):
    """Generate Pydantic models from raw JSON."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "datamodel-codegen",
        "--input", str(schema_path),
        "--input-file-type", "json",  # Treats raw JSON as data to infer schema
        "--output", str(output_file),
        "--use-default",
        "--disable-timestamp",
        "--reuse-model",
        "--use-double-quotes",
        "--strip-default-none",
        "--field-constraints",
    ]
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    if result.stderr:
        logger.warning(f"datamodel-codegen output: {result.stderr}")
    line_count = output_file.read_text(encoding="utf-8").count("\n")
    logger.info(f"Generated {line_count} lines of models at {relpath(output_file)}")

def generate_init_py(models_dir: Path, categories):
    """Generate __init__.py with imports for each category's models."""
    models_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"from .{cat}_models import {cat.capitalize()}Model\n" for cat in categories]
    init_file = models_dir / "__init__.py"
    init_file.write_text("".join(lines), encoding="utf-8")
    logger.info(f"Generated {relpath(init_file)} with imports for {len(categories)} categories")

def clean_output_dir(output_dir: Path):
    """Clean the output directory if it exists."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
        logger.info(f"Cleaned existing output directory {relpath(output_dir)}")

def main():
    """Main function to generate models from raw JSON."""
    try:
        logger.info(f"Collecting JSON files from {relpath(SCHEMA_DIR)}")
        files_by_category = collect_files_by_category()

        clean_output_dir(APP_MODELS_DIR)

        for category, schema_files in files_by_category.items():
            if not schema_files:
                logger.warning(f"No JSON files found for category '{category}'")
                continue
            combined_path = SCHEMA_DIR / f"combined_{category}.json"
            combine_schemas(schema_files, combined_path, category)
            output_file = APP_MODELS_DIR / f"{category}_models.py"
            generate_models(combined_path, output_file)

        generate_init_py(APP_MODELS_DIR, files_by_category.keys())
        logger.info("Model generation complete.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess failed: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

if __name__ == "__main__":
    main()