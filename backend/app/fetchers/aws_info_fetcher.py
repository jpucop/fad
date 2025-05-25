import boto3
import json
from pydantic import BaseModel, Field
from typing import List, Optional

class CICDInfo(BaseModel):
  arn: Optional[str] = ""
  last_deployment_timestamp: Optional[str] = ""
  pipeline_status: Optional[str] = ""

class Route53Info(BaseModel):
  hostedZone: Optional[str] = ""

class CertManagerInfo(BaseModel):
  tls_http_arn: Optional[str] = ""

class RDSInfo(BaseModel):
  rds_arnb: Optional[str] = ""

class ECSInfo(BaseModel):
  cluster_arn: Optional[str] = ""
  service_name: Optional[str] = ""
  task_definition_arn: Optional[str] = ""

class ALBInfo(BaseModel):
  alb_arn: Optional[str] = ""

class S3Info(BaseModel):
  referenced_bucket_arns: List[str] = []

class CloudWatchLogGroup(BaseModel):
  name: str
  url: str

class AWSInfo(BaseModel):
  account_id: str
  region: str
  codecommit_project_url: Optional[str] = ""
  cicd: CICDInfo
  route53: Route53Info
  certificatemgr: CertManagerInfo
  dbs: dict = Field(default_factory=lambda: {"rds": []})
  ecs: ECSInfo
  alb: ALBInfo
  s3: S3Info
  cloudwatch_log_groups: List[CloudWatchLogGroup] = []

aws_region = boto3.Session().region_name
sts_client = boto3.client('sts')
aws_account_id = sts_client.get_caller_identity()['Account']

codecommit = boto3.client('codecommit')
pipelines = boto3.client('codepipeline')
route53 = boto3.client('route53')
acm = boto3.client('acm')
rds = boto3.client('rds')
ecs = boto3.client('ecs')
elbv2 = boto3.client('elbv2')
s3 = boto3.client('s3')
logs = boto3.client('logs')

# Fetch data
def safe_fetch(fn, default=None):
  try:
    return fn()
  except Exception:
    return default

codecommit_repos = safe_fetch(lambda: codecommit.list_repositories()['repositories'][0]['repositoryName'], "")
pipeline_arn = safe_fetch(lambda: pipelines.list_pipelines()['pipelines'][0]['name'], "")
pipeline_status = safe_fetch(lambda: pipelines.get_pipeline_state(name=pipeline_arn)['stageStates'][0]['latestExecution']['status'], "")
last_deployment = safe_fetch(lambda: pipelines.list_pipeline_executions(pipeline_name=pipeline_arn)['pipelineExecutionSummaries'][0]['lastUpdateTime'], "")
hosted_zone = safe_fetch(lambda: route53.list_hosted_zones()['HostedZones'][0]['Id'], "")
tls_cert_arn = safe_fetch(lambda: acm.list_certificates()['CertificateSummaryList'][0]['CertificateArn'], "")
rds_arn = safe_fetch(lambda: rds.describe_db_instances()['DBInstances'][0]['DBInstanceArn'], "")

ecs_clusters = safe_fetch(lambda: ecs.list_clusters()['clusterArns'][0], "")
ecs_services = safe_fetch(lambda: ecs.list_services(cluster=ecs_clusters)['serviceArns'][0], "")
task_definition_arn = safe_fetch(lambda: ecs.describe_services(cluster=ecs_clusters, services=[ecs_services])['services'][0]['taskDefinition'], "")

alb_arn = safe_fetch(lambda: elbv2.describe_load_balancers()['LoadBalancers'][0]['LoadBalancerArn'], "")
s3_buckets = safe_fetch(lambda: [f"arn:aws:s3:::{b['Name']}" for b in s3.list_buckets()['Buckets']], [])
log_groups = safe_fetch(lambda: [{"name": lg['logGroupName'], "url": f"https://console.aws.amazon.com/cloudwatch/home?region={aws_region}#logStream:group={lg['logGroupName']}"} for lg in logs.describe_log_groups()['logGroups']], [])

# Construct JSON output
aws_info = AWSInfo(
  account_id=aws_account_id,
  region=aws_region,
  codecommit_project_url=codecommit_repos,
  cicd=CICDInfo(
    arn=pipeline_arn,
    last_deployment_timestamp=str(last_deployment),
    pipeline_status=pipeline_status
  ),
  route53=Route53Info(hostedZone=hosted_zone),
  certificatemgr=CertManagerInfo(tls_http_arn=tls_cert_arn),
  dbs={"rds": [RDSInfo(rds_arnb=rds_arn)]},
  ecs=ECSInfo(
    cluster_arn=ecs_clusters,
    service_name=ecs_services,
    task_definition_arn=task_definition_arn
  ),
  alb=ALBInfo(alb_arn=alb_arn),
  s3=S3Info(referenced_bucket_arns=s3_buckets),
  cloudwatch_log_groups=[CloudWatchLogGroup(**lg) for lg in log_groups]
)

print(aws_info.json(indent=2))
