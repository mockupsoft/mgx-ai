#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CLI script to seed example workflows into the database.

Usage:
    python -m backend.scripts.seed_workflows --workspace-id <id> [--project-id <id>]
"""

import json
import logging
import sys
from pathlib import Path
from argparse import ArgumentParser

import asyncio
from sqlalchemy import select

from backend.config import get_settings
from backend.db.engine import engine
from backend.db.session import AsyncSessionLocal
from backend.db.models import Workspace, Project, WorkflowDefinition, WorkflowStep, WorkflowVariable
from backend.db.models.enums import WorkflowStepType
from backend.schemas import WorkflowCreate

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_workflow_files():
    """Get all example workflow JSON files."""
    examples_dir = Path(__file__).parent.parent.parent / "examples" / "workflows"
    if not examples_dir.exists():
        logger.warning(f"Workflows directory not found: {examples_dir}")
        return []
    
    workflow_files = sorted(examples_dir.glob("*.json"))
    logger.info(f"Found {len(workflow_files)} workflow definitions")
    return workflow_files


def load_workflow_definition(file_path: Path) -> dict:
    """Load a workflow definition from a JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


async def seed_workflow(
    session,
    workspace_id: str,
    project_id: str,
    workflow_def: dict
) -> str:
    """Seed a single workflow definition into the database."""
    try:
        # Create WorkflowCreate schema from definition
        workflow_data = WorkflowCreate(
            name=workflow_def.get("name"),
            description=workflow_def.get("description"),
            project_id=project_id,
            config=workflow_def.get("config", {}),
            timeout_seconds=workflow_def.get("timeout_seconds", 3600),
            max_retries=workflow_def.get("max_retries", 3),
            steps=[],
            variables=[],
            meta_data=workflow_def.get("metadata") or workflow_def.get("meta_data", {}),
        )

        # Add variables
        for var_def in workflow_def.get("variables", []):
            from backend.schemas import WorkflowVariableCreate
            workflow_data.variables.append(
                WorkflowVariableCreate(
                    name=var_def.get("name"),
                    data_type=var_def.get("data_type"),
                    is_required=var_def.get("is_required", False),
                    default_value=var_def.get("default_value"),
                    description=var_def.get("description"),
                    meta_data=var_def.get("metadata") or var_def.get("meta_data", {}),
                )
            )

        # Add steps
        for step_def in workflow_def.get("steps", []):
            from backend.schemas import WorkflowStepCreate, WorkflowStepTypeEnum
            workflow_data.steps.append(
                WorkflowStepCreate(
                    name=step_def.get("name"),
                    step_type=WorkflowStepTypeEnum(step_def.get("step_type")),
                    step_order=step_def.get("step_order"),
                    config=step_def.get("config", {}),
                    timeout_seconds=step_def.get("timeout_seconds"),
                    max_retries=step_def.get("max_retries"),
                    agent_definition_id=step_def.get("agent_definition_id"),
                    agent_instance_id=step_def.get("agent_instance_id"),
                    depends_on_steps=step_def.get("depends_on_steps", []),
                    condition_expression=step_def.get("condition_expression"),
                    meta_data=step_def.get("metadata") or step_def.get("meta_data", {}),
                )
            )

        # Create workflow in database
        db_workflow = WorkflowDefinition(
            workspace_id=workspace_id,
            project_id=project_id,
            name=workflow_data.name,
            description=workflow_data.description,
            version=1,
            is_active=True,
            config=workflow_data.config,
            timeout_seconds=workflow_data.timeout_seconds,
            max_retries=workflow_data.max_retries,
            meta_data=workflow_data.meta_data,
        )

        session.add(db_workflow)
        await session.flush()

        # Add variables
        for var_data in workflow_data.variables:
            db_var = WorkflowVariable(
                workflow_id=db_workflow.id,
                name=var_data.name,
                data_type=var_data.data_type,
                is_required=var_data.is_required,
                default_value=var_data.default_value,
                description=var_data.description,
                meta_data=var_data.meta_data,
            )
            session.add(db_var)

        # Add steps
        for step_data in workflow_data.steps:
            db_step = WorkflowStep(
                workflow_id=db_workflow.id,
                name=step_data.name,
                step_type=WorkflowStepType(step_data.step_type.value),
                step_order=step_data.step_order,
                config=step_data.config,
                timeout_seconds=step_data.timeout_seconds,
                max_retries=step_data.max_retries,
                agent_definition_id=step_data.agent_definition_id,
                agent_instance_id=step_data.agent_instance_id,
                depends_on_steps=step_data.depends_on_steps,
                condition_expression=step_data.condition_expression,
                meta_data=step_data.meta_data,
            )
            session.add(db_step)

        await session.flush()
        await session.commit()

        logger.info(f"✓ Seeded workflow: {workflow_data.name} (ID: {db_workflow.id})")
        return db_workflow.id

    except Exception as e:
        logger.error(f"✗ Failed to seed workflow: {workflow_def.get('name')} - {str(e)}")
        await session.rollback()
        raise


async def main():
    """Main function to seed workflows."""
    parser = ArgumentParser(description="Seed example workflows into the database")
    parser.add_argument(
        "--workspace-id",
        required=True,
        help="ID of the workspace to seed workflows into"
    )
    parser.add_argument(
        "--project-id",
        help="ID of the project (uses default if not specified)"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip workflows that already exist"
    )

    args = parser.parse_args()
    workspace_id = args.workspace_id
    project_id = args.project_id
    skip_existing = args.skip_existing

    # Get database session
    async_session = AsyncSessionLocal
    async with async_session() as session:
        try:
            # Verify workspace exists
            workspace_result = await session.execute(
                select(Workspace).where(Workspace.id == workspace_id)
            )
            workspace = workspace_result.scalar_one_or_none()
            if not workspace:
                logger.error(f"Workspace not found: {workspace_id}")
                sys.exit(1)

            # Get default project if not specified
            if not project_id:
                project_result = await session.execute(
                    select(Project).where(Project.workspace_id == workspace_id).limit(1)
                )
                project = project_result.scalar_one_or_none()
                if not project:
                    logger.error(f"No projects found in workspace: {workspace_id}")
                    sys.exit(1)
                project_id = project.id
            else:
                # Verify project exists and belongs to workspace
                project_result = await session.execute(
                    select(Project).where(
                        Project.id == project_id,
                        Project.workspace_id == workspace_id
                    )
                )
                project = project_result.scalar_one_or_none()
                if not project:
                    logger.error(f"Project not found or does not belong to workspace")
                    sys.exit(1)

            logger.info(f"Seeding workflows into workspace: {workspace.name} ({workspace_id})")
            logger.info(f"Using project: {project.name} ({project_id})")

            # Get and process workflow files
            workflow_files = get_workflow_files()
            if not workflow_files:
                logger.warning("No workflow definitions found")
                sys.exit(1)

            seeded_count = 0
            skipped_count = 0

            for workflow_file in workflow_files:
                try:
                    workflow_def = load_workflow_definition(workflow_file)
                    workflow_name = workflow_def.get("name")

                    # Check if workflow already exists
                    if skip_existing:
                        existing_result = await session.execute(
                            select(WorkflowDefinition).where(
                                WorkflowDefinition.workspace_id == workspace_id,
                                WorkflowDefinition.project_id == project_id,
                                WorkflowDefinition.name == workflow_name,
                            )
                        )
                        if existing_result.scalar_one_or_none():
                            logger.info(f"⊘ Skipping existing workflow: {workflow_name}")
                            skipped_count += 1
                            continue

                    workflow_id = await seed_workflow(
                        session,
                        workspace_id,
                        project_id,
                        workflow_def
                    )
                    seeded_count += 1

                except json.JSONDecodeError as e:
                    logger.error(f"✗ Invalid JSON in {workflow_file.name}: {str(e)}")
                except Exception as e:
                    logger.error(f"✗ Error processing {workflow_file.name}: {str(e)}")

            logger.info(f"\n=== Summary ===")
            logger.info(f"✓ Seeded: {seeded_count} workflows")
            if skipped_count > 0:
                logger.info(f"⊘ Skipped: {skipped_count} existing workflows")
            logger.info("✓ Workflow seeding complete!")

        except Exception as e:
            logger.error(f"Fatal error during seeding: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
