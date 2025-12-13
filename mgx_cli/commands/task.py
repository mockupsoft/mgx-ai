import click
import asyncio
import json
import sys
from pathlib import Path

# Try to import from mgx_agent
try:
    from mgx_agent.team import MGXStyleTeam
    from mgx_agent.config import TeamConfig
except ImportError:
    # If mgx_agent is not installed/found, we might be in a different context
    # But for this task, we assume it's available.
    MGXStyleTeam = None
    TeamConfig = None

@click.command()
@click.argument('description', required=False)
@click.option('--json', 'json_file', type=click.Path(exists=True), help='Structured JSON input file')
@click.option('--project-path', type=click.Path(), help='Path to the project')
def task(description, json_file, project_path):
    """Create and run a task"""
    if not MGXStyleTeam:
        click.echo("Error: mgx_agent package not found. Please install it.", err=True)
        sys.exit(1)

    if json_file:
        click.echo(f"Running task from JSON: {json_file}")
        asyncio.run(run_json_task(json_file))
    elif description:
        click.echo(f"Running task: {description}")
        asyncio.run(run_task(description, project_path))
    else:
        click.echo("Error: Please provide a task description or a JSON input file.", err=True)
        click.echo(task.get_help(click.get_current_context()))
        sys.exit(1)

async def run_task(description, project_path):
    config = TeamConfig()
    if project_path:
        # In a real implementation, we would set project path in config
        pass
    
    mgx_team = MGXStyleTeam(config=config)
    
    print("\n📋 ADIM 1: Görev Analizi ve Plan Oluşturma")
    await mgx_team.analyze_and_plan(description)
    
    print("\n✅ ADIM 2: Plan Onayı")
    # In CLI interactive mode, we might want to ask for confirmation
    # For now, auto approve as in existing CLI or implement prompt
    if click.confirm('Do you approve the plan?'):
        mgx_team.approve_plan()
        
        print("\n🚀 ADIM 3: Görev Yürütme")
        await mgx_team.execute()
        
        print("\n📊 ADIM 4: Sonuç")
        print(mgx_team.get_progress())
    else:
        print("Plan rejected. Aborting.")

async def run_json_task(json_path):
    # Load JSON and run similar logic to mgx_agent.cli.json_input_main
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            task_input = json.load(f)
    except Exception as e:
        click.echo(f"Error loading JSON: {e}", err=True)
        return

    task_desc = task_input.get("task")
    if not task_desc:
        click.echo("Error: 'task' field is required in JSON", err=True)
        return

    config = TeamConfig(
        target_stack=task_input.get("target_stack"),
        project_type=task_input.get("project_type"),
        output_mode=task_input.get("output_mode", "generate_new"),
        strict_requirements=task_input.get("strict_requirements", False),
        existing_project_path=task_input.get("existing_project_path"),
        constraints=task_input.get("constraints", []),
    )
    
    mgx_team = MGXStyleTeam(config=config)
    await mgx_team.analyze_and_plan(task_desc)
    mgx_team.approve_plan()
    await mgx_team.execute()
    print(mgx_team.get_progress())
