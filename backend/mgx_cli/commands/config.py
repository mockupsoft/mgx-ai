import click
from mgx_cli.utils.config_manager import get_config_value, set_config_value, load_config

@click.group()
def config():
    """Configuration management"""
    pass

@config.command()
@click.argument('key')
def get(key):
    """Get configuration value"""
    val = get_config_value(key)
    if val is None:
        click.echo(f"{key} is not set.")
    else:
        click.echo(f"{key} = {val}")

@config.command()
@click.argument('key')
@click.argument('value')
def set(key, value):
    """Set configuration value"""
    set_config_value(key, value)
    click.echo(f"Set {key} = {value}")

@config.command()
def list():
    """List all configuration"""
    cfg = load_config()
    for k, v in cfg.items():
        click.echo(f"{k} = {v}")
