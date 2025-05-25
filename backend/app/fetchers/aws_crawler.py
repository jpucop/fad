# app/fetchers/aws_crawler.py
import boto3
import os
import tempfile
import shutil
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, Any, List
from datetime import datetime, timedelta
from model.app_definition import AppDefinition
from model.app_snapshot import AppSnapshot
from app.fetchers.transform import transform_app_snapshot

# In-memory cache for snapshots
SNAPSHOT_CACHE: Dict[str, Dict[str, Any]] = {}

# Initialize boto3 clients
sts_client = boto3.client("sts")
codecommit_client = boto3.client("codecommit")
codepipeline_client = boto3.client("codepipeline")
ecs_client = boto3.client("ecs")
cloudwatch_client = boto3.client("cloudwatch")
elbv2_client = boto3.client("elbv2")
acm_client = boto3.client("acm")
rds_client = boto3.client("rds")
ce_client = boto3.client("ce")
s3_client = boto3.client("s3")
logs_client = boto3.client("logs")
inspector_client = boto3.client("inspector2")

def run_mvn_command(repo_dir: str, command: list) -> str:
    try:
        result = subprocess.run(
            ["mvn"] + command,
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise Exception(f"Maven command error: {e.stderr}")

def load_app_definition(app_name: str) -> AppDefinition:
    file_path = f"backend/model/ucop-finapps/init/app_{app_name}.json"
    if not os.path.exists(file_path):
        raise Exception(f"App definition file for {app_name} not found")
    
    with open(file_path, "r") as f:
        data = json.load(f)
    return AppDefinition(**data)

def get_cached_snapshot(app_name: str, env: str) -> Dict[str, Any]:
    return SNAPSHOT_CACHE.get(f"{app_name}#{env}", {})

def update_cached_snapshot(app_name: str, env: str, snapshot: Dict[str, Any]):
    SNAPSHOT_CACHE[f"{app_name}#{env}"] = snapshot

def should_fetch_section(section_path: str, config: Dict[str, bool], last_updated: Dict[str, str], current_time: str) -> bool:
    if not config.get(section_path, False):
        return False
    last_updated_time = last_updated.get(section_path, "1970-01-01T00:00:00Z")
    last_updated_dt = datetime.strptime(last_updated_time, "%Y-%m-%dT%H:%M:%SZ")
    current_dt = datetime.strptime(current_time, "%Y-%m-%dT%H:%M:%SZ")
    # Fetch if data is older than 5 minutes
    return (current_dt - last_updated_dt).total_seconds() > 300

def clone_codecommit_repo(repo_name: str, region: str) -> str:
    repo_data = codecommit_client.get_repository(repositoryName=repo_name)
    clone_url = repo_data.get("repositoryMetadata", {}).get("cloneUrlHttp")
    if not clone_url:
        raise Exception(f"Clone URL not found for repository {repo_name}")

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

def parse_dependency_tree(mvn_tree_output: str) -> List[Dict[str, Any]]:
    dependencies = []
    stack = []
    lines = mvn_tree_output.splitlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("[INFO]") or line.startswith("---"):
            continue

        level = 0
        for char in line:
            if char in "|\\+- ":
                level += 1
            else:
                break
        level = level // 4

        dep_info = line[level * 4:].strip()
        if not dep_info:
            continue

        parts = dep_info.split(":")
        if len(parts) < 5:
            continue

        group_id, artifact_id, _, version, scope = parts[:5]
        dep = {"group_id": group_id, "artifact_id": artifact_id, "version": version, "scope": scope, "children": []}

        while len(stack) > level:
            stack.pop()
        if level > 0:
            stack[-1]["children"].append(dep)
        else:
            dependencies.append(dep)
        stack.append(dep)

    return dependencies

def analyze_app_server(app_name: str, env: str, app_profile: str, repo_name: str, region: str) -> Dict[str, Any]:
    repo_dir = clone_codecommit_repo(repo_name, region)
    try:
        server_type = "unknown"
        server_version = "unknown"
        java_version = "unknown"
        dependencies = []

        if app_profile.startswith("java-"):
            server_type = app_profile.split("-")[1]

            pom_path = os.path.join(repo_dir, "pom.xml")
            if os.path.exists(pom_path):
                tree = ET.parse(pom_path)
                root = tree.getroot()
                ns = {"ns": "http://maven.apache.org/POM/4.0.0"}

                for dep in root.findall(".//ns:dependency", ns):
                    group_id = dep.find("ns:groupId", ns).text if dep.find("ns:groupId", ns) is not None else ""
                    artifact_id = dep.find("ns:artifactId", ns).text if dep.find("ns:artifactId", ns) is not None else ""
                    version = dep.find("ns:version", ns).text if dep.find("ns:version", ns) is not None else "unknown"

                    if server_type == "tomcat" and "tomcat" in artifact_id.lower():
                        server_version = version
                    elif server_type == "jboss" and "jboss" in artifact_id.lower():
                        server_version = version

                java_version_elem = root.find(".//ns:maven.compiler.source", ns) or root.find(".//ns:java.version", ns)
                java_version = java_version_elem.text if java_version_elem is not None else "unknown"

                try:
                    mvn_tree_output = run_mvn_command(repo_dir, ["dependency:tree", "-DoutputType=text"])
                    dependencies = parse_dependency_tree(mvn_tree_output)
                except Exception as e:
                    print(f"Failed to get dependency tree: {str(e)}")

        return {
            "server_type": server_type,
            "server_version": server_version,
            "java_version": java_version,
            "dependencies": dependencies
        }
    finally:
        shutil.rmtree(repo_dir)

def fetch_jira_tickets(app_name: str) -> Dict[str, Any]:
    return {
        "url": "https://myapp.atlassian.net",
        "tickets": {
            "open": 5,
            "latest": [
                {
                    "id": "JIRA-123",
                    "title": "Fix login bug",
                    "description": "Users can’t log in",
                    "status": "open",
                    "created": "2025-05-18T08:00:00Z"
                }
            ]
        }
    }

def fetch_servicenow_tickets(app_name: str) -> Dict[str, Any]:
    return {
        "open": 3,
        "overdue": 1,
        "tickets": [
            {
                "id": "INC001",
                "title": "Server down",
                "description": "Prod server offline",
                "created": "2025-05-17T14:00:00Z",
                "impact": "high",
                "approvers": ["user1@myapp.com"]
            }
        ]
    }

def fetch_security_vulnerabilities(app_name: str, region: str) -> Dict[str, Any]:
    findings = inspector_client.list_findings(
        filterCriteria={
            "resourceType": [{"comparison": "EQUALS", "value": "AWS_ECS_SERVICE"}],
            "resourceId": [{"comparison": "EQUALS", "value": f"{app_name}-prod-service"}]
        }
    ).get("findings", [])
    open_vulns = len(findings)
    critical_vulns = sum(1 for f in findings if f.get("severity") == "CRITICAL")
    latest_vulns = [
        {
            "id": f.get("id", "CVE-UNKNOWN"),
            "severity": f.get("severity", "unknown"),
            "description": f.get("title", "No description"),
            "reported": f.get("firstObservedAt", "2025-05-05T12:00:00Z")
        }
        for f in findings[:3]
    ]
    return {
        "open": open_vulns,
        "critical": critical_vulns,
        "latest": latest_vulns
    }

def crawl_app_infrastructure(app_name: str, env: str, config: Dict[str, bool]) -> AppSnapshot:
    """
    Publicly visible function to crawl app infrastructure data with event-driven updates.
    Uses boto3 SDK instead of AWS CLI, stores snapshots in memory.
    
    Args:
        app_name (str): Name of the app.
        env (str): Environment (e.g., "prod").
        config (Dict[str, bool]): Configuration specifying which subsections to fetch.
            Example: {"source": true, "aws_infrastructure.ecs": true, "logs.app": true}
    
    Returns:
        AppSnapshot: The updated app snapshot.
    """
    app_def = load_app_definition(app_name)
    environment = app_def.environments.get(env)
    if not environment:
        raise Exception(f"Environment {env} not found for app {app_name}")

    pipeline_name = environment.deploy_pipeline
    region = environment.region
    app_profile = app_def.app_profile
    repo_name = app_def.codecommit_repo.repo_name
    repo_region = app_def.codecommit_repo.region
    current_time = "2025-05-19T01:29:00Z"  # Current time: 01:29 AM PDT on May 19, 2025

    # Load cached snapshot from memory
    cached_snapshot = get_cached_snapshot(app_name, env)
    last_updated = cached_snapshot.get("app_snapshot", {}).get("last_updated", {
        "source": "1970-01-01T00:00:00Z",
        "aws": "1970-01-01T00:00:00Z",
        "logs": "1970-01-01T00:00:00Z",
        "jira": "1970-01-01T00:00:00Z",
        "servicenow": "1970-01-01T00:00:00Z",
        "security": "1970-01-01T00:00:00Z"
    })

    # Initialize raw data for transformation
    raw_data = {
        "app_server_data": {},
        "codepipeline_execution": {},
        "ecs_service": {},
        "ecs_tasks": [],
        "alb_data": {},
        "alb_metrics": {},
        "cert_data": {},
        "rds_data": {},
        "codecommit_commit": {},
        "logs_data": {"firewall_loadbalancer": {}, "sso": {}, "app": {}},
        "latest_logs_data": {"firewall_loadbalancer": {}, "sso": {}, "app": {}},
        "cpu_data": {},
        "memory_data": {},
        "cost_data": {},
        "jira_data": {},
        "servicenow_data": {},
        "security_data": {},
        "account_data": {},
        "trusted_advisor_data": {},
        "s3_data": {}
    }

    # Fetch app server data if needed
    if should_fetch_section("app_server", config, last_updated, current_time):
        raw_data["app_server_data"] = analyze_app_server(app_name, env, app_profile, repo_name, repo_region)
        last_updated["app_server"] = current_time

    # Fetch source data (CodeCommit)
    if should_fetch_section("source", config, last_updated, current_time):
        commits_data = codecommit_client.get_branch(
            repositoryName=repo_name,
            branchName="main"
        )
        commit_id = commits_data.get("branch", {}).get("commitId")
        raw_data["codecommit_commit"] = codecommit_client.get_commit(
            repositoryName=repo_name,
            commitId=commit_id
        ) if commit_id else {}
        last_updated["source"] = current_time

    # Fetch AWS infrastructure data
    if should_fetch_section("aws_infrastructure", config, last_updated, current_time):
        raw_data["account_data"] = sts_client.get_caller_identity()
        last_updated["aws"] = current_time

        # CodePipeline
        if should_fetch_section("aws_infrastructure.codepipeline", config, last_updated, current_time):
            pipeline_executions = codepipeline_client.list_pipeline_executions(
                pipelineName=pipeline_name
            )
            latest_execution = next(
                (execution for execution in pipeline_executions.get("pipelineExecutionSummaries", []) if execution.get("status") == "Succeeded"),
                None
            )
            if latest_execution:
                execution_id = latest_execution["pipelineExecutionId"]
                raw_data["codepipeline_execution"] = codepipeline_client.get_pipeline_execution(
                    pipelineName=pipeline_name,
                    pipelineExecutionId=execution_id
                )

        # ECS
        cluster_name = f"{app_name}-{env}-cluster"
        service_name = f"{app_name}-{env}-service"
        if should_fetch_section("aws_infrastructure.ecs", config, last_updated, current_time):
            raw_data["ecs_service"] = ecs_client.describe_services(
                cluster=cluster_name,
                services=[service_name]
            )
            tasks_data = ecs_client.list_tasks(
                cluster=cluster_name,
                serviceName=service_name
            )
            task_arns = tasks_data.get("taskArns", [])
            if task_arns:
                raw_data["ecs_tasks"] = ecs_client.describe_tasks(
                    cluster=cluster_name,
                    tasks=task_arns
                ).get("tasks", [])

            # CloudWatch metrics for ECS
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=5)
            raw_data["cpu_data"] = cloudwatch_client.get_metric_statistics(
                Namespace="AWS/ECS",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "ServiceName", "Value": service_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=60,
                Statistics=["Average"]
            )
            raw_data["memory_data"] = cloudwatch_client.get_metric_statistics(
                Namespace="AWS/ECS",
                MetricName="MemoryUtilization",
                Dimensions=[{"Name": "ServiceName", "Value": service_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=60,
                Statistics=["Average"]
            )

        # ALB
        alb_name = f"{app_name}-{env}-alb"
        if should_fetch_section("aws_infrastructure.alb", config, last_updated, current_time):
            raw_data["alb_data"] = elbv2_client.describe_load_balancers(Names=[alb_name])
            alb_arn = raw_data["alb_data"].get("LoadBalancers", [{}])[0].get("LoadBalancerArn", "unknown")
            raw_data["alb_metrics"] = cloudwatch_client.get_metric_statistics(
                Namespace="AWS/ApplicationELB",
                MetricName="ActiveConnectionCount",
                Dimensions=[
                    {
                        "Name": "LoadBalancer",
                        "Value": f"{alb_arn.split('/')[-3]}/{alb_arn.split('/')[-2]}/{alb_arn.split('/')[-1]}"
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=60,
                Statistics=["Sum"]
            )
            listener_data = elbv2_client.describe_listeners(LoadBalancerArn=alb_arn)
            cert_arn = listener_data.get("Listeners", [{}])[0].get("Certificates", [{}])[0].get("CertificateArn", "unknown")
            raw_data["cert_data"] = acm_client.describe_certificate(CertificateArn=cert_arn) if cert_arn else {}

        # RDS
        rds_identifier = f"{app_name}-{env}-db"
        if should_fetch_section("aws_infrastructure.rds", config, last_updated, current_time):
            raw_data["rds_data"] = rds_client.describe_db_instances(DBInstanceIdentifier=rds_identifier)

        # Cost
        if should_fetch_section("aws_infrastructure.cost", config, last_updated, current_time):
            raw_data["cost_data"] = ce_client.get_cost_and_usage(
                TimePeriod={"Start": "2025-05-01", "End": "2025-05-19"},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                GroupBy=[
                    {"Type": "DIMENSION", "Key": "SERVICE"},
                    {"Type": "TAG", "Key": f"AppName${app_name}"}
                ]
            )

        # Trusted Advisor (simplified)
        if should_fetch_section("aws_infrastructure.trusted_advisor", config, last_updated, current_time):
            raw_data["trusted_advisor_data"] = {
                "checks": [
                    {
                        "id": "check-001",
                        "name": "High Utilization",
                        "status": "warning",
                        "description": "ECS service has high CPU usage"
                    }
                ]
            }

        # S3
        if should_fetch_section("aws_infrastructure.s3", config, last_updated, current_time):
            buckets = s3_client.list_buckets()
            s3_buckets = []
            for bucket in buckets.get("Buckets", []):
                if bucket["Name"].startswith(f"{app_name}-{env}"):
                    s3_buckets.append({
                        "name": bucket["Name"],
                        "arn": f"arn:aws:s3:::{bucket['Name']}",
                        "size_mb": 2048,  # Placeholder
                        "last_modified": "2025-05-18T08:00:00Z"
                    })
            raw_data["s3_data"] = {"buckets": s3_buckets}

    # Fetch logs (CloudWatch Logs)
    if should_fetch_section("logs", config, last_updated, current_time):
        log_sections = ["firewall_loadbalancer", "sso", "app"]
        for section in log_sections:
            if should_fetch_section(f"logs.{section}", config, last_updated, current_time):
                log_group_name = f"/aws/{'alb' if section == 'firewall_loadbalancer' else 'fargate'}/{app_name}-{env}{'-sso' if section == 'sso' else ''}"
                start_time = int((datetime.utcnow() - timedelta(hours=1)).timestamp() * 1000)
                raw_data["logs_data"][section] = logs_client.filter_log_events(
                    logGroupName=log_group_name,
                    startTime=start_time,
                    filterPattern="ERROR"
                )
                raw_data["latest_logs_data"][section] = logs_client.filter_log_events(
                    logGroupName=log_group_name,
                    startTime=start_time,
                    limit=5
                )
        last_updated["logs"] = current_time

    # Fetch Jira, ServiceNow, and Security
    if should_fetch_section("jira", config, last_updated, current_time):
        raw_data["jira_data"] = fetch_jira_tickets(app_name)
        last_updated["jira"] = current_time
    if should_fetch_section("servicenow", config, last_updated, current_time):
        raw_data["servicenow_data"] = fetch_servicenow_tickets(app_name)
        last_updated["servicenow"] = current_time
    if should_fetch_section("security", config, last_updated, current_time):
        raw_data["security_data"] = fetch_security_vulnerabilities(app_name, region)
        last_updated["security"] = current_time

    # Transform and update snapshot
    app_version = raw_data["app_server_data"].get("dependencies", [{}])[0].get("version", "unknown") if raw_data["app_server_data"].get("dependencies") else "unknown"
    snapshot = transform_app_snapshot(
        app_name=app_name,
        env=env,
        app_profile=app_profile,
        snapshot_time=current_time,
        app_version=app_version,
        last_updated=last_updated,
        app_server_data=raw_data["app_server_data"],
        codepipeline_execution=raw_data["codepipeline_execution"],
        ecs_service=raw_data["ecs_service"],
        ecs_tasks=raw_data["ecs_tasks"],
        alb_data=raw_data["alb_data"],
        alb_metrics=raw_data["alb_metrics"],
        cert_data=raw_data["cert_data"],
        rds_data=raw_data["rds_data"],
        codecommit_commit=raw_data["codecommit_commit"],
        logs_data=raw_data["logs_data"],
        latest_logs_data=raw_data["latest_logs_data"],
        cpu_data=raw_data["cpu_data"],
        memory_data=raw_data["memory_data"],
        cost_data=raw_data["cost_data"],
        jira_data=raw_data["jira_data"],
        servicenow_data=raw_data["servicenow_data"],
        security_data=raw_data["security_data"],
        account_data=raw_data["account_data"],
        trusted_advisor_data=raw_data["trusted_advisor_data"],
        s3_data=raw_data["s3_data"],
        repo_name=repo_name,
        repo_region=repo_region
    )

    # Update cached snapshot in memory
    update_cached_snapshot(app_name, env, snapshot.dict())
    return snapshot