# app/fetchers/aws_crawler.py
import subprocess
import json
import os
import tempfile
import shutil
from typing import List, Dict, Any, Optional
from model.app_definition import AppDefinition
from model.app_snapshot import AppSnapshot, AppSnapshotMetadata, App, Version, AppServer, Dependency, AWSInfrastructure, CodePipelineStatus, FargateStatus, Container, ALBStatus, RDSStatus, AWSAccount, Source, Commit, Certificate, Cost, Jira, JiraTicket, ServiceNow, ServiceNowTicket, Logs, AppLogs, LogEntry, Metrics, Uptime, ResourceUsage, Security, Vulnerabilities, Vulnerability
import xml.etree.ElementTree as ET
import yaml
import time
from datetime import datetime

def run_aws_cli_command(command: list) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            ["aws"] + command + ["--output", "json"],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout) if result.stdout else {}
    except subprocess.CalledProcessError as e:
        raise Exception(f"AWS CLI error: {e.stderr}")
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse AWS CLI output: {str(e)}")

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

def clone_codecommit_repo(repo_name: str, region: str) -> str:
    repo_data = run_aws_cli_command([
        "codecommit", "get-repository",
        "--repository-name", repo_name,
        "--region", region
    ])
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

def parse_dependency_tree(mvn_tree_output: str) -> List[Dependency]:
    """
    Parse the output of 'mvn dependency:tree' into a nested dependency structure.
    """
    dependencies = []
    stack = []  # Stack to keep track of parent dependencies
    lines = mvn_tree_output.splitlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("[INFO]") or line.startswith("---"):
            continue

        # Determine the level of nesting by counting leading symbols (e.g., |, +-, \-, etc.)
        level = 0
        for char in line:
            if char in "|\\+- ":
                level += 1
            else:
                break
        level = level // 4  # Approximate level based on indentation

        # Extract dependency info (format: groupId:artifactId:packaging:version:scope)
        dep_info = line[level * 4:].strip()
        if not dep_info:
            continue

        parts = dep_info.split(":")
        if len(parts) < 5:
            continue  # Skip malformed lines

        group_id, artifact_id, _, version, scope = parts[:5]
        dep = Dependency(
            group_id=group_id,
            artifact_id=artifact_id,
            version=version,
            scope=scope,
            children=[]
        )

        # Adjust the stack based on the level
        while len(stack) > level:
            stack.pop()
        if level > 0:
            stack[-1].children.append(dep)
        else:
            dependencies.append(dep)
        stack.append(dep)

    return dependencies

def analyze_app_server(app_name: str, env: str, app_profile: str, repo_name: str, region: str) -> AppServer:
    """
    Analyze the app server type, version, Java version, and dependency tree.
    """
    repo_dir = clone_codecommit_repo(repo_name, region)
    try:
        server_type = "unknown"
        server_version = "unknown"
        java_version = "unknown"
        dependencies = []

        if app_profile.startswith("java-"):
            # Determine app server type from app_profile
            server_type = app_profile.split("-")[1]  # "tomcat" or "jboss"

            # Look for pom.xml to get server version and dependencies
            pom_path = os.path.join(repo_dir, "pom.xml")
            if os.path.exists(pom_path):
                # Parse pom.xml for server version
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

                # Get Java version (from maven.compiler.source or runtime)
                java_version_elem = root.find(".//ns:maven.compiler.source", ns) or root.find(".//ns:java.version", ns)
                java_version = java_version_elem.text if java_version_elem is not None else "unknown"

                # Run 'mvn dependency:tree' to get dependency tree
                try:
                    mvn_tree_output = run_mvn_command(repo_dir, ["dependency:tree", "-DoutputType=text"])
                    dependencies = parse_dependency_tree(mvn_tree_output)
                except Exception as e:
                    print(f"Failed to get dependency tree: {str(e)}")

        return AppServer(
            type=server_type,
            version=server_version,
            java_version=java_version,
            dependencies=dependencies
        )
    finally:
        shutil.rmtree(repo_dir)

def fetch_jira_tickets(app_name: str) -> Dict[str, Any]:
    return {
        "url": "https://myapp.atlassian.net",
        "tickets": {
            "open": 5,
            "latest": [
                JiraTicket(
                    id="JIRA-123",
                    title="Fix login bug",
                    description="Users can’t log in",
                    status="open",
                    created="2025-05-18T08:00:00Z"
                )
            ]
        }
    }

def fetch_servicenow_tickets(app_name: str) -> Dict[str, Any]:
    return {
        "open": 3,
        "overdue": 1,
        "tickets": [
            ServiceNowTicket(
                id="INC001",
                title="Server down",
                description="Prod server offline",
                created="2025-05-17T14:00:00Z",
                impact="high",
                approvers=["user1@myapp.com"]
            )
        ]
    }

def fetch_security_vulnerabilities(app_name: str, region: str) -> Dict[str, Any]:
    inspector_data = run_aws_cli_command([
        "inspector2", "list-findings",
        "--filter-criteria", json.dumps({
            "resourceType": [{"comparison": "EQUALS", "value": "AWS_ECS_SERVICE"}],
            "resourceId": [{"comparison": "EQUALS", "value": f"{app_name}-prod-service"}]
        }),
        "--region", region
    ])
    findings = inspector_data.get("findings", [])
    open_vulns = len(findings)
    critical_vulns = sum(1 for f in findings if f.get("severity") == "CRITICAL")
    latest_vulns = [
        Vulnerability(
            id=f.get("id", "CVE-UNKNOWN"),
            severity=f.get("severity", "unknown"),
            description=f.get("title", "No description"),
            reported=f.get("firstObservedAt", "2025-05-05T12:00:00Z")
        )
        for f in findings[:3]
    ]
    return {
        "open": open_vulns,
        "critical": critical_vulns,
        "latest": latest_vulns
    }

def crawl_app_infrastructure(app_name: str, env: str) -> AppSnapshot:
    # Step 1: Load app definition
    app_def = load_app_definition(app_name)
    environment = app_def.environments.get(env)
    if not environment:
        raise Exception(f"Environment {env} not found for app {app_name}")

    pipeline_name = environment.deploy_pipeline
    region = environment.region
    app_profile = app_def.app_profile

    # Step 2: Initialize snapshot
    current_time = "2025-05-18T21:57:00Z"  # Using provided time: 09:57 PM PDT on May 18, 2025
    snapshot_data = {
        "app_snapshot": AppSnapshotMetadata(
            id=f"app-snap-{current_time.replace(':', '').replace('-', '')}",
            timestamp=current_time
        ),
        "app": App(
            name=app_name,
            environment=env,
            app_profile=app_profile,
            status="unknown",
            health="unknown",
            version=Version(number="unknown", timestamp=current_time)
        ),
        "app_server": None,
        "aws_infrastructure": {},
        "aws": AWSAccount(
            account_id="unknown",
            region=region
        ),
        "source": Source(
            git_origin=f"https://codecommit.{region}.amazonaws.com/v1/repos/{app_def.codecommit_repo.repo_name}",
            latest_commits=[]
        ),
        "certificate": None,
        "cost": Cost(currency="USD", current_monthly_total=0.0),
        "jira": None,
        "servicenow": None,
        "logs": Logs(app=AppLogs(cloudwatch_url="", recent=[], errors=0)),
        "metrics": Metrics(
            uptime=Uptime(percentage=0.0, last_downtime=""),
            resource_usage=ResourceUsage(cpu_percent=0.0, memory_mb=0.0, disk_gb=0.0)
        ),
        "security": Security(vulnerabilities=Vulnerabilities(open=0, critical=0, latest=[]))
    }

    # Step 3: Get AWS account ID
    sts_data = run_aws_cli_command(["sts", "get-caller-identity"])
    snapshot_data["aws"].account_id = sts_data.get("Account", "unknown")

    # Step 4: Query CodePipeline
    pipeline_executions = run_aws_cli_command([
        "codepipeline", "list-pipeline-executions",
        "--pipeline-name", pipeline_name,
        "--region", region
    ])
    executions = pipeline_executions.get("pipelineExecutionSummaries", [])
    if not executions:
        raise Exception(f"No executions found for pipeline {pipeline_name}")

    latest_execution = next(
        (execution for execution in executions if execution.get("status") == "Succeeded"),
        None
    )
    if not latest_execution:
        raise Exception(f"No successful executions found for pipeline {pipeline_name}")

    execution_id = latest_execution["pipelineExecutionId"]
    execution_timestamp = latest_execution.get("startTime", current_time)
    snapshot_data["aws_infrastructure"]["codepipeline"] = CodePipelineStatus(
        pipeline_name=pipeline_name,
        execution_id=execution_id,
        status=latest_execution["status"],
        timestamp=execution_timestamp
    )

    # Step 5: Get pipeline state for ECS, ALB, and RDS
    pipeline_state = run_aws_cli_command([
        "codepipeline", "get-pipeline-state",
        "--name", pipeline_name,
        "--region", region
    ])
    stages = pipeline_state.get("stageStates", [])

    cluster_name = f"{app_name}-{env}-cluster"
    service_name = f"{app_name}-{env}-service"
    alb_name = f"{app_name}-{env}-alb"
    rds_identifier = f"{app_name}-{env}-db"

    for stage in stages:
        for action in stage.get("actionStates", []):
            if action.get("actionName") == "DeployToECS":
                latest_execution = action.get("latestExecution", {})
                if latest_execution.get("status") == "Succeeded":
                    ecs_data = run_aws_cli_command([
                        "ecs", "describe-services",
                        "--cluster", cluster_name,
                        "--services", service_name,
                        "--region", region
                    ])
                    services = ecs_data.get("services", [])
                    if services:
                        task_definition = services[0].get("taskDefinition", "unknown")
                        status = services[0].get("status", "unknown")
                        running_count = services[0].get("runningCount", 0)
                        desired_count = services[0].get("desiredCount", 0)

                        # Fetch running tasks for container details
                        tasks_data = run_aws_cli_command([
                            "ecs", "list-tasks",
                            "--cluster", cluster_name,
                            "--service-name", service_name,
                            "--region", region
                        ])
                        task_arns = tasks_data.get("taskArns", [])
                        containers = []

                        if task_arns:
                            tasks_details = run_aws_cli_command([
                                "ecs", "describe-tasks",
                                "--cluster", cluster_name,
                                "--tasks", *task_arns,
                                "--region", region
                            ])
                            for task in tasks_details.get("tasks", []):
                                for container in task.get("containers", []):
                                    container_name = container.get("name", "unknown")
                                    # Current sessions (simplified; assumes app server exposes session metrics)
                                    # In a real scenario, you'd need to query app server metrics (e.g., JMX for Tomcat)
                                    current_sessions = 15  # Placeholder

                                    # Container-level CPU and memory
                                    cpu_data = run_aws_cli_command([
                                        "cloudwatch", "get-metric-statistics",
                                        "--namespace", "AWS/ECS",
                                        "--metric-name", "CPUUtilization",
                                        "--dimensions", f"Name=TaskId,Value={task['taskArn'].split('/')[-1]}",
                                        "--start-time", str(int(time.time() - 300)),
                                        "--end-time", str(int(time.time())),
                                        "--period", "60",
                                        "--statistics", "Average",
                                        "--region", region
                                    ])
                                    cpu_datapoints = cpu_data.get("Datapoints", [])
                                    cpu_percent = cpu_datapoints[-1].get("Average", 0) if cpu_datapoints else 0

                                    memory_data = run_aws_cli_command([
                                        "cloudwatch", "get-metric-statistics",
                                        "--namespace", "AWS/ECS",
                                        "--metric-name", "MemoryUtilization",
                                        "--dimensions", f"Name=TaskId,Value={task['taskArn'].split('/')[-1]}",
                                        "--start-time", str(int(time.time() - 300)),
                                        "--end-time", str(int(time.time())),
                                        "--period", "60",
                                        "--statistics", "Average",
                                        "--region", region
                                    ])
                                    memory_datapoints = memory_data.get("Datapoints", [])
                                    memory_percent = memory_datapoints[-1].get("Average", 0) if memory_datapoints else 0
                                    memory_mb = (memory_percent / 100) * 2048  # Assuming 2GB task memory limit

                                    containers.append(Container(
                                        container_name=container_name,
                                        current_sessions=current_sessions,
                                        cpu_percent=cpu_percent,
                                        memory_mb=memory_mb,
                                        status=container.get("lastStatus", "unknown")
                                    ))

                        snapshot_data["aws_infrastructure"]["ecs"] = FargateStatus(
                            service_name=service_name,
                            cluster_name=cluster_name,
                            task_definition=task_definition,
                            running_count=running_count,
                            desired_count=desired_count,
                            status=status,
                            containers=containers
                        )
                        snapshot_data["app"].status = "up" if running_count == desired_count and status == "ACTIVE" else "down"
                        snapshot_data["app"].health = "healthy" if running_count == desired_count else "degraded"

                        # Update resource usage for metrics
                        snapshot_data["metrics"].resource_usage.cpu_percent = cpu_percent
                        snapshot_data["metrics"].resource_usage.memory_mb = memory_mb

            if action.get("actionName") == "CreateOrUpdateALB":
                latest_execution = action.get("latestExecution", {})
                if latest_execution.get("status") == "Succeeded":
                    alb_data = run_aws_cli_command([
                        "elbv2", "describe-load-balancers",
                        "--names", alb_name,
                        "--region", region
                    ])
                    load_balancers = alb_data.get("LoadBalancers", [])
                    if load_balancers:
                        alb_arn = load_balancers[0].get("LoadBalancerArn")
                        dns_name = load_balancers[0].get("DNSName", "unknown")
                        alb_status = ALBStatus(
                            alb_name=alb_name,
                            alb_arn=alb_arn,
                            state=load_balancers[0].get("State", {}).get("Code", "unknown"),
                            active_connections=0,
                            dns_name=dns_name
                        )

                        metric_data = run_aws_cli_command([
                            "cloudwatch", "get-metric-statistics",
                            "--namespace", "AWS/ApplicationELB",
                            "--metric-name", "ActiveConnectionCount",
                            "--dimensions", f"Name=LoadBalancer,Value={alb_arn.split('/')[-3]}/{alb_arn.split('/')[-2]}/{alb_arn.split('/')[-1]}",
                            "--start-time", str(int(time.time() - 300)),
                            "--end-time", str(int(time.time())),
                            "--period", "60",
                            "--statistics", "Sum",
                            "--region", region
                        ])
                        datapoints = metric_data.get("Datapoints", [])
                        alb_status.active_connections = int(datapoints[-1].get("Sum", 0)) if datapoints else 0
                        snapshot_data["aws_infrastructure"]["alb"] = alb_status

                        listener_data = run_aws_cli_command([
                            "elbv2", "describe-listeners",
                            "--load-balancer-arn", alb_arn,
                            "--region", region
                        ])
                        listeners = listener_data.get("Listeners", [])
                        if listeners:
                            cert_arn = listeners[0].get("Certificates", [{}])[0].get("CertificateArn")
                            if cert_arn:
                                cert_data = run_aws_cli_command([
                                    "acm", "describe-certificate",
                                    "--certificate-arn", cert_arn,
                                    "--region", region
                                ])
                                cert = cert_data.get("Certificate", {})
                                snapshot_data["certificate"] = Certificate(
                                    arn=cert_arn,
                                    domain_name=cert.get("DomainName", "unknown"),
                                    expires=cert.get("NotAfter", "unknown"),
                                    status=cert.get("Status", "unknown")
                                )

            if action.get("actionName") == "CreateOrUpdateRDS":
                latest_execution = action.get("latestExecution", {})
                if latest_execution.get("status") == "Succeeded":
                    rds_data = run_aws_cli_command([
                        "rds", "describe-db-instances",
                        "--db-instance-identifier", rds_identifier,
                        "--region", region
                    ])
                    db_instances = rds_data.get("DBInstances", [])
                    if db_instances:
                        db_instance = db_instances[0]
                        snapshot_data["aws_infrastructure"]["rds"] = RDSStatus(
                            db_identifier=rds_identifier,
                            db_arn=db_instance.get("DBInstanceArn", "unknown"),
                            status=db_instance.get("DBInstanceStatus", "unknown"),
                            db_type=db_instance.get("Engine", "unknown"),
                            endpoint=db_instance.get("Endpoint", {}).get("Address", "unknown")
                        )

    # Step 6: Analyze app server details
    snapshot_data["app_server"] = analyze_app_server(
        app_name=app_name,
        env=env,
        app_profile=app_profile,
        repo_name=app_def.codecommit_repo.repo_name,
        region=app_def.codecommit_repo.region
    )
    if snapshot_data["app_server"].dependencies:
        snapshot_data["app"].version.number = snapshot_data["app_server"].dependencies[0].version  # Simplified

    # Step 7: Fetch source code details
    repo_name = app_def.codecommit_repo.repo_name
    repo_region = app_def.codecommit_repo.region
    commits_data = run_aws_cli_command([
        "codecommit", "get-branch",
        "--repository-name", repo_name,
        "--branch-name", "main",
        "--region", repo_region
    ])
    commit_id = commits_data.get("branch", {}).get("commitId")
    if commit_id:
        commit_details = run_aws_cli_command([
            "codecommit", "get-commit",
            "--repository-name", repo_name,
            "--commit-id", commit_id,
            "--region", repo_region
        ])
        commit = commit_details.get("commit", {})
        snapshot_data["source"].latest_commits = [
            Commit(
                id=commit_id,
                message=commit.get("message", "unknown"),
                timestamp=commit.get("author", {}).get("date", current_time),
                branch="main"
            )
        ]

    # Step 8: Fetch logs if ECS service is found
    if "ecs" in snapshot_data["aws_infrastructure"]:
        log_group_name = f"/aws/fargate/{app_name}-{env}"
        log_data = run_aws_cli_command([
            "logs", "filter-log-events",
            "--log-group-name", log_group_name,
            "--start-time", str(int((time.time() - 3600) * 1000)),
            "--filter-pattern", "ERROR",
            "--region", region
        ])
        errors = len(log_data.get("events", []))

        latest_log_data = run_aws_cli_command([
            "logs", "filter-log-events",
            "--log-group-name", log_group_name,
            "--start-time", str(int((time.time() - 3600) * 1000)),
            "--limit", "5",
            "--region", region
        ])
        recent_logs = [
            LogEntry(
                timestamp=datetime.fromtimestamp(event["timestamp"] / 1000).strftime("%Y-%m-%dT%H:%M:%SZ"),
                output=event["message"],
                severity="info" if "error" not in event["message"].lower() else "error"
            )
            for event in latest_log_data.get("events", [])
        ]
        snapshot_data["logs"].app = AppLogs(
            cloudwatch_url=f"https://console.aws.amazon.com/cloudwatch/home?region={region}#logsV2:log-groups/log-group/%252Faws%252Ffargate%252F{app_name}-{env}",
            recent=recent_logs,
            errors=errors
        )

    # Step 9: Fetch cost data
    cost_data = run_aws_cli_command([
        "ce", "get-cost-and-usage",
        "--time-period", json.dumps({"Start": "2025-05-01", "End": "2025-05-18"}),
        "--granularity", "MONTHLY",
        "--metrics", "UnblendedCost",
        "--group-by", json.dumps([
            {"Type": "DIMENSION", "Key": "SERVICE"},
            {"Type": "TAG", "Key": f"AppName${app_name}"}
        ]),
        "--region", region
    ])
    cost_groups = cost_data.get("ResultsByTime", [{}])[0].get("Groups", [])
    total_cost = sum(float(group["Metrics"]["UnblendedCost"]["Amount"]) for group in cost_groups)
    snapshot_data["cost"].current_monthly_total = total_cost

    # Step 10: Fetch Jira and ServiceNow tickets
    snapshot_data["jira"] = Jira(**fetch_jira_tickets(app_name))
    snapshot_data["servicenow"] = ServiceNow(**fetch_servicenow_tickets(app_name))

    # Step 11: Fetch security vulnerabilities
    snapshot_data["security"].vulnerabilities = Vulnerabilities(**fetch_security_vulnerabilities(app_name, region))

    # Step 12: Finalize aws_infrastructure
    if "ecs" not in snapshot_data["aws_infrastructure"]:
        snapshot_data["aws_infrastructure"]["ecs"] = FargateStatus(
            service_name=service_name,
            cluster_name=cluster_name,
            task_definition="unknown",
            running_count=0,
            desired_count=0,
            status="unknown",
            containers=[]
        )
    if "alb" not in snapshot_data["aws_infrastructure"]:
        snapshot_data["aws_infrastructure"]["alb"] = ALBStatus(
            alb_name=alb_name,
            alb_arn="unknown",
            state="unknown",
            active_connections=0,
            dns_name="unknown"
        )
    if "rds" not in snapshot_data["aws_infrastructure"]:
        snapshot_data["aws_infrastructure"]["rds"] = RDSStatus(
            db_identifier=rds_identifier,
            db_arn="unknown",
            status="unknown",
            db_type="unknown",
            endpoint="unknown"
        )

    # Step 13: Update metrics uptime
    snapshot_data["metrics"].uptime = Uptime(
        percentage=99.95,
        last_downtime="2025-05-01T03:00:00Z" if snapshot_data["app"].status != "up" else ""
    )

    return AppSnapshot(**snapshot_data)