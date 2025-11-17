"""
Llama Stack Configuration and Initialization

This module configures the Llama Stack framework with Ollama models and MCP tool providers.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for LLM models."""

    code_analysis: str = "deepseek-coder-v2:33b"
    triage: str = "codellama:13b"
    text_generation: str = "llama3.1:8b"
    base_url: str = "http://ollama:11434"


@dataclass
class MCPServerConfig:
    """Configuration for MCP servers."""

    name: str
    command: str
    args: list[str]
    env: Dict[str, str]


class LlamaStackConfig:
    """Manages Llama Stack configuration and initialization."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize Llama Stack configuration.

        Args:
            config_path: Path to agent configuration YAML file
        """
        self.config_path = config_path or os.getenv(
            "AGENT_CONFIG_PATH",
            "/app/config/agent-config.yaml"
        )
        self.config = self._load_config()
        self.model_config = self._load_model_config()
        self.mcp_servers = self._load_mcp_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load agent configuration from YAML file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return yaml.safe_load(f)
            else:
                logger.warning(f"Config file not found: {self.config_path}, using defaults")
                return self._default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "agent": {
                "name": "SonarQube Analysis Agent",
                "version": "1.0.0"
            },
            "llm": {
                "provider": "ollama",
                "base_url": os.getenv("OLLAMA_HOST", "http://ollama:11434"),
                "models": {
                    "primary": "deepseek-coder-v2:33b",
                    "secondary": "codellama:13b",
                    "lightweight": "llama3.1:8b"
                }
            },
            "sonarqube": {
                "url": os.getenv("SONARQUBE_URL", ""),
                "token": os.getenv("SONARQUBE_TOKEN", ""),
                "projects": os.getenv("SONARQUBE_PROJECTS", "").split(",") if os.getenv("SONARQUBE_PROJECTS") else [],
                "severities": ["CRITICAL", "HIGH"]
            },
            "github": {
                "token": os.getenv("GITHUB_TOKEN", ""),
                "repositories": []
            },
            "behavior": {
                "false_positive": {
                    "min_confidence": 0.85,
                    "auto_mark": True,
                    "require_review_below": 0.70
                },
                "fix_generation": {
                    "min_confidence": 0.90,
                    "auto_create_pr": True,
                    "request_copilot_review": True,
                    "supported_patterns": [
                        "null_pointer",
                        "resource_leak",
                        "sql_injection",
                        "hardcoded_credentials",
                        "insecure_random"
                    ]
                },
                "prioritization": {
                    "auto_fix_priorities": ["P0", "P1"],
                    "escalate_priorities": ["P0"]
                },
                "rate_limiting": {
                    "max_prs_per_hour": 5,
                    "max_comments_per_hour": 20,
                    "poll_interval_seconds": 300
                }
            }
        }

    def _load_model_config(self) -> ModelConfig:
        """Load model configuration."""
        llm_config = self.config.get("llm", {})
        base_url = llm_config.get("base_url", "http://ollama:11434")
        models = llm_config.get("models", {})

        return ModelConfig(
            code_analysis=models.get("primary", "deepseek-coder-v2:33b"),
            triage=models.get("secondary", "codellama:13b"),
            text_generation=models.get("lightweight", "llama3.1:8b"),
            base_url=base_url
        )

    def _load_mcp_config(self) -> Dict[str, MCPServerConfig]:
        """Load MCP server configurations."""
        mcp_servers = {}

        # SonarQube MCP Server
        mcp_servers["sonarqube"] = MCPServerConfig(
            name="sonarqube",
            command="npx",
            args=["-y", "@sonarsource/sonarqube-mcp-server"],
            env={
                "SONARQUBE_URL": self.config["sonarqube"]["url"],
                "SONARQUBE_TOKEN": self.config["sonarqube"]["token"]
            }
        )

        # GitHub MCP Server
        mcp_servers["github"] = MCPServerConfig(
            name="github",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={
                "GITHUB_PERSONAL_ACCESS_TOKEN": self.config["github"]["token"]
            }
        )

        return mcp_servers

    def get_model_for_task(self, task: str) -> str:
        """
        Get appropriate model for a specific task based on complexity.

        Args:
            task: Task type (analyze_code_context, generate_fix, detect_false_positive, etc.)

        Returns:
            Model identifier string
        """
        task_routing = {
            "analyze_code_context": self.model_config.code_analysis,
            "generate_fix": self.model_config.code_analysis,
            "detect_false_positive": self.model_config.triage,
            "calculate_risk": self.model_config.triage,
            "generate_pr_description": self.model_config.text_generation,
            "generate_comment": self.model_config.text_generation,
        }

        return task_routing.get(task, self.model_config.triage)

    def get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return """You are an expert code security analyst and software engineer.
Your role is to analyze SonarQube findings, distinguish false positives
from real issues, and generate high-quality fixes when possible.

Guidelines:
- Be conservative: prefer false negatives over false positives
- Generate minimal, targeted fixes that preserve functionality
- Explain your reasoning clearly for human reviewers
- Escalate complex issues that require human judgment
- Always consider the business context and impact
- Focus on security vulnerabilities and code quality issues
- Provide detailed evidence for your conclusions
- When generating fixes, ensure they follow language idioms and best practices
"""

    def get_behavior_config(self, category: str) -> Dict[str, Any]:
        """
        Get behavior configuration for a specific category.

        Args:
            category: Configuration category (false_positive, fix_generation, etc.)

        Returns:
            Configuration dictionary
        """
        return self.config.get("behavior", {}).get(category, {})
