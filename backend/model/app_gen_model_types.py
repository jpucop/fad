# model/app_gen_model_types.py
import json
import os
from typing import Dict, Any, Set

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_TEMPLATE_PATH = os.path.join(BASE_DIR, "templates/app.config-template.json")
SNAPSHOT_TEMPLATE_PATH = os.path.join(BASE_DIR, "templates/app.snapshot-template.json")
APP_PROFILES_PATH = os.path.join(BASE_DIR, "app_profiles.json")
DEPLOY_PROFILES_PATH = os.path.join(BASE_DIR, "app_deploy_profiles.json")
AWS_PATH = os.path.join(BASE_DIR, "aws.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "../app/models.py")

def load_json(file_path: str) -> Dict[str, Any]:
    with open(file_path, "r") as f:
        return json.load(f)

def get_constrained_values(placeholder: str) -> Set[str]:
    """Load valid values for a placeholder from the appropriate file."""
    if "app_profiles[].name" in placeholder:
        data = load_json(APP_PROFILES_PATH)
        return {p["name"] for p in data["app_profiles"]}
    elif "deploy_profiles[].name" in placeholder:
        data = load_json(DEPLOY_PROFILES_PATH)
        return {p["name"] for p in data["app_deploy_profiles"]}
    elif "aws.accounts[].name" in placeholder:
        data = load_json(AWS_PATH)
        return {p["name"] for p in data["accounts"]}
    return set()

def infer_type(value: Any, key: str, parent_key: str = "") -> tuple[str, bool, Set[str]]:
    """Infer Python type, optionality, and constraints from JSON value or placeholder."""
    is_optional = isinstance(value, str) and (not value or value.startswith("{"))
    constraints = set()

    if isinstance(value, str):
        if value.startswith("{") and value.endswith("}"):
            if "app_profiles[].name" in value:
                constraints = get_constrained_values(value)
                return "str", is_optional, constraints
            elif "deploy_profiles[].name" in value:
                constraints = get_constrained_values(value)
                return "str", is_optional, constraints
            elif "aws.accounts[].name" in value:
                constraints = get_constrained_values(value)
                return "str", is_optional, constraints
            elif key == "git_origin_url" or "url" in key:
                return "HttpUrl", is_optional, constraints
            elif key == "name" and "environments" in parent_key:
                return "Literal['dev', 'qa', 'prod']", is_optional, {"dev", "qa", "prod"}
            elif key == "host" and "environments" in parent_key:
                return "Literal['aws']", is_optional, {"aws"}
            elif key == "type" and "docs" in parent_key:
                return "Literal['confluence', 'jira']", is_optional, {"confluence", "jira"}
            elif key == "status" and "environments" in parent_key:
                return "Literal['up', 'down', 'unknown']", is_optional, {"up", "down", "unknown"}
            elif key == "health" and "environments" in parent_key:
                return "Literal['healthy', 'unhealthy']", is_optional, {"healthy", "unhealthy"}
            elif key == "severity" and "logs" in parent_key:
                return "Literal['info', 'warning', 'error']", is_optional, {"info", "warning", "error"}
            elif key == "severity" and "vulnerabilities" in parent_key:
                return "Literal['low', 'medium', 'high', 'critical']", is_optional, {"low", "medium", "high", "critical"}
            elif key == "impact" and "servicenow" in parent_key:
                return "Literal['low', 'medium', 'high']", is_optional, {"low", "medium", "high"}
        return "str", is_optional, constraints
    elif isinstance(value, int):
        return "int", is_optional, constraints
    elif isinstance(value, float):
        return "float", is_optional, constraints
    elif isinstance(value, bool):
        return "bool", is_optional, constraints
    elif isinstance(value, list):
        return "List[Any]", is_optional, constraints
    elif isinstance(value, dict):
        return "Dict[str, Any]", is_optional, constraints
    return "Any", is_optional, constraints

def generate_class(name: str, data: Dict[str, Any], indent: int = 0, parent_key: str = "") -> list:
    """Generate Pydantic class definition as lines of code."""
    lines = [f"{' ' * indent}class {name}(BaseModel):"]
    for key, value in data.items():
        type_hint, is_optional, constraints = infer_type(value, key, parent_key)
        
        if isinstance(value, dict):
            nested_name = key.capitalize()
            nested_lines = generate_class(nested_name, value, indent + 4, f"{parent_key}{key}.")
            lines.extend(nested_lines)
            field_def = f"{' ' * (indent + 4)}{key}: {nested_name}"
            if is_optional:
                field_def += " = None"
            lines.append(field_def)
        elif isinstance(value, list) and value:
            nested_name = key.capitalize()
            nested_lines = generate_class(nested_name, value[0], indent + 4, f"{parent_key}{key}.")
            lines.extend(nested_lines)
            field_def = f"{' ' * (indent + 4)}{key}: List[{nested_name}]"
            if is_optional:
                field_def += " = []"
            lines.append(field_def)
        else:
            field_def = f"{' ' * (indent + 4)}{key}: {type_hint}"
            if is_optional:
                field_def = f"{' ' * (indent + 4)}{key}: Optional[{type_hint}] = None"
            lines.append(field_def)
            
            if constraints and "Literal" not in type_hint:
                lines.append(f"{' ' * (indent + 4)}@validator('{key}')")
                lines.append(f"{' ' * (indent + 4)}def validate_{key}(cls, v):")
                lines.append(f"{' ' * (indent + 8)}if v is not None and v not in {constraints}:")
                lines.append(f"{' ' * (indent + 12)}raise ValueError(f'{key} must be one of {constraints}')")
                lines.append(f"{' ' * (indent + 8)}return v")

    return lines

def main():
    config_template = load_json(CONFIG_TEMPLATE_PATH)
    snapshot_template = load_json(SNAPSHOT_TEMPLATE_PATH)
    snapshot_app_data = snapshot_template["app"]  # Extract the 'app' section for App model
    
    output = [
        "# Generated by app_gen_model_types.py",
        "from pydantic import BaseModel, HttpUrl, Field, validator",
        "from typing import List, Optional, Literal, Dict, Any",
        "from datetime import datetime",
        "import json",
        "import os",
        "",
        "BASE_DIR = os.path.dirname(os.path.abspath(__file__))",
        f"APP_PROFILES_PATH = os.path.join(BASE_DIR, '../model/app_profiles.json')",
        f"DEPLOY_PROFILES_PATH = os.path.join(BASE_DIR, '../model/app_deploy_profiles.json')",
        f"AWS_PATH = os.path.join(BASE_DIR, '../model/aws.json')",
        "",
        "# Load valid values for validation",
        "with open(APP_PROFILES_PATH, 'r') as f:",
        "    APP_PROFILES = {p['name'] for p in json.load(f)['app_profiles']}",
        "with open(DEPLOY_PROFILES_PATH, 'r') as f:",
        "    DEPLOY_PROFILES = {p['name'] for p in json.load(f)['app_deploy_profiles']}",
        "with open(AWS_PATH, 'r') as f:",
        "    AWS_ACCOUNTS = {p['name'] for p in json.load(f)['accounts']}",
        ""
    ]
    
    # Generate shared sub-models
    output.extend(generate_class("Doc", {"name": "", "url": "", "type": "Confluence"}))
    output.extend(generate_class("Source", config_template["source"]))
    
    # Generate AppConfig
    output.extend(generate_class("AppConfig", config_template))
    
    # Generate Snapshot sub-models
    output.extend(generate_class("Version", snapshot_template["app"]["environments"][0]["version"]))
    output.extend(generate_class("Deployment", snapshot_template["app"]["environments"][0]["deployment"]))
    output.extend(generate_class("DNS", snapshot_template["app"]["environments"][0]["dns"]))
    output.extend(generate_class("Certificate", snapshot_template["app"]["environments"][0]["certificate"]))
    output.extend(generate_class("AWSEnv", snapshot_template["app"]["environments"][0]["aws"]))
    output.extend(generate_class("Cost", snapshot_template["app"]["environments"][0]["cost"]))
    output.extend(generate_class("LogEntry", snapshot_template["app"]["environments"][0]["logs"]["http"]["recent"][0]))
    output.extend(generate_class("Logs", snapshot_template["app"]["environments"][0]["logs"]))
    output.extend(generate_class("Uptime", snapshot_template["app"]["environments"][0]["metrics"]["uptime"]))
    output.extend(generate_class("Errors", snapshot...

Something went wrong, please try again.