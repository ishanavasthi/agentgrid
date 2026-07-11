"""AgentGrid exception types."""


class AgentGridError(Exception):
    """Base error for AgentGrid."""


class ConfigError(AgentGridError):
    """Missing/invalid configuration (e.g. no API key for a real backend)."""


class BackendUnavailable(AgentGridError):
    """A requested LLM backend cannot run in this environment."""


class ToolError(AgentGridError):
    """A tool call failed or was rejected (e.g. path escape attempt)."""


class PipelineError(AgentGridError):
    """The orchestrated pipeline could not complete."""
