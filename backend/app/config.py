import boto3
import json
import os

class Config:
  def __init__(self, env: str = "dev"):
    self.env = env
    self.config = self.load_config()

  def load_config(self):
    """Loads the app configuration from the config.json file."""
    config_file = "app.config.json"
    with open(config_file, "r") as f:
      config_data = json.load(f)

    if self.env not in config_data:
      raise ValueError(f"Invalid environment: {self.env}")

    return config_data[self.env]

  def assume_role(self, role_arn: str):
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
  def aws_region(self):
    return self.config.get("aws_region")

  @property
  def cluster_name(self):
    return self.config.get("cluster_name")

  def get_aws_credentials(self, role_arn: str):
    """Get the AWS credentials (access key, secret key, session token)."""
    return self.assume_role(role_arn)
