"""DeepAgents package."""

# Import directly from the current package (no nested structure)
from .graph import create_deep_agent
from .middleware.filesystem import FilesystemMiddleware
from .middleware.subagents import CompiledSubAgent, SubAgent, SubAgentMiddleware

__all__ = [
    "CompiledSubAgent",
    "FilesystemMiddleware",
    "SubAgent",
    "SubAgentMiddleware",
    "create_deep_agent",
]
