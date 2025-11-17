"""
GitHub Integration Module

Handles communication with GitHub via MCP server for fetching code,
creating branches, committing fixes, and managing pull requests.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PullRequest:
    """Represents a GitHub pull request."""

    number: int
    title: str
    html_url: str
    state: str
    head_branch: str
    base_branch: str


class GitHubClient:
    """Client for interacting with GitHub via MCP server."""

    def __init__(self, mcp_client: Any, config: Dict[str, Any]):
        """
        Initialize GitHub client.

        Args:
            mcp_client: MCP client instance for GitHub
            config: GitHub configuration dictionary
        """
        self.mcp_client = mcp_client
        self.config = config
        self.token = config.get("token", "")
        self.repositories = config.get("repositories", [])

    async def get_file_contents(
        self,
        repo: str,
        path: str,
        ref: str = "main"
    ) -> Optional[str]:
        """
        Fetch file contents from GitHub repository.

        Args:
            repo: Repository in format "owner/repo"
            path: File path within repository
            ref: Git reference (branch, tag, or commit SHA)

        Returns:
            File contents as string
        """
        try:
            owner, repo_name = repo.split("/")
            result = await self.mcp_client.call_tool(
                "github_get_file_contents",
                arguments={
                    "owner": owner,
                    "repo": repo_name,
                    "path": path,
                    "ref": ref
                }
            )
            return result.get("content", "")
        except Exception as e:
            logger.error(f"Error fetching file {path} from {repo}: {e}")
            return None

    async def search_code(
        self,
        repo: str,
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Search for code patterns in repository.

        Args:
            repo: Repository in format "owner/repo"
            query: Search query

        Returns:
            List of search results
        """
        try:
            owner, repo_name = repo.split("/")
            result = await self.mcp_client.call_tool(
                "github_search_code",
                arguments={
                    "owner": owner,
                    "repo": repo_name,
                    "query": query
                }
            )
            return result.get("items", [])
        except Exception as e:
            logger.error(f"Error searching code in {repo}: {e}")
            return []

    async def create_branch(
        self,
        repo: str,
        branch_name: str,
        from_branch: str = "main"
    ) -> bool:
        """
        Create a new branch in the repository.

        Args:
            repo: Repository in format "owner/repo"
            branch_name: Name for the new branch
            from_branch: Source branch to branch from

        Returns:
            True if successful, False otherwise
        """
        try:
            owner, repo_name = repo.split("/")
            await self.mcp_client.call_tool(
                "github_create_branch",
                arguments={
                    "owner": owner,
                    "repo": repo_name,
                    "branch": branch_name,
                    "from_branch": from_branch
                }
            )
            logger.info(f"Created branch {branch_name} in {repo}")
            return True
        except Exception as e:
            logger.error(f"Error creating branch {branch_name} in {repo}: {e}")
            return False

    async def create_or_update_file(
        self,
        repo: str,
        branch: str,
        path: str,
        content: str,
        message: str
    ) -> bool:
        """
        Create or update a file in the repository.

        Args:
            repo: Repository in format "owner/repo"
            branch: Branch to commit to
            path: File path
            content: File content
            message: Commit message

        Returns:
            True if successful, False otherwise
        """
        try:
            owner, repo_name = repo.split("/")
            await self.mcp_client.call_tool(
                "github_create_or_update_file",
                arguments={
                    "owner": owner,
                    "repo": repo_name,
                    "path": path,
                    "content": content,
                    "message": message,
                    "branch": branch
                }
            )
            logger.info(f"Updated file {path} in {repo}:{branch}")
            return True
        except Exception as e:
            logger.error(f"Error updating file {path} in {repo}: {e}")
            return False

    async def create_pull_request(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        labels: Optional[List[str]] = None
    ) -> Optional[PullRequest]:
        """
        Create a pull request.

        Args:
            repo: Repository in format "owner/repo"
            title: PR title
            body: PR description (supports markdown)
            head: Head branch (source of changes)
            base: Base branch (target branch)
            labels: Optional list of labels to add

        Returns:
            PullRequest object if successful, None otherwise
        """
        try:
            owner, repo_name = repo.split("/")
            params = {
                "owner": owner,
                "repo": repo_name,
                "title": title,
                "body": body,
                "head": head,
                "base": base
            }

            result = await self.mcp_client.call_tool(
                "github_create_pull_request",
                arguments=params
            )

            pr = PullRequest(
                number=result.get("number"),
                title=result.get("title"),
                html_url=result.get("html_url"),
                state=result.get("state"),
                head_branch=head,
                base_branch=base
            )

            # Add labels if specified
            if labels:
                await self.add_labels_to_pr(repo, pr.number, labels)

            logger.info(f"Created PR #{pr.number} in {repo}: {pr.html_url}")
            return pr

        except Exception as e:
            logger.error(f"Error creating PR in {repo}: {e}")
            return None

    async def add_labels_to_pr(
        self,
        repo: str,
        pr_number: int,
        labels: List[str]
    ) -> bool:
        """
        Add labels to a pull request.

        Args:
            repo: Repository in format "owner/repo"
            pr_number: PR number
            labels: List of label names

        Returns:
            True if successful, False otherwise
        """
        try:
            owner, repo_name = repo.split("/")
            await self.mcp_client.call_tool(
                "github_add_labels",
                arguments={
                    "owner": owner,
                    "repo": repo_name,
                    "issue_number": pr_number,
                    "labels": labels
                }
            )
            logger.info(f"Added labels to PR #{pr_number}: {labels}")
            return True
        except Exception as e:
            logger.error(f"Error adding labels to PR #{pr_number}: {e}")
            return False

    async def request_copilot_review(
        self,
        repo: str,
        pull_number: int
    ) -> bool:
        """
        Request GitHub Copilot review for a pull request.

        Args:
            repo: Repository in format "owner/repo"
            pull_number: PR number

        Returns:
            True if successful, False otherwise
        """
        try:
            owner, repo_name = repo.split("/")
            await self.mcp_client.call_tool(
                "github_request_copilot_review",
                arguments={
                    "owner": owner,
                    "repo": repo_name,
                    "pull_number": pull_number
                }
            )
            logger.info(f"Requested Copilot review for PR #{pull_number}")
            return True
        except Exception as e:
            logger.error(f"Error requesting Copilot review for PR #{pull_number}: {e}")
            return False

    async def get_file_history(
        self,
        repo: str,
        path: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get commit history for a specific file.

        Args:
            repo: Repository in format "owner/repo"
            path: File path
            limit: Maximum number of commits to retrieve

        Returns:
            List of commit information
        """
        try:
            owner, repo_name = repo.split("/")
            result = await self.mcp_client.call_tool(
                "github_get_commits",
                arguments={
                    "owner": owner,
                    "repo": repo_name,
                    "path": path,
                    "per_page": limit
                }
            )
            return result.get("commits", [])
        except Exception as e:
            logger.error(f"Error fetching file history for {path}: {e}")
            return []

    def extract_repo_from_component(self, component: str) -> Optional[str]:
        """
        Extract repository identifier from SonarQube component key.

        Args:
            component: SonarQube component key

        Returns:
            Repository in "owner/repo" format, or None
        """
        # Implementation depends on how SonarQube component keys map to repos
        # This is a placeholder - adjust based on your setup
        for repo_config in self.repositories:
            if isinstance(repo_config, dict):
                owner = repo_config.get("owner")
                name = repo_config.get("name")
                if owner and name:
                    return f"{owner}/{name}"

        # Fallback: try to parse from environment
        return None
