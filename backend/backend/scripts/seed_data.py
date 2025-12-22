# -*- coding: utf-8 -*-
"""
Seed script for populating demo data in the database.

This script creates sample tasks, task runs, metrics, and artifacts
for local dashboard previews and testing.
"""

import asyncio
import hashlib
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add the project root to Python path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from db.engine import get_session_factory
from db.models import (
    Workspace,
    Project,
    Task,
    TaskRun,
    MetricSnapshot,
    Artifact,
    TaskStatus,
    RunStatus,
    MetricType,
    ArtifactType,
)


async def create_sample_task(
    session: AsyncSession,
    workspace: Workspace,
    project: Project,
    name: str,
    description: str = None,
) -> Task:
    """Create a sample task with realistic configuration."""
    config = {
        "prompt": f"Generate a comprehensive report about {name}",
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 2000,
        "tools": ["web_search", "data_analysis", "report_generator"],
        "output_format": "markdown",
        "include_sources": True,
        "validation_rules": ["check_facts", "verify_sources", "test_code"]
    }
    
    task = Task(
        workspace_id=workspace.id,
        project_id=project.id,
        name=name,
        description=description or f"Automated analysis task for {name}",
        config=config,
        status=TaskStatus.COMPLETED,
        max_rounds=random.randint(3, 8),
        max_revision_rounds=random.randint(1, 3),
        memory_size=random.randint(30, 80),
        total_runs=random.randint(5, 15),
        successful_runs=random.randint(4, 12),
        failed_runs=random.randint(0, 3),
        last_run_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72)),
        last_run_duration=random.uniform(45.5, 180.2),
    )
    
    session.add(task)
    await session.flush()
    return task


async def create_sample_runs(session: AsyncSession, task: Task, num_runs: int = None) -> list[TaskRun]:
    """Create sample task runs for a given task."""
    if num_runs is None:
        num_runs = random.randint(3, 8)
    
    runs = []
    for i in range(num_runs):
        status = random.choices(
            [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED],
            weights=[0.7, 0.2, 0.1]
        )[0]
        
        started_at = datetime.utcnow() - timedelta(days=random.randint(1, 30))
        duration = random.uniform(30.0, 300.0) if status == RunStatus.COMPLETED else None
        completed_at = started_at + timedelta(seconds=duration) if duration else None
        
        plan = {
            "steps": [
                {"step": 1, "action": "data_collection", "duration": 15.0},
                {"step": 2, "action": "analysis", "duration": 45.0},
                {"step": 3, "action": "synthesis", "duration": 30.0},
                {"step": 4, "action": "reporting", "duration": 25.0}
            ],
            "estimated_duration": 115.0,
            "memory_usage": f"{random.randint(200, 800)}MB"
        }
        
        results = {
            "summary": f"Analysis completed for task {task.name}",
            "insights": [
                "Market analysis shows positive trends",
                "Technical indicators suggest growth potential", 
                "Risk assessment indicates moderate exposure"
            ],
            "recommendations": [
                "Focus on sustainable growth strategies",
                "Diversify portfolio for risk mitigation",
                "Monitor key performance indicators"
            ],
            "confidence_score": random.uniform(0.75, 0.95),
            "processing_time": duration,
            "data_points_analyzed": random.randint(1000, 50000)
        }
        
        run = TaskRun(
            task_id=task.id,
            workspace_id=task.workspace_id,
            project_id=task.project_id,
            run_number=i + 1,
            status=status,
            plan=plan,
            results=results if status == RunStatus.COMPLETED else None,
            started_at=started_at,
            completed_at=completed_at,
            duration=duration,
            error_message="Sample error message" if status == RunStatus.FAILED else None,
            error_details={"error_type": "ValidationError", "details": "Invalid input data"} if status == RunStatus.FAILED else None,
            memory_used=random.randint(200, 1200),
            round_count=random.randint(2, 6)
        )
        
        runs.append(run)
        session.add(run)
    
    await session.flush()
    return runs


async def create_sample_metrics(session: AsyncSession, task: Task, runs: list[TaskRun]) -> list[MetricSnapshot]:
    """Create sample metrics for tasks and runs."""
    metrics = []
    
    # Task-level metrics
    task_metrics = [
        ("task_success_rate", MetricType.GAUGE, random.uniform(0.6, 0.95), "%"),
        ("avg_execution_time", MetricType.GAUGE, random.uniform(60, 180), "seconds"),
        ("memory_usage_avg", MetricType.GAUGE, random.uniform(400, 800), "MB"),
        ("rounds_per_execution", MetricType.GAUGE, random.uniform(3, 6), "count"),
    ]
    
    for name, metric_type, value, unit in task_metrics:
        metric = MetricSnapshot(
            workspace_id=task.workspace_id,
            project_id=task.project_id,
            task_id=task.id,
            name=name,
            metric_type=metric_type,
            value=value,
            unit=unit,
            labels={"scope": "task", "task_name": task.name},
            timestamp=datetime.utcnow() - timedelta(hours=random.randint(1, 24))
        )
        metrics.append(metric)
        session.add(metric)
    
    # Run-level metrics
    for run in runs:
        if run.status == RunStatus.COMPLETED:
            run_metrics = [
                ("execution_duration", MetricType.TIMER, run.duration or 0, "seconds"),
                ("memory_peak", MetricType.GAUGE, run.memory_used or 0, "MB"),
                ("rounds_completed", MetricType.COUNTER, run.round_count or 0, "count"),
                ("data_points_processed", MetricType.COUNTER, random.randint(1000, 10000), "count"),
                ("api_calls_made", MetricType.COUNTER, random.randint(5, 25), "count"),
                ("error_rate", MetricType.ERROR_RATE, random.uniform(0, 0.05), "%"),
                ("throughput", MetricType.THROUGHPUT, random.uniform(10, 50), "ops/min"),
            ]
            
            for name, metric_type, value, unit in run_metrics:
                metric = MetricSnapshot(
                    workspace_id=task.workspace_id,
                    project_id=task.project_id,
                    task_id=task.id,
                    task_run_id=run.id,
                    name=name,
                    metric_type=metric_type,
                    value=value,
                    unit=unit,
                    labels={"scope": "run", "run_id": run.id, "task_name": task.name},
                    timestamp=run.completed_at or run.started_at
                )
                metrics.append(metric)
                session.add(metric)
    
    await session.flush()
    return metrics


async def create_sample_artifacts(session: AsyncSession, task: Task, runs: list[TaskRun]) -> list[Artifact]:
    """Create sample artifacts for tasks and runs."""
    artifacts = []
    
    # Task-level artifacts
    task_artifacts = [
        ("task_config.json", ArtifactType.CONFIG, '{"version": "1.0", "settings": {}}'),
        ("README.md", ArtifactType.DOCUMENT, f"# {task.name}\n\n## Description\n{task.description}\n\n## Usage\nThis task can be executed using the MGX agent system."),
    ]
    
    for name, artifact_type, content in task_artifacts:
        artifact = Artifact(
                        task_id=task.id,
                        name=name,
                        artifact_type=artifact_type,
                        file_path=f"/artifacts/task_{task.id}/{name}",
                        content_type="application/json" if name.endswith('.json') else "text/markdown",
                        content=content,
                        meta_data={"created_by": "seed_script", "version": "1.0"}
                    )
        artifacts.append(artifact)
        session.add(artifact)
    
    # Run-level artifacts
    for run in runs:
        if run.status == RunStatus.COMPLETED:
            # Generate a hash for file integrity
            content = json.dumps(run.results or {}, indent=2)
            file_hash = hashlib.sha256(content.encode()).hexdigest()
            
            run_artifacts = [
                ("analysis_report.md", ArtifactType.REPORT, f"# Analysis Report\n\n{run.results.get('summary', 'No summary available')}"),
                ("results.json", ArtifactType.DATA, content),
                ("metrics.csv", ArtifactType.DATA, "metric_name,value,unit\ncpu_usage,45.2,%\nmemory_usage,512.3,MB\n"),
                ("execution_log.txt", ArtifactType.LOG, f"Run {run.run_number} completed successfully\nDuration: {run.duration}s\nMemory: {run.memory_used}MB"),
            ]
            
            for name, artifact_type, content in run_artifacts:
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                
                artifact = Artifact(
                    task_id=task.id,
                    task_run_id=run.id,
                    name=name,
                    artifact_type=artifact_type,
                    file_path=f"/artifacts/run_{run.id}/{name}",
                    file_size=len(content.encode('utf-8')),
                    file_hash=content_hash,
                    content_type="text/markdown" if name.endswith('.md') else "application/json" if name.endswith('.json') else "text/csv" if name.endswith('.csv') else "text/plain",
                    content=content,
                    meta_data={
                        "created_by": "seed_script",
                        "run_number": run.run_number,
                        "execution_status": run.status,
                        "checksum": content_hash
                    }
                )
                artifacts.append(artifact)
                session.add(artifact)
    
    await session.flush()
    return artifacts


async def seed_database():
    """Main function to seed the database with sample data."""
    print("🌱 Starting database seeding...")
    
    # Create session factory
    session_factory = await get_session_factory()
    
    async with session_factory() as session:
        try:
            # Create or reuse a demo tenant
            ws_result = await session.execute(select(Workspace).where(Workspace.slug == "demo"))
            workspace = ws_result.scalar_one_or_none()
            if workspace is None:
                workspace = Workspace(name="Demo Workspace", slug="demo", meta_data={"source": "seed_data"})
                session.add(workspace)
                await session.flush()

            proj_result = await session.execute(
                select(Project).where(Project.workspace_id == workspace.id, Project.slug == "demo")
            )
            project = proj_result.scalar_one_or_none()
            if project is None:
                project = Project(
                    workspace_id=workspace.id,
                    name="Demo Project",
                    slug="demo",
                    meta_data={"source": "seed_data"},
                )
                session.add(project)
                await session.flush()

            # Sample task configurations
            sample_tasks = [
                ("Market Analysis", "Comprehensive market trend analysis for Q4 2024"),
                ("Code Review", "Automated code review and quality assessment"),
                ("Data Mining", "Extract insights from customer behavior data"),
                ("Content Generation", "Generate marketing content for social media"),
                ("Performance Benchmark", "Benchmark system performance metrics"),
                ("Security Audit", "Comprehensive security vulnerability assessment"),
                ("User Research", "Analyze user feedback and behavior patterns"),
                ("Trend Analysis", "Identify emerging technology trends"),
            ]

            print(f"Creating {len(sample_tasks)} sample tasks in workspace '{workspace.slug}'...")

            created_tasks = []
            all_runs = []
            all_metrics = []
            all_artifacts = []

            for name, description in sample_tasks:
                task = await create_sample_task(session, workspace, project, name, description)
                created_tasks.append(task)
                print(f"  ✅ Created task: {task.name}")

                runs = await create_sample_runs(session, task)
                all_runs.extend(runs)
                print(f"  ✅ Created {len(runs)} runs for task: {task.name}")

                metrics = await create_sample_metrics(session, task, runs)
                all_metrics.extend(metrics)

                artifacts = await create_sample_artifacts(session, task, runs)
                all_artifacts.extend(artifacts)

            print(f"  ✅ Created {len(all_metrics)} metrics")
            print(f"  ✅ Created {len(all_artifacts)} artifacts")
            
            # Summary statistics
            print("\n📊 Seeding Summary:")
            print(f"  • Tasks created: {len(created_tasks)}")
            print(f"  • Task runs created: {len(all_runs)}")
            print(f"  • Metrics created: {len(all_metrics)}")
            print(f"  • Artifacts created: {len(all_artifacts)}")
            
            # Database stats
            total_runs = sum(task.total_runs for task in created_tasks)
            successful_runs = sum(task.successful_runs for task in created_tasks)
            success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0
            
            print(f"  • Total executions: {total_runs}")
            print(f"  • Successful executions: {successful_runs}")
            print(f"  • Overall success rate: {success_rate:.1f}%")
            
            print("\n🎉 Database seeding completed successfully!")
            print("\nYou can now:")
            print("  • Start the API server and view the dashboard")
            print("  • Query the database for real-time task monitoring")
            print("  • Test API endpoints with realistic data")
            
        except Exception as e:
            print(f"❌ Error during seeding: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


if __name__ == "__main__":
    # Set up event loop and run seeding
    try:
        asyncio.run(seed_database())
    except KeyboardInterrupt:
        print("\n⏹️  Seeding cancelled by user")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        sys.exit(1)