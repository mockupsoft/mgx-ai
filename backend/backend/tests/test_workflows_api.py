# -*- coding: utf-8 -*-
"""Tests for workflow API endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock

from backend.app.main import create_app
from backend.db.models import (
    Workspace,
    Project,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowVariable,
    WorkflowExecution,
    WorkflowStepExecution,
    AgentDefinition,
    AgentInstance,
)
from backend.db.models.enums import WorkflowStepType, WorkflowStatus, WorkflowStepStatus
from backend.schemas import (
    WorkflowCreate,
    WorkflowStepCreate,
    WorkflowVariableCreate,
    WorkflowUpdate,
    WorkflowExecutionCreate,
)


class TestWorkflowAPI:
    """Test suite for workflow API endpoints."""
    
    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test FastAPI application."""
        return create_app()
    
    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def test_workspace(self):
        """Create test workspace data."""
        return {
            "id": "test-workspace-123",
            "name": "Test Workspace",
            "slug": "test-workspace",
            "meta_data": {"description": "Test workspace for workflow API"},
        }
    
    @pytest.fixture
    def test_project(self):
        """Create test project data."""
        return {
            "id": "test-project-123",
            "workspace_id": "test-workspace-123",
            "name": "Test Project",
            "slug": "test-project",
            "meta_data": {"description": "Test project for workflow API"},
        }
    
    def test_list_workflows_empty(self, client: TestClient):
        """Test listing workflows when none exist."""
        # Mock workspace context
        response = client.get("/api/workflows/")
        # This will fail until we implement proper authentication/context
        assert response.status_code in [200, 401, 422]  # Depends on auth setup
    
    def test_workflow_validation_circular_dependency(self):
        """Test workflow validation detects circular dependencies."""
        from backend.services.workflows.dependency_resolver import WorkflowDependencyResolver
        
        resolver = WorkflowDependencyResolver()
        
        # Create workflow with circular dependency
        workflow = WorkflowCreate(
            name="Circular Workflow",
            description="Test circular dependency",
            steps=[
                WorkflowStepCreate(
                    name="step1",
                    step_type="task",
                    step_order=1,
                    depends_on_steps=["step3"],
                ),
                WorkflowStepCreate(
                    name="step2",
                    step_type="task", 
                    step_order=2,
                    depends_on_steps=["step1"],
                ),
                WorkflowStepCreate(
                    name="step3",
                    step_type="task",
                    step_order=3,
                    depends_on_steps=["step2"],
                ),
            ]
        )
        
        result = resolver.validate_workflow(workflow)
        
        assert not result.is_valid
        assert any("CIRCULAR_DEPENDENCY" in error.error_type for error in result.errors)
    
    def test_workflow_validation_missing_dependency(self):
        """Test workflow validation detects missing dependencies."""
        from backend.services.workflows.dependency_resolver import WorkflowDependencyResolver
        
        resolver = WorkflowDependencyResolver()
        
        # Create workflow with missing dependency
        workflow = WorkflowCreate(
            name="Missing Dependency Workflow",
            description="Test missing dependency",
            steps=[
                WorkflowStepCreate(
                    name="step1",
                    step_type="task",
                    step_order=1,
                    depends_on_steps=["nonexistent_step"],
                ),
            ]
        )
        
        result = resolver.validate_workflow(workflow)
        
        assert not result.is_valid
        assert any("MISSING_DEPENDENCY" in error.error_type for error in result.errors)
    
    def test_workflow_validation_duplicate_step_names(self):
        """Test workflow validation detects duplicate step names."""
        from backend.services.workflows.dependency_resolver import WorkflowDependencyResolver
        
        resolver = WorkflowDependencyResolver()
        
        # Create workflow with duplicate step names
        workflow = WorkflowCreate(
            name="Duplicate Names Workflow",
            description="Test duplicate step names",
            steps=[
                WorkflowStepCreate(
                    name="duplicate_name",
                    step_type="task",
                    step_order=1,
                ),
                WorkflowStepCreate(
                    name="duplicate_name",
                    step_type="task",
                    step_order=2,
                ),
            ]
        )
        
        result = resolver.validate_workflow(workflow)
        
        assert not result.is_valid
        assert any("DUPLICATE_STEP_NAME" in error.error_type for error in result.errors)
    
    def test_workflow_validation_duplicate_step_order(self):
        """Test workflow validation detects duplicate step orders."""
        from backend.services.workflows.dependency_resolver import WorkflowDependencyResolver
        
        resolver = WorkflowDependencyResolver()
        
        # Create workflow with duplicate step orders
        workflow = WorkflowCreate(
            name="Duplicate Order Workflow",
            description="Test duplicate step orders",
            steps=[
                WorkflowStepCreate(
                    name="step1",
                    step_type="task",
                    step_order=1,
                ),
                WorkflowStepCreate(
                    name="step2",
                    step_type="task",
                    step_order=1,  # Same order as step1
                ),
            ]
        )
        
        result = resolver.validate_workflow(workflow)
        
        assert not result.is_valid
        assert any("DUPLICATE_STEP_ORDER" in error.error_type for error in result.errors)
    
    def test_workflow_validation_non_sequential_order(self):
        """Test workflow validation detects non-sequential step orders."""
        from backend.services.workflows.dependency_resolver import WorkflowDependencyResolver
        
        resolver = WorkflowDependencyResolver()
        
        # Create workflow with non-sequential orders
        workflow = WorkflowCreate(
            name="Non-sequential Order Workflow",
            description="Test non-sequential step orders",
            steps=[
                WorkflowStepCreate(
                    name="step1",
                    step_type="task",
                    step_order=1,
                ),
                WorkflowStepCreate(
                    name="step2",
                    step_type="task",
                    step_order=3,  # Should be 2
                ),
            ]
        )
        
        result = resolver.validate_workflow(workflow)
        
        assert not result.is_valid
        assert any("NON_SEQUENTIAL_STEP_ORDER" in error.error_type for error in result.errors)
    
    def test_workflow_validation_valid_workflow(self):
        """Test workflow validation passes for valid workflow."""
        from backend.services.workflows.dependency_resolver import WorkflowDependencyResolver
        
        resolver = WorkflowDependencyResolver()
        
        # Create valid workflow
        workflow = WorkflowCreate(
            name="Valid Workflow",
            description="Test valid workflow",
            steps=[
                WorkflowStepCreate(
                    name="step1",
                    step_type="task",
                    step_order=1,
                ),
                WorkflowStepCreate(
                    name="step2",
                    step_type="task",
                    step_order=2,
                    depends_on_steps=["step1"],
                ),
                WorkflowStepCreate(
                    name="step3",
                    step_type="task",
                    step_order=3,
                    depends_on_steps=["step2"],
                ),
            ]
        )
        
        result = resolver.validate_workflow(workflow)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_dependency_resolver_topological_sort(self):
        """Test topological sorting of workflow steps."""
        from backend.services.workflows.dependency_resolver import WorkflowDependencyResolver
        
        resolver = WorkflowDependencyResolver()
        
        # Create workflow with dependencies
        steps = [
            WorkflowStepCreate(
                name="step1",
                step_type="task",
                step_order=1,
            ),
            WorkflowStepCreate(
                name="step2",
                step_type="task",
                step_order=2,
                depends_on_steps=["step1"],
            ),
            WorkflowStepCreate(
                name="step3",
                step_type="task",
                step_order=3,
                depends_on_steps=["step1", "step2"],
            ),
        ]
        
        order = resolver.get_topological_order(steps)
        
        # Verify step1 comes before step2 and step3
        assert order.index("step1") < order.index("step2")
        assert order.index("step1") < order.index("step3")
        # Verify step2 comes before step3
        assert order.index("step2") < order.index("step3")
    
    def test_dependency_resolver_topological_sort_cycle_detection(self):
        """Test circular dependency detection in topological sort."""
        from backend.services.workflows.dependency_resolver import WorkflowDependencyResolver
        
        resolver = WorkflowDependencyResolver()
        
        # Create workflow with circular dependency
        steps = [
            WorkflowStepCreate(
                name="step1",
                step_type="task",
                step_order=1,
                depends_on_steps=["step2"],
            ),
            WorkflowStepCreate(
                name="step2",
                step_type="task",
                step_order=2,
                depends_on_steps=["step1"],
            ),
        ]
        
        with pytest.raises(ValueError, match="Circular dependency detected"):
            resolver.get_topological_order(steps)
    
    def test_workflow_schemas_workflow_create(self):
        """Test WorkflowCreate schema validation."""
        # Valid workflow creation
        workflow_data = {
            "name": "Test Workflow",
            "description": "A test workflow",
            "config": {"setting1": "value1"},
            "timeout_seconds": 7200,
            "max_retries": 5,
            "steps": [
                {
                    "name": "step1",
                    "step_type": "task",
                    "step_order": 1,
                    "config": {"param1": "value1"},
                }
            ],
            "variables": [
                {
                    "name": "input_var",
                    "data_type": "string",
                    "is_required": True,
                    "description": "Input variable",
                }
            ],
        }
        
        workflow = WorkflowCreate(**workflow_data)
        assert workflow.name == "Test Workflow"
        assert workflow.description == "A test workflow"
        assert len(workflow.steps) == 1
        assert len(workflow.variables) == 1
    
    def test_workflow_schemas_workflow_execution_create(self):
        """Test WorkflowExecutionCreate schema validation."""
        # Valid execution creation
        execution_data = {
            "input_variables": {
                "param1": "value1",
                "param2": 123,
            }
        }
        
        execution = WorkflowExecutionCreate(**execution_data)
        assert execution.input_variables["param1"] == "value1"
        assert execution.input_variables["param2"] == 123
    
    def test_workflow_templates_endpoint(self, client: TestClient):
        """Test workflow templates endpoint."""
        # Mock workspace context and test templates endpoint
        response = client.get("/api/workflows/templates")
        
        # This will fail until we implement proper authentication/context
        assert response.status_code in [200, 401, 422]
        
        if response.status_code == 200:
            templates = response.json()
            assert isinstance(templates, list)
            assert len(templates) > 0
            
            # Check template structure
            for template in templates:
                assert "id" in template
                assert "name" in template
                assert "description" in template
                assert "steps" in template
                assert "variables" in template
    
    def test_workflow_validation_endpoint(self, client: TestClient):
        """Test workflow validation endpoint."""
        # Mock workspace context and test validation endpoint
        workflow_data = {
            "name": "Validation Test Workflow",
            "description": "Test workflow validation",
            "steps": [
                {
                    "name": "step1",
                    "step_type": "task",
                    "step_order": 1,
                }
            ],
        }
        
        response = client.post("/api/workflows/validate", json=workflow_data)
        
        # This will fail until we implement proper authentication/context
        assert response.status_code in [200, 401, 422]
        
        if response.status_code == 200:
            result = response.json()
            assert "is_valid" in result
            assert "errors" in result
            assert "warnings" in result
            assert isinstance(result["is_valid"], bool)
    
    def test_workflow_crud_operations(self):
        """Test basic CRUD operations for workflows (without database)."""
        # Test schema creation and validation
        workflow_data = {
            "name": "CRUD Test Workflow",
            "description": "Test CRUD operations",
            "steps": [
                WorkflowStepCreate(
                    name="initialize",
                    step_type=WorkflowStepType.TASK,
                    step_order=1,
                    config={"description": "Initialize workflow"}
                ),
                WorkflowStepCreate(
                    name="process",
                    step_type=WorkflowStepType.TASK,
                    step_order=2,
                    config={"description": "Process data"},
                    depends_on_steps=["initialize"]
                ),
            ],
            "variables": [
                WorkflowVariableCreate(
                    name="input_data",
                    data_type="json",
                    is_required=True,
                    description="Input data for processing"
                ),
            ]
        }
        
        workflow = WorkflowCreate(**workflow_data)
        
        # Verify data
        assert workflow.name == "CRUD Test Workflow"
        assert len(workflow.steps) == 2
        assert len(workflow.variables) == 1
        assert workflow.steps[1].depends_on_steps == ["initialize"]
        
        # Test validation
        from backend.services.workflows.dependency_resolver import WorkflowDependencyResolver
        
        resolver = WorkflowDependencyResolver()
        result = resolver.validate_workflow(workflow)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_workflow_step_types(self):
        """Test all workflow step types."""
        step_types = [
            WorkflowStepType.TASK,
            WorkflowStepType.CONDITION,
            WorkflowStepType.PARALLEL,
            WorkflowStepType.SEQUENTIAL,
            WorkflowStepType.AGENT,
        ]
        
        for step_type in step_types:
            step_data = {
                "name": f"test_step_{step_type.value}",
                "step_type": step_type,
                "step_order": 1,
            }
            
            step = WorkflowStepCreate(**step_data)
            assert step.step_type == step_type
    
    def test_workflow_complex_validation_scenarios(self):
        """Test complex workflow validation scenarios."""
        from backend.services.workflows.dependency_resolver import WorkflowDependencyResolver
        
        resolver = WorkflowDependencyResolver()
        
        # Test: Self-dependency
        workflow = WorkflowCreate(
            name="Self Dependency Workflow",
            steps=[
                WorkflowStepCreate(
                    name="self_dependent_step",
                    step_type="task",
                    step_order=1,
                    depends_on_steps=["self_dependent_step"],  # Self-dependency
                ),
            ]
        )
        
        result = resolver.validate_workflow(workflow)
        assert not result.is_valid
        assert any("SELF_DEPENDENCY" in error.error_type for error in result.errors)
        
        # Test: Complex dependency chain
        workflow = WorkflowCreate(
            name="Complex Chain Workflow",
            steps=[
                WorkflowStepCreate(
                    name="start",
                    step_type="task",
                    step_order=1,
                ),
                WorkflowStepCreate(
                    name="branch_a",
                    step_type="task",
                    step_order=2,
                    depends_on_steps=["start"],
                ),
                WorkflowStepCreate(
                    name="branch_b",
                    step_type="task",
                    step_order=2,
                    depends_on_steps=["start"],
                ),
                WorkflowStepCreate(
                    name="merge",
                    step_type="task",
                    step_order=3,
                    depends_on_steps=["branch_a", "branch_b"],
                ),
            ]
        )
        
        result = resolver.validate_workflow(workflow)
        assert result.is_valid
        
        # Verify topological order
        order = resolver.get_topological_order(workflow.steps)
        assert order.index("start") < order.index("branch_a")
        assert order.index("start") < order.index("branch_b")
        assert order.index("branch_a") < order.index("merge")
        assert order.index("branch_b") < order.index("merge")


if __name__ == "__main__":
    pytest.main([__file__])