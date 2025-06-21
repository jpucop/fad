#!/usr/bin/env python3

import json
import logging
from pathlib import Path
from typing import Any, Dict, List
from gen.apps import regenerate as generate_apps

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent.parent.parent  # /Users/gonre/dev/fad/backend
MODEL_DIR = BASE_DIR / "model"
UCOP_DIR = MODEL_DIR / "ucop" / "finapps"
SCHEMA_DIR = MODEL_DIR / "schema"
OUTPUT_MODELS_DIR = BASE_DIR / "app" / "models"
OUTPUT_DATA_DIR = BASE_DIR / "app" / "data"

def load_json(file_path: Path) -> Dict:
    """Load a JSON file."""
    logger.debug(f"Loading {file_path}")
    if not file_path.exists():
        logger.error(f"File {file_path} does not exist.")
        raise FileNotFoundError(f"File {file_path} does not exist.")
    with open(file_path, "r") as f:
        return json.load(f)

def save_file(content: str, file_path: str | Path) -> None:
    """Save content to a file."""
    file_path = Path(file_path)
    logger.debug(f"Saving {file_path}")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w") as f:
        f.write(content)

def get_type(value: Any) -> str:
    """Infer type from a value."""
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "null"

def validate_structure(data: Dict, template: Dict, path: str, file_name: str) -> List[str]:
    """Validate data structure against template."""
    discrepancies = []

    for key, template_value in template.items():
        current_path = f"{path}.{key}" if path else key
        expected_type = get_type(template_value)

        if key not in data:
            discrepancies.append(f"{file_name}: Missing property '{current_path}' (expected {expected_type})")
            continue

        data_value = data[key]
        actual_type = get_type(data_value)

        if actual_type != expected_type:
            discrepancies.append(
                f"{file_name}: Type mismatch for '{current_path}' (expected {expected_type}, found {actual_type})"
            )
            continue

        if expected_type == "object":
            discrepancies.extend(validate_structure(data_value, template_value, current_path, file_name))
        elif expected_type == "array" and template_value and isinstance(template_value[0], dict):
            for i, item in enumerate(data_value):
                discrepancies.extend(
                    validate_structure(item, template_value[0], f"{current_path}[{i}]", file_name)
                )

    # Allow extra properties in data (e.g., _schema_description if present)
    return discrepancies

def snake_to_pascal(snake_str: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in snake_str.split("_"))

def template_to_pydantic(template: Dict, model_name: str, indent: int = 4) -> str:
    """Generate Pydantic model from JSON template."""
    lines = ["from pydantic import BaseModel\n"]
    imports = ["from typing import Optional"]

    if any(isinstance(v, list) for v in template.values()):
        imports.append("from typing import List")

    lines.extend([f"{imp}\n" for imp in sorted(imports)])
    lines.append("\n")

    lines.append(f"class {model_name}(BaseModel):\n")
    for key, value in template.items():
        value_type = get_type(value)
        python_type = {
            "string": "str",
            "number": "float",
            "boolean": "bool"
        }.get(value_type, "str")

        if value_type == "array":
            item_type = get_type(value[0]) if value else "string"
            item_python_type = {
                "string": "str",
                "number": "float",
                "boolean": "bool",
                "object": snake_to_pascal(key)
            }.get(item_type, "str")
            if item_type == "object":
                lines.append(template_to_pydantic(value[0], item_python_type))
            python_type = f"List[{item_python_type}]"
        elif value_type == "object":
            nested_model_name = snake_to_pascal(key)
            lines.append(template_to_pydantic(value, nested_model_name))
            python_type = nested_model_name

        python_type = f"Optional[{python_type}]"
        lines.append(f"{' ' * indent}{key}: {python_type}\n")

    return "".join(lines)

def generate_init_file() -> None:
    """Generate __init__.py."""
    model_files = [f.stem for f in OUTPUT_MODELS_DIR.glob("*.py") if f.name != "__init__.py"]
    data_files = [f.stem for f in OUTPUT_DATA_DIR.glob("*.json")]

    init_content = ["from pathlib import Path\n"]
    init_content.append("from . import (\n")
    init_content.extend(f"    {model},\n" for model in sorted(model_files))
    init_content.append(")\n\n")

    init_content.append("DATA_DIR = Path(__file__).parent / 'data'\n")
    init_content.append("def load_data(file_name: str) -> dict:\n")
    init_content.append("    file_path = DATA_DIR / f'{file_name}.json'\n")
    init_content.append("    with open(file_path) as f:\n")
    init_content.append("        return json.load(f)\n\n")

    init_content.append("DATA_FILES = {\n")
    for data_file in sorted(data_files):
        key = data_file.replace("app_", "").replace("_", "-")
        init_content.append(f"    '{key}': '{data_file}',\n")
    init_content.append("}\n")

    save_file("".join(init_content), OUTPUT_MODELS_DIR / "__init__.py")
    logger.info(f"Generated {OUTPUT_MODELS_DIR / '__init__.py'}")

def validate_models():
    """Validate JSON files against their templates."""
    errors = []

    # Validate org_ucop.json
    org_path = MODEL_DIR / "ucop" / "org_ucop.json"
    org_template = load_json(SCHEMA_DIR / "org.json")
    if org_path.exists():
        org_data = load_json(org_path)
        errors.extend(validate_structure(org_data, org_template, "", "org_ucop.json"))
    else:
        errors.append(f"org_ucop.json: File not found at {org_path}")

    # Validate group_finapps.json
    group_path = UCOP_DIR / "group_finapps.json"
    group_template = load_json(SCHEMA_DIR / "group.json")
    if group_path.exists():
        group_data = load_json(group_path)
        errors.extend(validate_structure(group_data, group_template, "", "group_finapps.json"))
    else:
        errors.append(f"group_finapps.json: File not found at {group_path}")

    # Validate app_*.json
    app_template = load_json(SCHEMA_DIR / "app.json")
    for app_file in UCOP_DIR.glob("app_*.json"):
        if app_file.exists():
            app_data = load_json(app_file)
            errors.extend(validate_structure(app_data, app_template, "", app_file.name))
        else:
            errors.append(f"{app_file.name}: File not found")

    return errors

def copy_to_app():
    """Copy validated JSON files to app/data/."""
    OUTPUT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    templates = {
        "app": load_json(SCHEMA_DIR / "app.json"),
        "org_ucop": load_json(SCHEMA_DIR / "org.json"),
        "group_finapps": load_json(SCHEMA_DIR / "group.json")
    }

    for json_file in UCOP_DIR.glob("*.json"):
        if json_file.name.startswith("app_") or json_file.name in ["org_ucop.json", "group_finapps.json"]:
            json_data = load_json(json_file)
            template_key = "app" if json_file.name.startswith("app_") else json_file.name
            template_data = templates[template_key]
            errors = validate_structure(json_data, template_data, "", json_file.name)
            if errors:
                logger.error(f"Validation errors in {json_file.name}: {errors}")
                continue
            dest_path = OUTPUT_DATA_DIR / json_file.name
            save_file(json.dumps(json_data, indent=2), dest_path)
            logger.info(f"Copied {json_file.name} to {dest_path}")

def generate_models():
    """Generate Pydantic models from templates."""
    OUTPUT_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for template_file in SCHEMA_DIR.glob("*.json"):
        template_name = template_file.stem
        template_data = load_json(template_file)
        model_name = snake_to_pascal(template_name)
        pydantic_model = template_to_pydantic(template_data, model_name)
        model_path = OUTPUT_MODELS_DIR / f"{template_name}.py"
        save_file(pydantic_model, model_path)
        logger.info(f"Generated Pydantic model for {template_name} at {model_path}")

def regenerate(validate: bool = True, generate_apps_flag: bool = True, copy: bool = True, models: bool = True):
    """Regenerate, validate, copy, and generate models."""
    if validate:
        errors = validate_models()
        if errors:
            logger.error("Validation failed:")
            for err in errors:
                logger.error(err)
            raise ValueError("Validation errors detected")

    if generate_apps_flag:
        generate_apps()

    if copy:
        copy_to_app()

    if models:
        generate_models()
        generate_init_file()

if __name__ == "__main__":
    try:
        logger.info(f"BASE_DIR: {BASE_DIR}")
        logger.info(f"MODEL_DIR: {MODEL_DIR}")
        logger.info(f"UCOP_DIR: {UCOP_DIR}")
        logger.info(f"SCHEMA_DIR: {SCHEMA_DIR}")
        for path in [
            MODEL_DIR / "ucop" / "org_ucop.json",
            UCOP_DIR / "group_finapps.json",
            SCHEMA_DIR / "app.json",
            SCHEMA_DIR / "group.json",
            SCHEMA_DIR / "org.json"
        ]:
            logger.debug(f"Checking file: {path} -> {'exists' if path.exists() else 'missing'}")
        regenerate()
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise