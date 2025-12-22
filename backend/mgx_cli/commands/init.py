import click
import os
import yaml
from pathlib import Path

@click.command()
@click.argument('project_path', type=click.Path())
def init(project_path):
    """Initialize new project"""
    path = Path(project_path)
    if not path.exists():
        path.mkdir(parents=True)
        click.echo(f"Created directory: {path}")
    
    config_file = path / "mgx.yaml"
    if config_file.exists():
        click.echo(f"Config file already exists: {config_file}")
        return

    default_config = {
        "project_name": path.name,
        "version": "0.1.0",
        "stack": "auto",
        "workflows": {
            "default": "standard"
        }
    }
    
    with open(config_file, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False)
    
    click.echo(f"Initialized mgx project at {project_path}")
    click.echo(f"Created {config_file}")
