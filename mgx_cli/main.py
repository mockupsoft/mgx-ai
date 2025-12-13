import click
import os
import sys
import json
import yaml
from pathlib import Path
from mgx_cli import __version__
from mgx_cli.commands import task, init, config, workspace, project

@click.group()
@click.version_option(__version__, prog_name="mgx")
@click.pass_context
def cli(ctx):
    """MGX AI CLI Tool - Global Expansion Package"""
    ctx.ensure_object(dict)
    # Load config here if needed
    
cli.add_command(task.task)
cli.add_command(init.init)
cli.add_command(config.config)
cli.add_command(workspace.workspace)
cli.add_command(project.project)

# Add aliases or direct commands if needed, e.g. list, status, logs
# The requirement says `mgx list`, `mgx status`, `mgx logs`. 
# These could be separate commands or aliases.
# I will implement them as top level commands for now as per requirement.

@cli.command()
def list():
    """List tasks"""
    click.echo("Listing tasks...")
    # Implementation to follow

@cli.command()
@click.argument('task_id')
def status(task_id):
    """Get task status"""
    click.echo(f"Status for task {task_id}...")

@cli.command()
@click.argument('task_id')
def logs(task_id):
    """Get task execution logs"""
    click.echo(f"Logs for task {task_id}...")

if __name__ == '__main__':
    cli()
