"""Locust stress test for AuditBee API.

Usage:
    locust -f scripts/locustfile.py --host=http://localhost:8000

Then open http://localhost:8089 to configure and run the test.
"""

from locust import HttpUser, task, between


class AuditBeeUser(HttpUser):
    wait_time = between(1, 3)

    @task(5)
    def health_check(self):
        """Lightweight health check — baseline throughput."""
        self.client.get("/api/health")

    @task(3)
    def list_tasks(self):
        """List audit tasks with pagination."""
        self.client.get("/api/audit/tasks?page=1&page_size=20")

    @task(3)
    def list_documents(self):
        """List uploaded documents."""
        self.client.get("/api/documents/?page=1&page_size=20")

    @task(2)
    def get_config(self):
        """Get all config entries."""
        self.client.get("/api/config/")

    @task(2)
    def get_alerts(self):
        """List risk alerts."""
        self.client.get("/api/alerts/?page=1&page_size=20")

    @task(2)
    def list_reports(self):
        """List reports."""
        self.client.get("/api/reports/?page=1&page_size=20")

    @task(1)
    def kg_status(self):
        """Check knowledge graph status."""
        self.client.get("/api/kg/status")

    @task(1)
    def get_task_detail(self):
        """Get a specific task detail (task_id=1 assumed to exist)."""
        self.client.get("/api/audit/tasks/1")
