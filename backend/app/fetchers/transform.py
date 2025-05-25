# app/fetchers/transform.py
from typing import List, Dict, Any
from datetime import datetime
from model.app_snapshot import (
  AppSnapshot, SnapshotMetadata, AppDefinition, Version, Source, AppServer, Dependency,
  AWSInfrastructure, CodePipelineStatus, FargateStatus, Container, ALBStatus, Certificate,
  CertificateAWS, RDSStatus, AWSAccount, Cost, TrustedAdvisor, TrustedAdvisorCheck, S3, S3Bucket,
  Logs, LogSection, LogEntry, Jira, JiraTicket, ServiceNow, ServiceNowTicket, Security, Vulnerabilities, Vulnerability
)

def transform_app_snapshot(
  app_name: str,
  env: str,
  app_profile: str,
  snapshot_time: str,
  app_version: str,
  last_updated: Dict[str, str],
  app_server_data: Dict[str, Any],
  codepipeline_execution: Dict[str, Any],
  ecs_service: Dict[str, Any],
  ecs_tasks: List[Dict[str, Any]],
  alb_data: Dict[str, Any],
  alb_metrics: Dict[str, Any],
  cert_data: Dict[str, Any],
  rds_data: Dict[str, Any],
  codecommit_commit: Dict[str, Any],
  logs_data: Dict[str, Any],
  latest_logs_data: Dict[str, Any],
  cpu_data: Dict[str, Any],
  memory_data: Dict[str, Any],
  cost_data: Dict[str, Any],
  jira_data: Dict[str, Any],
  servicenow_data: Dict[str, Any],
  security_data: Dict[str, Any],
  account_data: Dict[str, Any],
  trusted_advisor_data: Dict[str, Any],
  s3_data: Dict[str, Any],
  repo_name: str,
  repo_region: str
) -> AppSnapshot:
  running_count = ecs_service.get("services", [{}])[0].get("runningCount", 0) if ecs_service.get("services") else 0
  desired_count = ecs_service.get("services", [{}])[0].get("desiredCount", 0) if ecs_service.get("services") else 0
  status = ecs_service.get("services", [{}])[0].get("status", "unknown") if ecs_service.get("services") else "unknown"
  app_status = "up" if running_count == desired_count and status == "ACTIVE" else "down"
  app_health = "healthy" if running_count == desired_count else "degraded"

  containers = []
  for task in ecs_tasks:
    for container in task.get("containers", []):
      container_name = container.get("name", "unknown")
      cpu_percent = cpu_data.get("Datapoints", [{}])[-1].get("Average", 0) if cpu_data.get("Datapoints") else 0
      memory_percent = memory_data.get("Datapoints", [{}])[-1].get("Average", 0) if memory_data.get("Datapoints") else 0
      memory_mb = (memory_percent / 100) * 2048
      containers.append(Container(
        container_name=container_name,
        current_sessions=15 if container_name == "myapp-container" else 10,  # Placeholder
        cpu_percent=cpu_percent,
        memory_mb=memory_mb,
        status=container.get("lastStatus", "unknown")
      ))

  return AppSnapshot(
    app_snapshot=SnapshotMetadata(
      snapshot_id=f"app-snap-{snapshot_time.replace(':', '').replace('-', '')}",
      timestamp=snapshot_time,
      last_updated=last_updated
    ),
    app_definition=AppDefinition(
      app_name=app_name,
      environment=env,
      app_profile=app_profile,
      deploy_profile="cicd-fargate-alb-rds",
      status=app_status,
      health=app_health,
      version=Version(
        number=app_version,
        timestamp=snapshot_time
      )
    ),
    source=Source(
      project_name=repo_name,
      branch_name="main",
      git_origin_url=f"https://codecommit.{repo_region}.amazonaws.com/v1/repos/{repo_name}",
      latest_commits=[
        {
          "commit_id": codecommit_commit.get("commit", {}).get("commitId", "unknown"),
          "message": codecommit_commit.get("commit", {}).get("message", "unknown"),
          "timestamp": codecommit_commit.get("commit", {}).get("author", {}).get("date", snapshot_time),
          "branch": "main"
        }
      ]
    ),
    app_server=AppServer(
      server_type=app_server_data.get("server_type", "unknown"),
      server_version=app_server_data.get("server_version", "unknown"),
      java_version=app_server_data.get("java_version", "unknown"),
      dependencies=[
        Dependency(
          group_id=dep["group_id"],
          artifact_id=dep["artifact_id"],
          version=dep["version"],
          scope=dep["scope"],
          children=[
            Dependency(
              group_id=child["group_id"],
              artifact_id=child["artifact_id"],
              version=child["version"],
              scope=child["scope"],
              children=[]
            ) for child in dep["children"]
          ]
        ) for dep in app_server_data.get("dependencies", [])
      ]
    ),
    aws_infrastructure=AWSInfrastructure(
      account=AWSAccount(
        account_id=account_data.get("Account", "unknown"),
        account_name="myapp-account",
        region=repo_region
      ),
      codepipeline=CodePipelineStatus(
        pipeline_name=codepipeline_execution.get("pipelineExecution", {}).get("pipelineName", "unknown"),
        execution_id=codepipeline_execution.get("pipelineExecution", {}).get("pipelineExecutionId", "unknown"),
        status=codepipeline_execution.get("pipelineExecution", {}).get("status", "unknown"),
        timestamp=codepipeline_execution.get("pipelineExecution", {}).get("startTime", snapshot_time)
      ),
      ecs=FargateStatus(
        service_name=ecs_service.get("services", [{}])[0].get("serviceName", f"{app_name}-{env}-service"),
        cluster_name=ecs_service.get("services", [{}])[0].get("clusterArn", f"{app_name}-{env}-cluster").split("/")[-1],
        task_definition=ecs_service.get("services", [{}])[0].get("taskDefinition", "unknown"),
        running_count=running_count,
        desired_count=desired_count,
        status=status,
        containers=containers
      ),
      alb=ALBStatus(
        alb_name=alb_data.get("LoadBalancers", [{}])[0].get("LoadBalancerName", f"{app_name}-{env}-alb"),
        alb_arn=alb_data.get("LoadBalancers", [{}])[0].get("LoadBalancerArn", "unknown"),
        state=alb_data.get("LoadBalancers", [{}])[0].get("State", {}).get("Code", "unknown"),
        active_connections=int(alb_metrics.get("Datapoints", [{}])[-1].get("Sum", 0)) if alb_metrics.get("Datapoints") else 0,
        dns_name=alb_data.get("LoadBalancers", [{}])[0].get("DNSName", "unknown"),
        certificate=Certificate(
          domain_name=cert_data.get("Certificate", {}).get("DomainName", "unknown"),
          expires=cert_data.get("Certificate", {}).get("NotAfter", "unknown"),
          status=cert_data.get("Certificate", {}).get("Status", "unknown"),
          aws=CertificateAWS(
            arn=cert_data.get("Certificate", {}).get("CertificateArn", "unknown"),
            tags=[{"key": "Environment", "value": "prod"}]
          )
        )
      ),
      rds=RDSStatus(
        db_identifier=rds_data.get("DBInstances", [{}])[0].get("DBInstanceIdentifier", f"{app_name}-{env}-db"),
        db_arn=rds_data.get("DBInstances", [{}])[0].get("DBInstanceArn", "unknown"),
        status=rds_data.get("DBInstances", [{}])[0].get("DBInstanceStatus", "unknown"),
        db_type=rds_data.get("DBInstances", [{}])[0].get("Engine", "unknown"),
        db_version=rds_data.get("DBInstances", [{}])[0].get("EngineVersion", "unknown"),
        endpoint=rds_data.get("DBInstances", [{}])[0].get("Endpoint", {}).get("Address", "unknown"),
        tags=[{"key": "Environment", "value": "prod"}]
      ),
      cost=Cost(
        currency="USD",
        current_monthly_total=sum(float(group["Metrics"]["UnblendedCost"]["Amount"]) for group in cost_data.get("ResultsByTime", [{}])[0].get("Groups", []))
      ),
      trusted_advisor=TrustedAdvisor(
        checks=[
          TrustedAdvisorCheck(
            id=check["id"],
            name=check["name"],
            status=check["status"],
            description=check["description"]
          ) for check in trusted_advisor_data.get("checks", [])
        ]
      ),
      s3=S3(
        buckets=[
          S3Bucket(
            name=bucket["name"],
            arn=bucket["arn"],
            size_mb=bucket["size_mb"],
            last_modified=bucket["last_modified"]
          ) for bucket in s3_data.get("buckets", [])
        ]
      )
    ),
    logs=Logs(
      firewall_loadbalancer=LogSection(
        cloudwatch_url=f"https://console.aws.amazon.com/cloudwatch/home?region={repo_region}#logsV2:log-groups/log-group/%252Faws%252Falb%252F{app_name}-{env}",
        recent=[
          LogEntry(
            timestamp=datetime.fromtimestamp(event["timestamp"] / 1000).strftime("%Y-%m-%dT%H:%M:%SZ"),
            output=event["message"],
            severity="info" if "error" not in event["message"].lower() else "error"
          ) for event in latest_logs_data.get("firewall_loadbalancer", {}).get("events", [])
        ],
        errors=len(logs_data.get("firewall_loadbalancer", {}).get("events", []))
      ),
      sso=LogSection(
        cloudwatch_url=f"https://console.aws.amazon.com/cloudwatch/home?region={repo_region}#logsV2:log-groups/log-group/%252Faws%252Ffargate%252F{app_name}-{env}-sso",
        recent=[
          LogEntry(
            timestamp=datetime.fromtimestamp(event["timestamp"] / 1000).strftime("%Y-%m-%dT%H:%M:%SZ"),
            output=event["message"],
            severity="info" if "error" not in event["message"].lower() else "error"
          ) for event in latest_logs_data.get("sso", {}).get("events", [])
        ],
        errors=len(logs_data.get("sso", {}).get("events", []))
      ),
      app=LogSection(
        cloudwatch_url=f"https://console.aws.amazon.com/cloudwatch/home?region={repo_region}#logsV2:log-groups/log-group/%252Faws%252Ffargate%252F{app_name}-{env}",
        recent=[
          LogEntry(
            timestamp=datetime.fromtimestamp(event["timestamp"] / 1000).strftime("%Y-%m-%dT%H:%M:%SZ"),
            output=event["message"],
            severity="info" if "error" not in event["message"].lower() else "error"
          ) for event in latest_logs_data.get("app", {}).get("events", [])
        ],
        errors=len(logs_data.get("app", {}).get("events", []))
      )
    ),
    jira=Jira(**jira_data),
    servicenow=ServiceNow(**servicenow_data),
    security=Security(vulnerabilities=Vulnerabilities(**security_data))
  )