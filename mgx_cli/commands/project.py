import click

@click.group()
def project():
    """Project management"""
    pass

@project.command()
def list():
    """List projects"""
    click.echo("Fetching projects...")
    # TODO: Connect to API
    click.echo("No projects found (API connection not implemented).")
