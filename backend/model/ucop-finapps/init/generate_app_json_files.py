import json
import os
from pathlib import Path

def load_json(file_path):
  with open(file_path, 'r') as f:
    return json.load(f)

def save_json(data, file_path):
  with open(file_path, 'w') as f:
    json.dump(data, f, indent=2)

def generate_app_json(app_name, org_group_data, app_schema, output_dir):
  # Base app.json structure from schema
  app_data = app_schema.copy()
  
  # Set basic app details
  app_data['name'] = app_name
  app_data['short_name'] = app_name.upper()
  app_data['long_name'] = f"Financial Applications - {app_name.upper()}"
  app_data['description'] = f"{app_name.upper()} application managed by Financial Applications group"
  
  # Set org and group
  app_data['org'] = org_group_data['org']['name']
  app_data['group'] = org_group_data['group']['name']
  
  # Default profiles (can be customized per app)
  app_data['app_profile'] = 'tomcat-java'
  app_data['deploy_profile'] = 'aws-cicd-fargate-rds'
  
  # Source configuration
  app_data['source']['project_name'] = app_name
  app_data['source']['git_origin_url'] = f"https://github.com/ucop/{app_name}.git"
  app_data['source']['production_branch_name'] = 'main'
  
  # AWS account mapping
  aws_accounts = org_group_data['group']['aws']['accounts']
  app_data['source']['aws']['account_name'] = next(
    acc['name'] for acc in aws_accounts if 'prod' in acc['name']
  )
  
  # ServiceNow assignment groups
  assignment_groups = org_group_data['group']['service_now']['assignment_groups']
  app_groups = [g['name'] for g in assignment_groups if app_name in g.get('apps', '').split(',') or g['apps'] == 'ALL']
  app_data['service_now']['assignment_groups'] = app_groups
  
  # Environment configurations
  environments = [
    {
      'env': 'dev',
      'name': 'development',
      'host': 'aws',
      'app_profile': 'tomcat-java',
      'deploy_profile': 'aws-cicd-fargate-rds',
      'deploy_pipeline_name': f"{app_name}-dev-pipeline",
      'git_branch': 'dev',
      'aws': {'account_name': 'finapps-dev'}
    },
    {
      'env': 'qa',
      'name': 'staging',
      'host': 'aws',
      'app_profile': 'tomcat-java',
      'deploy_profile': 'aws-cicd-fargate-rds',
      'deploy_pipeline_name': f"{app_name}-qa-pipeline",
      'git_branch': 'qa',
      'aws': {'account_name': 'finapps-dev'}
    },
    {
      'env': 'prod',
      'name': 'production',
      'host': 'aws',
      'app_profile': 'tomcat-java',
      'deploy_profile': 'aws-cicd-fargate-rds',
      'deploy_pipeline_name': f"{app_name}-prod-pipeline",
      'git_branch': 'main',
      'aws': {'account_name': 'finapps-prod'}
    }
  ]
  app_data['environments'] = environments
  
  # Save the generated app.json
  output_path = output_dir / f"{app_name}.json"
  save_json(app_data, output_path)
  print(f"Generated app.json for {app_name} at {output_path}")

def main():
  # Paths
  base_dir = Path(__file__).parent.parent
  schema_dir = base_dir / 'schema'
  org_group_file = base_dir / 'ucop-finapps' / 'org_group.json'
  output_dir = base_dir / 'ucop-finapps' / 'apps'
  
  # Create output directory if it doesn't exist
  output_dir.mkdir(exist_ok=True)
  
  # Load schema and org_group data
  app_schema = load_json(schema_dir / 'app.json')
  org_group_data = load_json(org_group_file)
  
  # Get list of apps from service_now assignment groups
  assignment_groups = org_group_data['group']['service_now']['assignment_groups']
  apps = set()
  for group in assignment_groups:
    if group['apps'] == 'ALL':
      continue
    apps.update(group.get('apps', '').split(','))
  
  # Generate app.json for each app
  for app in apps:
    if app:  # Skip empty app names
      generate_app_json(app, org_group_data, app_schema, output_dir)

if __name__ == '__main__':
  main()