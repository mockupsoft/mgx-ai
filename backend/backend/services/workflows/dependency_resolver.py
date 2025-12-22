# -*- coding: utf-8 -*-
"""
Workflow Dependency Resolver Service

Handles dependency resolution and validation for workflow definitions.
Extends the existing resolver with execution-level dependency resolution.
"""

import logging
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict, deque

from backend.schemas import (
    WorkflowStepCreate,
    WorkflowCreate,
    WorkflowValidationError,
    WorkflowValidationResult,
)
from backend.db.models import WorkflowStep

logger = logging.getLogger(__name__)


class WorkflowDependencyResolver:
    """Helper class for validating workflow step dependencies and graph structure."""
    
    def __init__(self):
        self.errors: List[WorkflowValidationError] = []
        self.warnings: List[str] = []
        logger.info("WorkflowDependencyResolver initialized")
    
    def validate_workflow(self, workflow: WorkflowCreate) -> WorkflowValidationResult:
        """Validate a workflow definition for common issues."""
        self.errors = []
        self.warnings = []
        
        if not workflow.steps:
            self.errors.append(WorkflowValidationError(
                error_type="MISSING_STEPS",
                message="Workflow must have at least one step"
            ))
        
        # Validate step names are unique within workflow
        self._validate_step_names(workflow.steps)
        
        # Validate step order is sequential
        self._validate_step_order(workflow.steps)
        
        # Build dependency graph
        graph, step_lookup = self._build_dependency_graph(workflow.steps)
        
        # Validate dependencies exist
        self._validate_dependencies_exist(graph, step_lookup, workflow.steps)
        
        # Check for circular dependencies
        self._detect_circular_dependencies(graph, step_lookup)
        
        # Validate agent requirements
        self._validate_agent_requirements(workflow.steps)
        
        # Check for unreachable steps
        self._check_reachable_steps(graph, step_lookup)
        
        return WorkflowValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings
        )
    
    def validate_step_updates(self, workflow_id: str, updated_steps: List[WorkflowStepCreate], 
                            existing_steps: List[WorkflowStepCreate]) -> WorkflowValidationResult:
        """Validate updates to existing workflow steps."""
        self.errors = []
        self.warnings = []
        
        # Build dependency graphs for both old and new states
        old_graph, old_lookup = self._build_dependency_graph(existing_steps)
        new_graph, new_lookup = self._build_dependency_graph(updated_steps)
        
        # Validate dependencies exist
        self._validate_dependencies_exist(new_graph, new_lookup, updated_steps)
        
        # Check for circular dependencies
        self._detect_circular_dependencies(new_graph, new_lookup)
        
        # Check for breaking changes (steps being depended on being removed or renamed)
        self._validate_breaking_changes(old_graph, new_graph, existing_steps, updated_steps)
        
        return WorkflowValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings
        )
    
    def get_topological_order(self, steps: List[WorkflowStepCreate]) -> List[str]:
        """Get steps in topological order based on dependencies."""
        graph, step_lookup = self._build_dependency_graph(steps)
        
        # Kahn's algorithm for topological sorting
        in_degree = defaultdict(int)
        for step_id in graph:
            in_degree[step_id] = 0
        
        for step_id in graph:
            for dependent in graph[step_id]:
                in_degree[dependent] += 1
        
        queue = deque([step_id for step_id in graph if in_degree[step_id] == 0])
        result = []
        
        while queue:
            current = queue.popleft()
            result.append(current)
            
            for dependent in graph[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        if len(result) != len(graph):
            raise ValueError("Circular dependency detected")
        
        return result

    # ============================================
    # Execution-time dependency resolution methods
    # ============================================

    def resolve_execution_order(self, steps: List[WorkflowStep]) -> List[List[WorkflowStep]]:
        """
        Resolve the execution order of workflow steps using topological sorting.
        
        Args:
            steps: List of workflow steps
            
        Returns:
            List of step groups that can be executed in parallel within each group
            
        Raises:
            ValueError: If circular dependencies are detected
            KeyError: If missing dependencies are referenced
        """
        # Build step lookup
        step_map = {step.id: step for step in steps}
        
        # Validate dependencies exist
        for step in steps:
            for dep_id in step.depends_on_steps:
                if dep_id not in step_map:
                    raise KeyError(f"Step '{step.name}' references unknown dependency '{dep_id}'")
        
        # Build dependency graph
        dependency_graph = {step.id: set(step.depends_on_steps) for step in steps}
        
        # Detect circular dependencies
        self._detect_circular_dependencies_execution(dependency_graph)
        
        # Perform topological sort to get execution levels
        return self._topological_sort_by_levels_execution(dependency_graph, step_map)
    
    def get_parallel_execution_groups(self, steps: List[WorkflowStep]) -> List[List[WorkflowStep]]:
        """
        Get groups of steps that can be executed in parallel.
        
        This method provides more granular parallelization than resolve_execution_order
        by considering step types and dependencies more carefully.
        
        Args:
            steps: List of workflow steps
            
        Returns:
            List of parallel execution groups
        """
        execution_levels = self.resolve_execution_order(steps)
        
        # Further split levels based on step types and dependencies
        parallel_groups = []
        
        for level in execution_levels:
            if len(level) <= 1:
                # Single step, no parallelization needed
                parallel_groups.append(level)
                continue
            
            # Analyze steps in this level for additional parallelization
            independent_groups = self._split_by_dependencies_execution(level)
            parallel_groups.extend(independent_groups)
        
        return parallel_groups
    
    def can_execute_step_now(
        self,
        step: WorkflowStep,
        completed_steps: Set[str],
        running_steps: Set[str],
    ) -> bool:
        """
        Check if a step can be executed right now based on dependencies.
        
        Args:
            step: Workflow step to check
            completed_steps: Set of step IDs that have completed
            running_steps: Set of step IDs that are currently running
            
        Returns:
            True if step can be executed
        """
        # Check if all dependencies are completed
        for dep_id in step.depends_on_steps:
            if dep_id not in completed_steps:
                return False
        
        # Check if step is not already running
        if step.id in running_steps:
            return False
        
        return True
    
    def get_next_executable_steps(
        self,
        steps: List[WorkflowStep],
        completed_steps: Set[str],
        running_steps: Set[str],
    ) -> List[WorkflowStep]:
        """
        Get all steps that can be executed right now.
        
        Args:
            steps: All workflow steps
            completed_steps: Set of step IDs that have completed
            running_steps: Set of step IDs that are currently running
            
        Returns:
            List of executable steps
        """
        executable = []
        
        for step in steps:
            if step.id in completed_steps or step.id in running_steps:
                continue
            
            if self.can_execute_step_now(step, completed_steps, running_steps):
                executable.append(step)
        
        return executable
    
    # ============================================
    # Private helper methods (existing)
    # ============================================
    
    def _build_dependency_graph(self, steps: List[WorkflowStepCreate]) -> Tuple[Dict[str, Set[str]], Dict[str, WorkflowStepCreate]]:
        """Build dependency graph from steps."""
        graph = defaultdict(set)
        step_lookup = {}
        
        for step in steps:
            step_lookup[step.name] = step
            # Initialize with empty set for all steps
            graph[step.name] = set()
        
        # Add dependencies
        for step in steps:
            for dep_name in step.depends_on_steps:
                if dep_name in step_lookup:
                    graph[step.name].add(dep_name)
                else:
                    self.errors.append(WorkflowValidationError(
                        error_type="INVALID_DEPENDENCY",
                        message=f"Step '{step.name}' depends on unknown step '{dep_name}'"
                    ))
        
        return dict(graph), step_lookup
    
    def _validate_step_names(self, steps: List[WorkflowStepCreate]):
        """Validate that all step names are unique."""
        names = [step.name for step in steps]
        duplicate_names = [name for name in set(names) if names.count(name) > 1]
        
        if duplicate_names:
            self.errors.append(WorkflowValidationError(
                error_type="DUPLICATE_STEP_NAMES",
                message=f"Duplicate step names found: {', '.join(duplicate_names)}"
            ))
    
    def _validate_step_order(self, steps: List[WorkflowStepCreate]):
        """Validate that step orders are sequential."""
        orders = [step.step_order for step in steps]
        min_order, max_order = min(orders), max(orders)
        
        expected_orders = set(range(min_order, max_order + 1))
        actual_orders = set(orders)
        
        missing_orders = expected_orders - actual_orders
        if missing_orders:
            self.errors.append(WorkflowValidationError(
                error_type="NON_SEQUENTIAL_ORDER",
                message=f"Missing step orders: {sorted(missing_orders)}"
            ))
    
    def _validate_dependencies_exist(self, graph: Dict[str, Set[str]], step_lookup: Dict[str, WorkflowStepCreate], steps: List[WorkflowStepCreate]):
        """Validate that all dependencies reference existing steps."""
        for step in steps:
            for dep_name in step.depends_on_steps:
                if dep_name not in step_lookup:
                    self.errors.append(WorkflowValidationError(
                        error_type="MISSING_DEPENDENCY",
                        message=f"Step '{step.name}' depends on non-existent step '{dep_name}'"
                    ))
    
    def _detect_circular_dependencies(self, graph: Dict[str, Set[str]], step_lookup: Dict[str, WorkflowStepCreate]):
        """Detect circular dependencies using DFS."""
        visited = set()
        rec_stack = set()
        
        def dfs(node: str) -> bool:
            if node in rec_stack:
                cycle_path = list(rec_stack) + [node]
                self.errors.append(WorkflowValidationError(
                    error_type="CIRCULAR_DEPENDENCY",
                    message=f"Circular dependency detected: {' -> '.join(cycle_path)}"
                ))
                return True
            
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph[node]:
                if dfs(neighbor):
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                dfs(node)
    
    def _validate_agent_requirements(self, steps: List[WorkflowStepCreate]):
        """Validate agent requirements for steps that need agents."""
        for step in steps:
            if step.step_type in ["agent", "task"]:
                if not step.agent_definition_id and not step.agent_instance_id:
                    self.warnings.append(f"Step '{step.name}' may require agent configuration")
    
    def _check_reachable_steps(self, graph: Dict[str, Set[str]], step_lookup: Dict[str, WorkflowStepCreate]):
        """Check for steps that are unreachable from any entry point."""
        if not graph:
            return
        
        # Find entry points (steps with no dependencies)
        entry_points = [step_name for step_name, deps in graph.items() if not deps]
        
        # If no entry points, all steps depend on something (potential issue)
        if not entry_points:
            self.warnings.append("No clear entry points found in workflow")
            return
        
        # DFS to find all reachable steps
        visited = set()
        
        def dfs(node: str):
            if node in visited:
                return
            visited.add(node)
            for neighbor in graph[node]:
                dfs(neighbor)
        
        for entry_point in entry_points:
            dfs(entry_point)
        
        # Check for unreachable steps
        unreachable = set(graph.keys()) - visited
        if unreachable:
            self.errors.append(WorkflowValidationError(
                error_type="UNREACHABLE_STEPS",
                message=f"Unreachable steps found: {', '.join(unreachable)}"
            ))
    
    def _validate_breaking_changes(self, old_graph: Dict[str, Set[str]], new_graph: Dict[str, Set[str]], 
                                 old_steps: List[WorkflowStepCreate], new_steps: List[WorkflowStepCreate]):
        """Validate that updates don't break existing dependencies."""
        old_step_names = {step.name for step in old_steps}
        new_step_names = {step.name for step in new_steps}
        
        # Check for removed steps that were depended upon
        removed_steps = old_step_names - new_step_names
        
        for step in new_steps:
            for dep_name in step.depends_on_steps:
                if dep_name in removed_steps:
                    self.errors.append(WorkflowValidationError(
                        error_type="BREAKING_CHANGE",
                        message=f"Step '{step.name}' depends on removed step '{dep_name}'"
                    ))
    
    # ============================================
    # Private helper methods (execution-time)
    # ============================================
    
    def _detect_circular_dependencies_execution(self, dependency_graph: Dict[str, Set[str]]):
        """
        Detect circular dependencies using DFS.
        
        Args:
            dependency_graph: Dictionary mapping step IDs to their dependencies
            
        Raises:
            ValueError: If circular dependencies are found
        """
        visited = set()
        rec_stack = set()
        
        def dfs(node: str) -> bool:
            """DFS to detect cycles."""
            if node in rec_stack:
                cycle_path = list(rec_stack) + [node]
                raise ValueError(f"Circular dependency detected: {' -> '.join(cycle_path)}")
            
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in dependency_graph.get(node, set()):
                dfs(neighbor)
            
            rec_stack.remove(node)
            return False
        
        for node in dependency_graph:
            if node not in visited:
                dfs(node)
    
    def _topological_sort_by_levels_execution(
        self,
        dependency_graph: Dict[str, Set[str]],
        step_map: Dict[str, WorkflowStep],
    ) -> List[List[WorkflowStep]]:
        """
        Perform topological sort and group by execution levels.
        
        Args:
            dependency_graph: Dictionary mapping step IDs to their dependencies
            step_map: Dictionary mapping step IDs to WorkflowStep objects
            
        Returns:
            List of step groups, where each group can be executed in parallel
        """
        in_degree = {node: 0 for node in dependency_graph}
        
        # Calculate in-degrees
        for node in dependency_graph:
            for neighbor in dependency_graph[node]:
                if neighbor in in_degree:
                    in_degree[neighbor] += 1
        
        # Start with nodes that have no dependencies
        queue = [node for node in in_degree if in_degree[node] == 0]
        result = []
        
        while queue:
            # Process current level
            current_level = queue
            queue = []
            
            level_steps = [step_map[node] for node in current_level]
            result.append(level_steps)
            
            # Reduce in-degree for dependent nodes
            for node in current_level:
                for dependent in self._get_dependents_execution(node, dependency_graph):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        
        return result
    
    def _get_dependents_execution(self, node: str, dependency_graph: Dict[str, Set[str]]) -> Set[str]:
        """Get all nodes that depend on the given node."""
        dependents = set()
        for dependent, dependencies in dependency_graph.items():
            if node in dependencies:
                dependents.add(dependent)
        return dependents
    
    def _split_by_dependencies_execution(self, steps: List[WorkflowStep]) -> List[List[WorkflowStep]]:
        """
        Split steps in a level into independent groups based on dependencies.
        
        Args:
            steps: Steps in the same execution level
            
        Returns:
            List of independent step groups
        """
        if len(steps) <= 1:
            return [steps]
        
        # Build dependency relationships within this level
        step_ids = [step.id for step in steps]
        step_map = {step.id: step for step in steps}
        
        # Find steps that don't depend on other steps in this level
        independent_steps = []
        dependent_steps = []
        
        for step in steps:
            has_internal_deps = any(dep_id in step_ids for dep_id in step.depends_on_steps)
            if has_internal_deps:
                dependent_steps.append(step)
            else:
                independent_steps.append(step)
        
        # If all steps are independent, they can run in parallel
        if not dependent_steps:
            return [steps]
        
        # If all steps are dependent, maintain original order
        if not independent_steps:
            return [steps]
        
        # Mix of independent and dependent steps
        groups = []
        if independent_steps:
            groups.append(independent_steps)
        
        # Process dependent steps in order
        groups.append(dependent_steps)
        
        return groups


# Backward compatibility alias
DependencyResolver = WorkflowDependencyResolver


__all__ = [
    "WorkflowDependencyResolver", 
    "DependencyResolver"
]