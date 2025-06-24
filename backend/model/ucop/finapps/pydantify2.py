#!/usr/bin/env python3

import logging
from pathlib import Path
from datamodel_code_generator import InputFileType, generate

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths (adjust as needed)
BASE_DIR = Path(__file__).parent.parent.parent.parent  # adjust to your repo root
SCHEMA_DIR = BASE_DIR / "model" / "schema"
MODEL_DIR = BASE_DIR / "model" / "ucop" / "finapps" / "models"

def snake_to_pascal(snake_str: str) -> str:
  return "".join(word.capitalize() for word in snake_str.split("_"))

def generate_models_with_datamodel(schema_dir: Path, output_dir: Path):
  output_dir.mkdir(parents=True, exist_ok=True)
  
  for json_file in sorted(schema_dir.glob("*.json")):
    model_name = snake_to_pascal(json_file.stem)
    logger.info(f"Generating model for {json_file.name} as class {model_name}")
    
    with open(json_file, "r") as f:
      json_data = f.read()
    
      generate(
        input_=json_data,
        input_file_type=InputFileType.Json,
        output=output_dir,
        class_name=model_name,
        strip_default_none=True,
        use_field_description=False,
      )

def main():
  logger.info(f"Starting model generation from {SCHEMA_DIR} to {MODEL_DIR}")
  generate_models_with_datamodel(SCHEMA_DIR, MODEL_DIR)
  logger.info("Model generation complete.")

if __name__ == "__main__":
  main()
