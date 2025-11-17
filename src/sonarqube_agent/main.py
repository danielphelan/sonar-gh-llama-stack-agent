"""
Main Entry Point for SonarQube Analysis Agent

Initializes the agent with Llama Stack, MCP servers, and starts processing.
"""

import asyncio
import os
import sys
from typing import Optional
import argparse

from .utils.logging_config import setup_logging, get_logger
from .agent.llama_stack_config import LlamaStackConfig
from .agent.agent_core import SonarQubeAgent
from .integrations.sonarqube import SonarQubeClient
from .integrations.github import GitHubClient

logger = get_logger(__name__)


class MockLLMClient:
    """
    Mock LLM client for demonstration purposes.
    In production, replace this with actual Llama Stack client.
    """

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model
        logger.warning(
            "Using MockLLMClient - replace with actual Llama Stack client for production"
        )

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Mock generate method.
        Replace with actual LLM API call to Ollama via Llama Stack.
        """
        logger.debug(f"LLM Generate called with model: {model or self.model}")

        # In production, this would call:
        # response = await ollama_client.generate(
        #     model=model or self.model,
        #     prompt=prompt,
        #     temperature=temperature
        # )
        # return response.text

        # Mock response for demonstration
        return '{"is_false_positive": false, "confidence": 0.5, "reasoning": "Mock analysis", "evidence": [], "recommendation": "Manual review"}'


class MockMCPClient:
    """
    Mock MCP client for demonstration purposes.
    In production, replace with actual MCP client.
    """

    def __init__(self, server_name: str):
        self.server_name = server_name
        logger.warning(
            f"Using MockMCPClient for {server_name} - replace with actual MCP client"
        )

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """
        Mock tool call method.
        Replace with actual MCP protocol call.
        """
        logger.debug(f"MCP Tool called: {self.server_name}.{tool_name}")

        # In production, this would call:
        # response = await mcp_client.call_tool(tool_name, arguments)
        # return response

        # Mock response
        return {
            "issues": [],
            "content": "",
            "sources": "",
        }


async def initialize_agent(config_path: Optional[str] = None) -> SonarQubeAgent:
    """
    Initialize the SonarQube Analysis Agent with all dependencies.

    Args:
        config_path: Path to configuration file

    Returns:
        Initialized SonarQubeAgent instance
    """
    logger.info("Initializing SonarQube Analysis Agent...")

    # Load configuration
    stack_config = LlamaStackConfig(config_path)

    # Initialize LLM client (Ollama via Llama Stack)
    # TODO: Replace MockLLMClient with actual Llama Stack client
    # from llama_stack_client import LlamaStackClient
    # llm_client = LlamaStackClient(base_url=stack_config.model_config.base_url)

    llm_client = MockLLMClient(
        base_url=stack_config.model_config.base_url,
        model=stack_config.model_config.code_analysis
    )

    # Initialize MCP clients
    # TODO: Replace MockMCPClient with actual MCP client
    # from mcp import Client as MCPClient
    # sonarqube_mcp = MCPClient(stack_config.mcp_servers["sonarqube"])
    # github_mcp = MCPClient(stack_config.mcp_servers["github"])

    sonarqube_mcp = MockMCPClient("sonarqube")
    github_mcp = MockMCPClient("github")

    # Initialize integration clients
    sonarqube_client = SonarQubeClient(
        mcp_client=sonarqube_mcp,
        config=stack_config.config["sonarqube"]
    )

    github_client = GitHubClient(
        mcp_client=github_mcp,
        config=stack_config.config["github"]
    )

    # Create agent
    agent = SonarQubeAgent(
        sonarqube_client=sonarqube_client,
        github_client=github_client,
        llm_client=llm_client,
        config=stack_config.config
    )

    logger.info("Agent initialized successfully")
    return agent


async def main_async(args: argparse.Namespace) -> None:
    """
    Async main function.

    Args:
        args: Command-line arguments
    """
    # Initialize agent
    agent = await initialize_agent(args.config)

    # Run agent
    if args.once:
        logger.info("Running agent once...")
        await agent.run_once(created_after=args.created_after)
    else:
        logger.info("Running agent in continuous mode...")
        await agent.run_continuous(poll_interval=args.poll_interval)


def main() -> None:
    """Main entry point."""

    # Parse arguments
    parser = argparse.ArgumentParser(
        description="SonarQube Analysis Agent - Automated security finding analysis and fixes"
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Path to agent configuration file",
        default=None
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level"
    )

    parser.add_argument(
        "--log-file",
        type=str,
        help="Path to log file (optional)",
        default=None
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once instead of continuous polling"
    )

    parser.add_argument(
        "--created-after",
        type=str,
        help="Process only findings created after this ISO timestamp (for --once mode)",
        default=None
    )

    parser.add_argument(
        "--poll-interval",
        type=int,
        help="Poll interval in seconds (for continuous mode)",
        default=None
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - analyze but don't make changes"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(level=args.log_level, log_file=args.log_file)

    logger.info("=" * 60)
    logger.info("SonarQube Analysis Agent v1.0")
    logger.info("=" * 60)

    if args.dry_run:
        logger.warning("DRY RUN MODE - No changes will be made")
        # Set environment variable for components to check
        os.environ["DRY_RUN"] = "true"

    try:
        # Run async main
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
