# -*- coding: utf-8 -*-
"""backend.services.generator

Project Generator & Scaffold Engine

Main orchestrator service for generating project scaffolds across multiple stacks.
"""

from .generator import ProjectGenerator
from .template_manager import TemplateManager
from .engines.file_engine import FileEngine
from .engines.env_engine import EnvEngine
from .engines.docker_engine import DockerEngine
from .engines.script_engine import ScriptEngine

__all__ = [
    "ProjectGenerator",
    "TemplateManager", 
    "FileEngine",
    "EnvEngine",
    "DockerEngine",
    "ScriptEngine",
]