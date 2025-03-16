import pytest
from fastapi.testclient import TestClient
from app.main import app, get_fargate_metrics
from unittest.mock import patch

# Create a TestClient instance for FastAPI
client = TestClient(app)

# Sample mock data to simulate AWS responses
mock_aws_response = {
  "app1-service": {"CPU": 32.5, "Memory": 65.4},
  "app2-service": {"CPU": 40.2, "Memory": 72.1},
}

# Unit Test for fetch_fargate_metrics
def test_fetch_fargate_metrics(mocker):
  # Mock the AWS SDK calls
  mock_list_services = mocker.patch("app.main.ecs.list_services")
  mock_get_metric_statistics = mocker.patch("app.main.cloudwatch.get_metric_statistics")

  # Define the mock return values for these AWS SDK calls
  mock_list_services.return_value = {"serviceArns": ["app1-service", "app2-service"]}

  mock_get_metric_statistics.return_value = {
    "Datapoints": [
      {"Average": 32.5},  # CPU Utilization for app1
      {"Average": 65.4},  # Memory Utilization for app1
      {"Average": 40.2},  # CPU Utilization for app2
      {"Average": 72.1},  # Memory Utilization for app2
    ]
  }

  # Call the FastAPI route to test
  response = client.get("/metrics")

  # Assert that the response is correct
  assert response.status_code == 200
  assert "metrics" in response.json()
  assert "app1-service" in response.json()["metrics"]
  assert "app2-service" in response.json()["metrics"]

  # Check that the mock response data matches the expected structure
  assert response.json()["metrics"]["app1-service"]["CPU"] == 32.5
  assert response.json()["metrics"]["app1-service"]["Memory"] == 65.4
  assert response.json()["metrics"]["app2-service"]["CPU"] == 40.2
  assert response.json()["metrics"]["app2-service"]["Memory"] == 72.1
