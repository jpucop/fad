import boto3
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
import requests
from datetime import datetime, timedelta
from typing import List

app = FastAPI()

templates = Jinja2Templates(directory="app/templates")

# AWS Configuration
AWS_REGION = "us-west-2"  # Change to your AWS region
CLUSTER_NAME = "your-cluster-name"

# Initialize AWS clients
cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)
ecs = boto3.client("ecs", region_name=AWS_REGION)

DATADOG_API_KEY = "your_datadog_api_key"
DATADOG_APP_KEY = "your_datadog_app_key"

def get_aws_ecs_metrics():
  headers = {"DD-API-KEY": DATADOG_API_KEY, "DD-APPLICATION-KEY": DATADOG_APP_KEY}
  response = requests.get("https://api.datadoghq.com/api/v1/query?query=avg:aws.ecs.running_tasks", headers=headers)
  return response.json()

@app.get("/")
def dashboard(request: Request):
  ecs_data = get_aws_ecs_metrics()
  return templates.TemplateResponse("dashboard.html", {"request": request, "ecs_data": ecs_data})


def get_fargate_metrics(service_names: List[str]):
  """
  Fetches CPU & Memory utilization for given AWS Fargate services in an ECS cluster.
  """
  end_time = datetime.utcnow()
  start_time = end_time - timedelta(minutes=10)  # Last 10 minutes

  metrics = {}

  for service in service_names:
    namespace = "AWS/ECS"

    # Fetch CPU Utilization
    cpu_response = cloudwatch.get_metric_statistics(
      Namespace=namespace,
      MetricName="CPUUtilization",
      Dimensions=[
        {"Name": "ClusterName", "Value": CLUSTER_NAME},
        {"Name": "ServiceName", "Value": service},
      ],
      StartTime=start_time,
      EndTime=end_time,
      Period=300,
      Statistics=["Average"],
      Unit="Percent",
    )

    # Fetch Memory Utilization
    memory_response = cloudwatch.get_metric_statistics(
      Namespace=namespace,
      MetricName="MemoryUtilization",
      Dimensions=[
        {"Name": "ClusterName", "Value": CLUSTER_NAME},
        {"Name": "ServiceName", "Value": service},
      ],
      StartTime=start_time,
      EndTime=end_time,
      Period=300,
      Statistics=["Average"],
      Unit="Percent",
    )

    metrics[service] = {
      "CPU": cpu_response.get("Datapoints", [{}])[-1].get("Average", 0),
      "Memory": memory_response.get("Datapoints", [{}])[-1].get("Average", 0),
    }

  return metrics

@app.get("/metrics")
def fetch_fargate_metrics():
  """
  Fetches metrics for all running ECS services in the given cluster.
  """
  response = ecs.list_services(cluster=CLUSTER_NAME)
  service_arns = response.get("serviceArns", [])

  # Extract service names
  service_names = [arn.split("/")[-1] for arn in service_arns]

  metrics_data = get_fargate_metrics(service_names)
  
  return {"timestamp": datetime.utcnow().isoformat(), "metrics": metrics_data}
