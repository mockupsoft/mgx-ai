# -*- coding: utf-8 -*-
"""Locust load testing scenarios for the platform."""

from locust import HttpUser, task, between, tag
import random
import string


class PlatformUser(HttpUser):
    """Simulates a typical platform user."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Called when a user starts."""
        self.workspace_id = None
        self.workflow_id = None
        
        # Authenticate (if needed)
        # response = self.client.post("/api/auth/login", json={
        #     "username": "test_user",
        #     "password": "test_password"
        # })
        # self.token = response.json().get("token")
    
    @task(3)
    @tag('health')
    def health_check(self):
        """Check system health."""
        self.client.get("/health")
    
    @task(5)
    @tag('workspaces')
    def list_workspaces(self):
        """List all workspaces."""
        with self.client.get("/api/workspaces", catch_response=True) as response:
            if response.status_code == 200:
                workspaces = response.json()
                if workspaces and len(workspaces) > 0:
                    self.workspace_id = workspaces[0].get("id")
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")
    
    @task(2)
    @tag('workspaces', 'write')
    def create_workspace(self):
        """Create a new workspace."""
        name = ''.join(random.choices(string.ascii_lowercase, k=8))
        with self.client.post("/api/workspaces", json={
            "name": f"load-test-{name}",
            "description": "Created by load test"
        }, catch_response=True) as response:
            if response.status_code in [200, 201]:
                self.workspace_id = response.json().get("id")
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")
    
    @task(4)
    @tag('workflows')
    def list_workflows(self):
        """List workflows in a workspace."""
        if not self.workspace_id:
            return
        
        self.client.get(f"/api/workspaces/{self.workspace_id}/workflows")
    
    @task(2)
    @tag('workflows', 'write')
    def create_workflow(self):
        """Create a new workflow."""
        if not self.workspace_id:
            return
        
        name = ''.join(random.choices(string.ascii_lowercase, k=8))
        with self.client.post(f"/api/workspaces/{self.workspace_id}/workflows", json={
            "name": f"workflow-{name}",
            "description": "Load test workflow",
            "steps": [
                {"type": "code_generation", "config": {}},
                {"type": "validation", "config": {}},
            ]
        }, catch_response=True) as response:
            if response.status_code in [200, 201]:
                self.workflow_id = response.json().get("id")
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")
    
    @task(3)
    @tag('execution')
    def get_execution_status(self):
        """Get execution status."""
        if not self.workspace_id or not self.workflow_id:
            return
        
        self.client.get(f"/api/workspaces/{self.workspace_id}/workflows/{self.workflow_id}/executions")
    
    @task(1)
    @tag('execution', 'write')
    def trigger_execution(self):
        """Trigger workflow execution."""
        if not self.workspace_id or not self.workflow_id:
            return
        
        self.client.post(f"/api/workspaces/{self.workspace_id}/workflows/{self.workflow_id}/execute", json={
            "input": {"task": "Generate hello world function"}
        })
    
    @task(2)
    @tag('knowledge')
    def search_knowledge_base(self):
        """Search knowledge base."""
        if not self.workspace_id:
            return
        
        query = random.choice(["python", "javascript", "docker", "kubernetes", "api"])
        self.client.get(f"/api/workspaces/{self.workspace_id}/knowledge/search", params={
            "query": query,
            "limit": 10
        })
    
    @task(1)
    @tag('knowledge', 'write')
    def add_knowledge_item(self):
        """Add knowledge base item."""
        if not self.workspace_id:
            return
        
        title = ''.join(random.choices(string.ascii_lowercase, k=10))
        self.client.post(f"/api/workspaces/{self.workspace_id}/knowledge", json={
            "title": f"KB-{title}",
            "content": "Sample knowledge base content for load testing",
            "tags": ["load-test", "sample"]
        })


class AdminUser(HttpUser):
    """Simulates an admin user performing administrative tasks."""
    
    wait_time = between(2, 5)
    
    @task(2)
    @tag('admin', 'monitoring')
    def check_system_metrics(self):
        """Check system metrics."""
        self.client.get("/api/admin/metrics")
    
    @task(1)
    @tag('admin', 'monitoring')
    def view_audit_logs(self):
        """View audit logs."""
        self.client.get("/api/admin/audit-logs", params={"limit": 50})
    
    @task(1)
    @tag('admin')
    def list_users(self):
        """List all users."""
        self.client.get("/api/admin/users")
    
    @task(1)
    @tag('admin', 'cost')
    def view_cost_tracking(self):
        """View cost tracking data."""
        self.client.get("/api/admin/costs", params={"days": 7})


class HeavyUser(HttpUser):
    """Simulates heavy operations (large data, complex workflows)."""
    
    wait_time = between(5, 10)
    
    @task(1)
    @tag('heavy', 'generation')
    def generate_large_project(self):
        """Generate a large project."""
        self.client.post("/api/generator/project", json={
            "name": "large-project",
            "type": "microservices",
            "features": [
                "authentication",
                "database",
                "api",
                "frontend",
                "docker",
                "kubernetes"
            ]
        }, timeout=60)
    
    @task(1)
    @tag('heavy', 'search')
    def search_large_dataset(self):
        """Search through large knowledge base."""
        self.client.get("/api/knowledge/search", params={
            "query": "comprehensive search query",
            "limit": 100,
            "include_content": True
        }, timeout=30)
    
    @task(1)
    @tag('heavy', 'analysis')
    def analyze_codebase(self):
        """Analyze a codebase."""
        self.client.post("/api/analysis/codebase", json={
            "repository": "example/repo",
            "deep_analysis": True
        }, timeout=60)
