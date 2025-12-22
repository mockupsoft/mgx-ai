import click

@click.group()
def workspace():
    """Workspace management"""
    pass

@workspace.command()
def list():
    """List workspaces"""
    click.echo("Fetching workspaces...")
    # TODO: Connect to API
    click.echo("No workspaces found (API connection not implemented).")
