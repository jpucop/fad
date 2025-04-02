#!/usr/bin/env python3
import argparse
import os
import json
from pydantic import ValidationError
from models import AppConfig

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def generate_app_config(app_name, output_dir=".", app_desc="FastAPI-based application"):
    config_data = {
        "version": "1",
        "app_name": app_name,
        "app_desc": app_desc,
        "app_profile": "flask-sso",
        "deploy_profile": "aws-cicd-fargate",
        "source": {
            "project_name": f"{app_name}Web",
            "git_origin_url": f"https://aws.codecommit.com/{app_name}Web",
            "aws": {"account_name": "finapps-dev"}
        },
        "docs": [
            {
                "name": "Wikis",
                "desc": f"Confluence docs for {app_name.upper()}",
                "url": f"https://ucopedu.atlassian.net/wiki/spaces/FA/pages/48138543/{app_name}Web"
            }
        ],
        "environments": [
            {
                "name": "dev",
                "host": "aws",
                "git_branch": "dev",
                "app_profile": "flask-sso",
                "deploy_profile": "aws-cicd-fargate",
                "deploy_pipeline_name": f"pipeline-{app_name}-dev",
                "aws": {"account_name": "finapps-dev"}
            },
            {
                "name": "qa",
                "host": "aws",
                "git_branch": "qa",
                "app_profile": "flask-sso",
                "deploy_profile": "aws-cicd-fargate",
                "deploy_pipeline_name": f"pipeline-{app_name}-qa",
                "aws": {"account_name": "finapps-dev"}
            },
            {
                "name": "prod",
                "host": "aws",
                "git_branch": "main",
                "app_profile": "flask-sso",
                "deploy_profile": "aws-cicd-fargate",
                "deploy_pipeline_name": f"pipeline-{app_name}-prod",
                "aws": {"account_name": "finapps-prod"}
            }
        ]
    }

    try:
        app_config = AppConfig(**config_data)
        output_file = os.path.join(output_dir, f"app.config-{app_name}.json")
        with open(output_file, "w") as f:
            json.dump(app_config.dict(), f, indent=2)
        print(f"Generated and validated app config file: {output_file}")
    except ValidationError as e:
        print(f"Validation error: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Generate a stub app configuration for a FastAPI app.")
    parser.add_argument("--app_name", required=True, help="Name of the application (e.g., 'fad')")
    parser.add_argument("--app_desc", default="FastAPI-based application", help="Description of the application")
    parser.add_argument("--output_dir", default=".", help="Directory to save the output JSON file")
    args = parser.parse_args()
    generate_app_config(args.app_name, args.output_dir, args.app_desc)

if __name__ == "__main__":
    main()