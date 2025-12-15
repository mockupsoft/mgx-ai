"""Workflow dependency resolver for validating workflow definitions."""

from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict, deque

from backend.schemas import (
    WorkflowStepCreate,
    WorkflowCreate,
    WorkflowValidationError,
    WorkflowValidationResult,
)


class WorkflowDependencyResolver:
    """Helper class for validating workflow step dependencies and graph structure."""
    
    def __init__(self):
        self.errors: List[WorkflowValidationError] = []
        self.warnings: List[str] = []
    
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
        
        # If we don't have all steps, there's a cycle
        if len(result) != len(graph):
            raise ValueError("Circular dependency detected in workflow steps")
        
        return result
    
    def _validate_step_names(self, steps: List[WorkflowStepCreate]) -> None:
        """Ensure all step names are unique within the workflow."""
        name_counts = defaultdict(int)
        for step in steps:
            name_counts[step.name] += 1
        
        for name, count in name_counts.items():
            if count > 1:
                self.errors.append(WorkflowValidationError(
                    error_type="DUPLICATE_STEP_NAME",
                    message=f"Step name '{name}' appears {count} times. Step names must be unique.",
                    details={"step_name": name, "count": count}
                ))
    
    def _validate_step_order(self, steps: List[WorkflowStepCreate]) -> None:
        """Validate that step orders are sequential starting from 1."""
        orders = [step.step_order for step in steps]
        orders.sort()
        
        # Check for duplicates
        order_counts = defaultdict(int)
        for order in orders:
            order_counts[order] += 1
        
        for order, count in order_counts.items():
            if count > 1:
                self.errors.append(WorkflowValidationError(
                    error_type="DUPLICATE_STEP_ORDER",
                    message=f"Step order {order} appears {count} times. Each step must have a unique order.",
                    details={"step_order": order, "count": count}
                ))
        
        # Check for missing orders (should be 1, 2, 3, ...)
        expected_orders = list(range(1, len(orders) + 1))
        for i, expected in enumerate(expected_orders):
            if i >= len(orders) or orders[i] != expected:
                self.errors.append(WorkflowValidationError(
                    error_type="NON_SEQUENTIAL_STEP_ORDER",
                    message=f"Step orders should be sequential starting from 1. Expected {expected} at position {i+1}, got {orders[i] if i < len(orders) else 'missing'}.",
                    details={"expected_order": expected, "actual_order": orders[i] if i < len(orders) else None}
                ))
                break
    
    def _build_dependency_graph(self, steps: List[WorkflowStepCreate]) -> Tuple[Dict[str, Set[str]], Dict[str, WorkflowStepCreate]]:
        """Build dependency graph and step lookup from steps."""
        graph = defaultdict(set)  # step_id -> set of dependent step IDs
        step_lookup = {}
        
        for step in steps:
            step_id = step.name  # Use name as ID for validation
            step_lookup[step_id] = step
            
            # Add dependencies
            for dependency in step.depends_on_steps:
                graph[dependency].add(step_id)
        
        return graph, step_lookup
    
    def _validate_dependencies_exist(self, graph: Dict[str, Set[str]], 
                                   step_lookup: Dict[str, WorkflowStepCreate],
                                   steps: List[WorkflowStepCreate]) -> None:
        """Validate that all dependencies reference existing steps."""
        for step in steps:
            step_id = step.name
            
            for dependency in step.depends_on_steps:
                if dependency not in step_lookup:
                    self.errors.append(WorkflowValidationError(
                        step_id=step_id,
                        step_name=step.name,
                        error_type="MISSING_DEPENDENCY",
                        message=f"Step '{step.name}' depends on step '{dependency}' which does not exist.",
                        details={"dependency": dependency, "step_id": step_id}
                    ))
                
                # Check for self-dependency
                if dependency == step_id:
                    self.errors.append(WorkflowValidationError(
                        step_id=step_id,
                        step_name=step.name,
                        error_type="SELF_DEPENDENCY",
                        message=f"Step '{step.name}' cannot depend on itself.",
                        details={"dependency": dependency}
                    ))
    
    def _detect_circular_dependencies(self, graph: Dict[str, Set[str]], 
                                    step_lookup: Dict[str, WorkflowStepCreate]) -> None:
        """Detect circular dependencies using DFS."""
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]) -> bool:
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycle_path = path[cycle_start:] + [node]
                self.errors.append(WorkflowValidationError(
                    error_type="CIRCULAR_DEPENDENCY",
                    message=f"Circular dependency detected: {' -> '.join(cycle_path)}",
                    details={"cycle": cycle_path}
                ))
                return True
            
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            
            for dependent in graph[node]:
                if dfs(dependent, path + [node]):
                    return True
            
            rec_stack.remove(node)
            return False
        
        for step_id in step_lookup:
            if step_id not in visited:
                dfs(step_id, [])
    
    def _validate_agent_requirements(self, steps: List[WorkflowStepCreate]) -> None:
        """Validate agent-related requirements."""
        for step in steps:
            # Check that we don't have both agent_definition_id and agent_instance_id
            if step.agent_definition_id and step.agent_instance_id:
                self.warnings.append(
                    f"Step '{step.name}' has both agent_definition_id and agent_instance_id. "
                    f"agent_instance_id will be used, agent_definition_id will be ignored."
                )
            
            # Check for agent requirements by step type
            if step.step_type.value == "agent" and not (step.agent_definition_id or step.agent_instance_id):
                self.warnings.append(
                    f"Agent step '{step.name}' has no agent requirements specified. "
                    f"This may cause execution issues."
                )
    
    def _check_reachable_steps(self, graph: Dict[str, Set[str]], 
                             step_lookup: Dict[str, WorkflowStepCreate]) -> None:
        """Check for steps that are unreachable from the start."""
        if not step_lookup:
            return
        
        # Find steps with no dependencies (entry points)
        entry_points = []
        all_steps = set(step_lookup.keys())
        dependent_steps = set()
        
        for step_id, dependents in graph.items():
            dependent_steps.update(dependents)
        
        for step_id in all_steps:
            if step_id not in dependent_steps:
                entry_points.append(step_id)
        
        if not entry_points:
            # All steps have dependencies, this might be fine
            return
        
        # Use DFS from entry points to find all reachable steps
        reachable = set()
        
        def dfs_reachable(node: str):
            if node in reachable:
                return
            reachable.add(node)
            for dependent in graph[node]:
                dfs_reachable(dependent)
        
        for entry_point in entry_points:
            dfs_reachable(entry_point)
        
        # Find unreachable steps
        unreachable = all_steps - reachable
        for step_id in unreachable:
            step = step_lookup[step_id]
            self.warnings.append(
                f"Step '{step.name}' might be unreachable from workflow entry points. "
                f"Consider adding it as a dependency or removing it if unused."
            )
    
    def _validate_breaking_changes(self, old_graph: Dict[str, Set[str]], 
                                 new_graph: Dict[str, Set[str]],
                                 old_steps: List[WorkflowStepCreate],
                                 new_steps: List[WorkflowStepCreate]) -> None:
        """Check for breaking changes when updating workflow steps."""
        old_lookup = {step.name: step for step in old_steps}
        new_lookup = {step.name: step for step in new_steps}
        
        # Check if any steps that were depended on have been removed or renamed
        for step_id in old_lookup:
            if step_id not in new_lookup:
                step = old_lookup[step_id]
                # Check if other steps still depend on this step
                for old_step_id in old_graph:
                    if step_id in old_graph[old_step_id]:
                        # This is a breaking change
                        self.errors.append(WorkflowValidationError(
                            error_type="BREAKING_DEPENDENCY_CHANGE",
                            message=f"Cannot remove step '{step.name}' because other steps depend on it.",
                            details={"removed_step": step_id, "dependents": list(old_graph[step_id])}
                        ))
    
    def validate_io_contracts(self, steps: List[WorkflowStepCreate]) -> WorkflowValidationResult:
        """Validate input/output contracts between steps."""
        self.errors = []
        self.warnings = []
        
        # Build a map of step outputs and expected inputs
        step_outputs = {}
        step_inputs = {}
        
        for step in steps:
            # Extract expected inputs from step configuration
            step_inputs[step.name] = self._extract_step_inputs(step)
            
            # Extract outputs from step configuration
            step_outputs[step.name] = self._extract_step_outputs(step)
        
        # Validate that each step's input requirements are met by preceding steps
        order = self.get_topological_order(steps)
        executed_steps = set()
        
        for step_id in order:
            step = next(s for s in steps if s.name == step_id)
            expected_inputs = step_inputs[step_id]
            
            # Check if expected inputs are available from executed steps
            for input_name, input_type in expected_inputs.items():
                available_from = None
                for executed_step in executed_steps:
                    if input_name in step_outputs[executed_step]:
                        available_type = step_outputs[executed_step][input_name]
                        if available_type == input_type or input_type == "any":
                            available_from = executed_step
                            break
                
                if not available_from:
                    self.warnings.append(
                        f"Step '{step.name}' expects input '{input_name}' of type '{input_type}' "
                        f"but no preceding step provides it. This may cause execution issues."
                    )
            
            executed_steps.add(step_id)
        
        return WorkflowValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings
        )
    
    def _extract_step_inputs(self, step: WorkflowStepCreate) -> Dict[str, str]:
        """Extract expected inputs from step configuration."""
        inputs = step.config.get("inputs", {})
        return {name: config.get("type", "any") for name, config in inputs.items()}
    
    def _extract_step_outputs(self, step: WorkflowStepCreate) -> Dict[str, str]:
        """Extract expected outputs from step configuration."""
        outputs = step.config.get("outputs", {})
        return {name: config.get("type", "any") for name, config in outputs.items()}