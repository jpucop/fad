import boto3
import json
import yaml
import os
import tempfile
import subprocess
import shutil
from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

# Pydantic models for updated app_topo.json schema
class SourceInfo(BaseModel):
    git_branch_name: str
    git_commit: str
    git_origin_url: str
    project_name: str

class CodePipelineInfo(BaseModel):
    name: str
    arn: str
    last_deployment_timestamp: str

class CloudWatchLogGroup(BaseModel):
    name: str
    arn: str

class ECSContainer(BaseModel):
    name: str
    image: str
    log_group_name: str

class ECSInfo(BaseModel):
    cluster_name: str
    service_name: str
    task_definition_arn: str
    status: str
    running_count: int
    health: str
    version: str
    containers: List[ECSContainer] = []
    cw_log_groups: List[CloudWatchLogGroup] = []

class ALBInfo(BaseModel):
    arn: str
    name: str
    dns_name: str
    certificate_arn: str
    protocol: str
    port: int
    status: str
    health: str
    cw_log_groups: List[CloudWatchLogGroup] = []

class RDSInstance(BaseModel):
    arn: str
    identifier: str
    endpoint: str
    status: str
    tags: List[str] = []
    cw_log_groups: List[CloudWatchLogGroup] = []

class RDSInfo(BaseModel):
    instances: List[RDSInstance] = []

class S3Bucket(BaseModel):
    name: str
    s3_url: str
    arn: str
    tags: List[str] = []

class S3Info(BaseModel):
    buckets: List[S3Bucket] = []

class AWSInfo(BaseModel):
    account_name: str
    account_id: str
    codepipeline: CodePipelineInfo
    ecs: ECSInfo
    alb: ALBInfo
    rds: RDSInfo
    s3: S3Info

class AppTopology(BaseModel):
    app_name: str
    environment: str
    deploy_profile: str
    created: str
    source: SourceInfo
    aws: AWSInfo

# Initialize boto3 clients
session = boto3.Session()
sts_client = session.client('sts')
codecommit_client = session.client('codecommit')
codepipeline_client = session.client('codepipeline')
codedeploy_client = session.client('codedeploy')
ecs_client = session.client('ecs')
rds_client = session.client('rds')
elbv2_client = session.client('elbv2')
s3_client = session.client('s3')
logs_client = session.client('logs')

# In-memory cache
SNAPSHOT_CACHE: Dict[str, Dict] = {}

def safe_fetch(fn, default=None):
    """Safely execute an AWS API call with error handling."""
    try:
        return fn()
    except Exception as e:
        print(f"Error in API call: {e}")
        return default

def load_app_definition(app_name: str, env: str) -> Dict:
    """Load app.json for the given app_name and environment."""
    file_path = f"backend/model/ucop-finapps/init/app_{app_name}.json"
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            env_data = data.get('environments', [{}])[0] if env == data.get('environment', 'prod') else next((e for e in data.get('environments', []) if e.get('name') == env), {})
            return {
                'app_name': data.get('name', app_name),
                'environment': env,
                'deploy_profile': data.get('deploy_profile', 'cicd-fargate-alb-rds'),
                'source': data.get('source', {}),
                'dbs': data.get('dbs', []),
                'region': env_data.get('region', session.region_name)
            }
    except FileNotFoundError:
        print(f"App definition file for {app_name} not found. Using default.")
        return {
            'app_name': app_name,
            'environment': env,
            'deploy_profile': 'cicd-fargate-alb-rds',
            'source': {
                'project_name': f"{app_name}-repo",
                'git_origin_url': f"https://codecommit.{session.region_name}.amazonaws.com/v1/repos/{app_name}-repo",
                'production_branch_name': 'main',
                'aws': {'account_name': ''}
            },
            'dbs': [{'name': f"{app_name}-{env}-db", 'aws': {'db_arn': ''}}],
            'region': session.region_name
        }

def clone_codecommit_repo(git_url: str, repo_name: str, region: str) -> str:
    """Clone the CodeCommit repository to a temporary directory."""
    repo_data = safe_fetch(lambda: codecommit_client.get_repository(repositoryName=repo_name))
    if not repo_data:
        raise Exception(f"Repository {repo_name} not found")
    
    clone_url = repo_data.get('repositoryMetadata', {}).get('cloneUrlHttp', git_url)
    temp_dir = tempfile.mkdtemp()
    try:
        subprocess.run(
            ["git", "clone", clone_url, temp_dir],
            check=True,
            capture_output=True,
            text=True
        )
        return temp_dir
    except subprocess.CalledProcessError as e:
        shutil.rmtree(temp_dir)
        raise Exception(f"Failed to clone repository {repo_name}: {e.stderr}")

def parse_appspec(repo_dir: str, env: str) -> Dict:
    """Parse appspec-{env}.yml to extract ECS task and container details."""
    appspec_path = os.path.join(repo_dir, f"appspec-{env}.yml")
    if not os.path.exists(appspec_path):
        print(f"appspec-{env}.yml not found in {repo_dir}")
        return {}
    
    with open(appspec_path, 'r') as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"Error parsing appspec-{env}.yml: {e}")
            return {}

def get_cached_snapshot(app_name: str, env: str) -> Optional[Dict]:
    """Retrieve cached snapshot if not expired."""
    cache_key = f"{app_name}#{env}"
    cached = SNAPSHOT_CACHE.get(cache_key)
    if cached:
        last_updated = datetime.strptime(cached.get('created', '1970-01-01T00:00:00Z'), '%Y-%m-%dT%H:%M:%SZ')
        if (datetime.utcnow() - last_updated).total_seconds() < 300:  # 5-minute cache
            return cached
    return None

def update_cached_snapshot(app_name: str, env: str, snapshot: Dict):
    """Update the in-memory cache with a new snapshot."""
    cache_key = f"{app_name}#{env}"
    SNAPSHOT_CACHE[cache_key] = snapshot

def get_source_info(app_def: Dict, env: str) -> SourceInfo:
    """Fetch source details (branch and commit) from CodeCommit."""
    repo_name = app_def['source'].get('project_name', '')
    branch_name = app_def['source'].get('production_branch_name', 'main')
    git_url = app_def['source'].get('git_origin_url', '')
    
    commit_id = ''
    if repo_name:
        branch_data = safe_fetch(lambda: codecommit_client.get_branch(repositoryName=repo_name, branchName=branch_name))
        if branch_data:
            commit_id = branch_data.get('branch', {}).get('commitId', '')
    
    return SourceInfo(
        git_branch_name=branch_name,
        git_commit=commit_id,
        git_origin_url=git_url,
        project_name=repo_name
    )

def get_pipeline_info(pipeline_name: str) -> CodePipelineInfo:
    """Fetch CodePipeline details, ARN, and last deployment timestamp."""
    pipeline_data = safe_fetch(lambda: codepipeline_client.get_pipeline(name=pipeline_name))
    arn = safe_fetch(lambda: codepipeline_client.get_pipeline_state(name=pipeline_name)['pipelineArn'], '')
    last_deployment = safe_fetch(lambda: codepipeline_client.list_pipeline_executions(pipelineName=pipeline_name)['pipelineExecutionSummaries'][0]['lastUpdateTime'], '')
    last_deployment_timestamp = last_deployment.strftime('%Y-%m-%dT%H:%M:%SZ') if last_deployment else ''
    return CodePipelineInfo(name=pipeline_name, arn=arn, last_deployment_timestamp=last_deployment_timestamp)

def get_ecs_from_pipeline(pipeline_name: str, app_name: str, env: str, repo_dir: Optional[str]) -> ECSInfo:
    """Derive ECS details from CodePipeline, appspec, and ECS API."""
    cluster_name = f"{app_name}-{env}-cluster"
    service_name = f"{app_name}-{env}-service"
    task_definition_arn = ''
    status = 'UNKNOWN'
    running_count = 0
    health = 'UNKNOWN'
    version = 'unknown'
    containers = []
    
    # Get CodeDeploy configuration from pipeline
    pipeline_data = safe_fetch(lambda: codepipeline_client.get_pipeline(name=pipeline_name))
    if pipeline_data:
        for stage in pipeline_data['pipeline']['stages']:
            for action in stage['actions']:
                if action['actionTypeId']['provider'] == 'CodeDeployToECS':
                    config = action.get('configuration', {})
                    app_name_cd = config.get('ApplicationName', app_name)
                    deployment_group = config.get('DeploymentGroupName')
                    deployment_info = safe_fetch(lambda: codedeploy_client.get_deployment_group(
                        applicationName=app_name_cd,
                        deploymentGroupName=deployment_group
                    ))
                    if deployment_info:
                        ecs_config = deployment_info['deploymentGroupInfo'].get('ecsServices', [{}])[0]
                        cluster_name = ecs_config.get('clusterName', cluster_name)
                        service_name = ecs_config.get('serviceName', service_name)

    # Parse appspec for task definition, containers, and version
    log_group_name = f"/aws/fargate/{app_name}-{env}"
    if repo_dir:
        appspec = parse_appspec(repo_dir, env)
        if appspec and 'Resources' in appspec:
            for resource in appspec['Resources']:
                if 'TargetService' in resource:
                    service_name = resource['TargetService']['Properties'].get('ServiceName', service_name)
                    task_def = resource['TargetService']['Properties'].get('TaskDefinition')
                    if task_def:
                        task_definition_arn = task_def
                        task_def_data = safe_fetch(lambda: ecs_client.describe_task_definition(taskDefinition=task_def)['taskDefinition'])
                        if task_def_data:
                            for container in task_def_data.get('containerDefinitions', []):
                                container_name = container.get('name', 'unknown')
                                image = container.get('image', 'unknown')
                                log_config = container.get('logConfiguration', {})
                                container_log_group = log_group_name
                                if log_config.get('logDriver') == 'awslogs':
                                    container_log_group = log_config['options'].get('awslogs-group', log_group_name)
                                containers.append(ECSContainer(
                                    name=container_name,
                                    image=image,
                                    log_group_name=container_log_group
                                ))
                            # Extract version from image tag or task definition tags
                            version = task_def_data.get('containerDefinitions', [{}])[0].get('image', 'unknown').split(':')[-1] or 'unknown'

    # Fetch ECS service details
    service_data = safe_fetch(lambda: ecs_client.describe_services(cluster=cluster_name, services=[service_name])['services'])
    if service_data and service_data[0]:
        status = service_data[0].get('status', 'UNKNOWN')
        running_count = service_data[0].get('runningCount', 0)
        desired_count = service_data[0].get('desiredCount', 0)
        task_definition_arn = service_data[0].get('taskDefinition', task_definition_arn)
        # Determine health: HEALTHY if running_count matches desired_count and tasks are healthy
        health = 'HEALTHY' if running_count == desired_count else 'DEGRADED'
        if running_count > 0:
            tasks = safe_fetch(lambda: ecs_client.list_tasks(cluster=cluster_name, serviceName=service_name)['taskArns'])
            if tasks:
                task_details = safe_fetch(lambda: ecs_client.describe_tasks(cluster=cluster_name, tasks=tasks)['tasks'])
                if task_details and any(t.get('healthStatus') == 'UNHEALTHY' for t in task_details):
                    health = 'UNHEALTHY'

    # Fetch ECS log groups
    log_groups = []
    account_id = safe_fetch(lambda: sts_client.get_caller_identity()['Account'], 'unknown')
    log_data = safe_fetch(lambda: logs_client.describe_log_groups(logGroupNamePrefix=f"/aws/ecs/{app_name}-{env}"))
    if not log_data:
        log_data = safe_fetch(lambda: logs_client.describe_log_groups(logGroupNamePrefix=f"/aws/fargate/{app_name}-{env}"), {})
    for lg in log_data.get('logGroups', []):
        if lg['logGroupName'].startswith(log_group_name):
            log_groups.append(CloudWatchLogGroup(
                name=lg['logGroupName'],
                arn=lg.get('arn', '')
            ))

    return ECSInfo(
        cluster_name=cluster_name,
        service_name=service_name,
        task_definition_arn=task_definition_arn,
        status=status,
        running_count=running_count,
        health=health,
        version=version,
        containers=containers,
        cw_log_groups=log_groups
    )

def get_alb_from_pipeline(pipeline_name: str, app_name: str, env: str) -> ALBInfo:
    """Derive ALB details from CodePipeline's CodeDeploy configuration."""
    alb_name = f"{app_name}-{env}-alb"
    arn = ''
    dns_name = ''
    cert_arn = ''
    protocol = 'HTTP'
    port = 80
    status = 'UNKNOWN'
    health = 'UNKNOWN'

    pipeline_data = safe_fetch(lambda: codepipeline_client.get_pipeline(name=pipeline_name))
    if pipeline_data:
        for stage in pipeline_data['pipeline']['stages']:
            for action in stage['actions']:
                if action['actionTypeId']['provider'] == 'CodeDeployToECS':
                    config = action.get('configuration', {})
                    deployment_group = config.get('DeploymentGroupName')
                    deployment_info = safe_fetch(lambda: codedeploy_client.get_deployment_group(
                        applicationName=config.get('ApplicationName', app_name),
                        deploymentGroupName=deployment_group
                    ))
                    if deployment_info:
                        lb_info = deployment_info['deploymentGroupInfo'].get('loadBalancerInfo', {}).get('targetGroupPairInfoList', [{}])[0]
                        target_group_names = [tg.get('name') for tg in lb_info.get('targetGroups', []) if tg.get('name')]
                        if target_group_names:
                            tg_data = safe_fetch(lambda: elbv2_client.describe_target_groups(Names=target_group_names))
                            if tg_data and tg_data.get('TargetGroups'):
                                tg_arn = tg_data['TargetGroups'][0]['TargetGroupArn']
                                lb_arns = tg_data['TargetGroups'][0].get('LoadBalancerArns', [])
                                if lb_arns:
                                    lb_data = safe_fetch(lambda: elbv2_client.describe_load_balancers(LoadBalancerArns=[lb_arns[0]]))
                                    if lb_data and lb_data.get('LoadBalancers'):
                                        alb = lb_data['LoadBalancers'][0]
                                        arn = alb.get('LoadBalancerArn', '')
                                        alb_name = alb.get('LoadBalancerName', alb_name)
                                        dns_name = alb.get('DNSName', '')
                                        status = alb.get('State', {}).get('Code', 'UNKNOWN')
                                        listener_data = safe_fetch(lambda: elbv2_client.describe_listeners(LoadBalancerArn=arn))
                                        if listener_data:
                                            listener = next((l for l in listener_data['Listeners'] if l['Port'] in [443, 80]), None)
                                            if listener:
                                                protocol = listener.get('Protocol', 'HTTP')
                                                port = listener.get('Port', 80)
                                                if listener.get('Certificates'):
                                                    cert_arn = listener['Certificates'][0]['CertificateArn']
                                        # Check target group health
                                        tg_health = safe_fetch(lambda: elbv2_client.describe_target_health(TargetGroupArn=tg_arn)['TargetHealthDescriptions'])
                                        if tg_health:
                                            health = 'HEALTHY' if all(t['TargetHealth']['State'] == 'healthy' for t in tg_health) else 'DEGRADED'

    # Fetch ALB log groups
    log_groups = []
    log_data = safe_fetch(lambda: logs_client.describe_log_groups(logGroupNamePrefix=f"/aws/alb/{app_name}-{env}"))
    for lg in log_data.get('logGroups', []):
        log_groups.append(CloudWatchLogGroup(
            name=lg['logGroupName'],
            arn=lg.get('arn', '')
        ))

    return ALBInfo(
        arn=arn,
        name=alb_name,
        dns_name=dns_name,
        certificate_arn=cert_arn,
        protocol=protocol,
        port=port,
        status=status,
        health=health,
        cw_log_groups=log_groups
    )

def get_rds_info(app_name: str, env: str, dbs: List[Dict]) -> RDSInfo:
    """Fetch RDS instance details from app.json or naming convention."""
    rds_identifier = next((db['name'] for db in dbs if db.get('name')), f"{app_name}-{env}-db")
    instances = []
    rds_data = safe_fetch(lambda: rds_client.describe_db_instances(DBInstanceIdentifier=rds_identifier))
    if rds_data and rds_data.get('DBInstances'):
        db = rds_data['DBInstances'][0]
        log_groups = []
        log_data = safe_fetch(lambda: logs_client.describe_log_groups(logGroupNamePrefix=f"/aws/rds/{rds_identifier}"))
        for lg in log_data.get('logGroups', []):
            log_groups.append(CloudWatchLogGroup(
                name=lg['logGroupName'],
                arn=lg.get('arn', '')
            ))
        instances.append(RDSInstance(
            arn=db.get('DBInstanceArn', ''),
            identifier=rds_identifier,
            endpoint=db.get('Endpoint', {}).get('Address', ''),
            status=db.get('DBInstanceStatus', 'UNKNOWN'),
            tags=[f"{t['Key']}:{t['Value']}" for t in db.get('TagList', [])],
            cw_log_groups=log_groups
        ))
    return RDSInfo(instances=instances)

def get_s3_info(app_name: str, env: str) -> S3Info:
    """Fetch S3 buckets associated with the app."""
    buckets = []
    s3_data = safe_fetch(lambda: s3_client.list_buckets())
    for b in s3_data.get('Buckets', []):
        if b['Name'].startswith(f"{app_name}-{env}"):
            tags = safe_fetch(lambda: s3_client.get_bucket_tagging(Bucket=b['Name'])['TagSet'], [])
            buckets.append(S3Bucket(
                name=b['Name'],
                s3_url=f"s3://{b['Name']}",
                arn=f"arn:aws:s3:::{b['Name']}",
                tags=[f"{t['Key']}:{t['Value']}" for t in tags]
            ))
    return S3Info(buckets=buckets)

def crawl_app_infrastructure(app_name: str, pipeline_name: str, env: str = "prod") -> Dict:
    """Crawl AWS infrastructure to produce app_topo.json, using app.json and appspec."""
    # Check cache
    cached_snapshot = get_cached_snapshot(app_name, env)
    if cached_snapshot:
        return cached_snapshot

    # Load app definition
    app_def = load_app_definition(app_name, env)
    region = app_def.get('region', session.region_name)
    deploy_profile = app_def.get('deploy_profile', 'cicd-fargate-alb-rds')
    account_id = safe_fetch(lambda: sts_client.get_caller_identity()['Account'], 'unknown')
    account_name = app_def['source'].get('aws', {}).get('account_name', f"aws-account-{account_id}")

    # Clone CodeCommit repository to parse appspec
    repo_dir = None
    try:
        repo_dir = clone_codecommit_repo(
            git_url=app_def['source'].get('git_origin_url', ''),
            repo_name=app_def['source'].get('project_name', f"{app_name}-repo"),
            region=region
        )
    except Exception as e:
        print(f"Failed to clone repository: {e}")

    # Fetch infrastructure details
    source_info = get_source_info(app_def, env)
    codepipeline_info = get_pipeline_info(pipeline_name)
    ecs_info = get_ecs_from_pipeline(pipeline_name, app_name, env, repo_dir)
    alb_info = get_alb_from_pipeline(pipeline_name, app_name, env)
    rds_info = get_rds_info(app_name, env, app_def.get('dbs', []))
    s3_info = get_s3_info(app_name, env)

    # Clean up repository
    if repo_dir:
        shutil.rmtree(repo_dir)

    # Construct output
    app_topo = AppTopology(
        app_name=app_name,
        environment=env,
        deploy_profile=deploy_profile,
        created=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        source=source_info,
        aws=AWSInfo(
            account_name=account_name,
            account_id=account_id,
            codepipeline=codepipeline_info,
            ecs=ecs_info,
            alb=alb_info,
            rds=rds_info,
            s3=s3_info
        )
    )

    # Cache and return
    snapshot = app_topo.dict()
    update_cached_snapshot(app_name, env, snapshot)
    return snapshot

if __name__ == "__main__":
    # Example usage
    app_name = "myapp"
    pipeline_name = "myapp-prod-pipeline"
    env = "prod"
    result = crawl_app_infrastructure(app_name, pipeline_name, env)
    print(json.dumps(result, indent=2))