import boto3
import json
import os
from typing import Optional
from app.models import AppConfig

class Config:
  def __init__(self, env: str = "dev", config_file: Optional[str] = None):
    self.env = env
    self.config_file = config_file or "app.config.json"
    self.config = self.load_config()

  def load_config(self) -> AppConfig:
    """Loads and validates app configuration from a JSON file."""
    if not os.path.exists(self.config_file):
      raise FileNotFoundError(f"Config file {self.config_file} not found")
    
    with open(self.config_file, "r") as f:
      config_data = json.load(f)
    
    # If config_file is environment-specific, extract the env data
    if isinstance(config_data, dict) and self.env in config_data:
      config_data = config_data[self.env]
    # Otherwise, assume it’s an AppConfig-like structure (e.g., generated file)
    
    try:
      return AppConfig(**config_data)
    except ValueError as e:
      raise ValueError(f"Invalid config format in {self.config_file}: {str(e)}")

  def assume_role(self, role_arn: str) -> dict:
    """Assume an IAM Role and get temporary credentials."""
    sts_client = boto3.client("sts")
    assumed_role_object = sts_client.assume_role(
      RoleArn=role_arn,
      RoleSessionName="AssumeRoleSession1"
    )
    credentials = assumed_role_object["Credentials"]
    return {
      "aws_access_key_id": credentials["AccessKeyId"],
      "aws_secret_access_key": credentials["SecretAccessKey"],
      "aws_session_token": credentials["SessionToken"],
    }

  @property
  def aws_region(self) -> str:
    return self.config.source.aws_region  # Updated to use Pydantic model

  @property
  def cluster_name(self) -> Optional[str]:
    return getattr(self.config, "cluster_name", None)  # Not in AppConfig yet

  def get_aws_credentials(self, role_arn: str) -> dict:
    """Get AWS credentials using role assumption."""
    return self.assume_role(role_arn)