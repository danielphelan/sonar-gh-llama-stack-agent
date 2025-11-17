"""
SonarQube Integration Module

Handles communication with SonarQube via MCP server for fetching issues,
adding comments, and managing issue lifecycle.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SonarQubeFinding:
    """Represents a SonarQube finding/issue."""

    key: str
    rule_key: str
    rule_name: str
    severity: str
    message: str
    file_path: str
    line: int
    status: str
    project: str
    component: str
    creation_date: str
    language: Optional[str] = None


class SonarQubeClient:
    """Client for interacting with SonarQube via MCP server."""

    def __init__(self, mcp_client: Any, config: Dict[str, Any]):
        """
        Initialize SonarQube client.

        Args:
            mcp_client: MCP client instance for SonarQube
            config: SonarQube configuration dictionary
        """
        self.mcp_client = mcp_client
        self.config = config
        self.url = config.get("url", "")
        self.projects = config.get("projects", [])
        self.severities = config.get("severities", ["CRITICAL", "HIGH"])

    async def get_issues(
        self,
        severity: Optional[List[str]] = None,
        status: str = "OPEN",
        created_after: Optional[str] = None
    ) -> List[SonarQubeFinding]:
        """
        Fetch issues from SonarQube.

        Args:
            severity: List of severity levels to filter (default: CRITICAL, HIGH)
            status: Issue status filter (default: OPEN)
            created_after: ISO timestamp to fetch only recent issues

        Returns:
            List of SonarQube findings
        """
        try:
            severity = severity or self.severities

            # Build query parameters
            params = {
                "severities": ",".join(severity),
                "statuses": status,
                "projects": ",".join(self.projects) if self.projects else None,
            }

            if created_after:
                params["createdAfter"] = created_after

            # Call MCP server tool
            result = await self.mcp_client.call_tool(
                "sonarqube_get_issues",
                arguments=params
            )

            # Parse response into SonarQubeFinding objects
            findings = []
            for issue in result.get("issues", []):
                findings.append(self._parse_issue(issue))

            logger.info(f"Fetched {len(findings)} issues from SonarQube")
            return findings

        except Exception as e:
            logger.error(f"Error fetching SonarQube issues: {e}")
            return []

    async def get_issue_details(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific issue.

        Args:
            issue_key: SonarQube issue key

        Returns:
            Detailed issue information
        """
        try:
            result = await self.mcp_client.call_tool(
                "sonarqube_get_issue_details",
                arguments={"issueKey": issue_key}
            )
            return result
        except Exception as e:
            logger.error(f"Error fetching issue details for {issue_key}: {e}")
            return None

    async def get_source_code(
        self,
        component: str,
        from_line: int,
        to_line: int
    ) -> Optional[str]:
        """
        Retrieve source code context from SonarQube.

        Args:
            component: Component key (file path)
            from_line: Starting line number
            to_line: Ending line number

        Returns:
            Source code snippet
        """
        try:
            result = await self.mcp_client.call_tool(
                "sonarqube_get_sources",
                arguments={
                    "component": component,
                    "from": from_line,
                    "to": to_line
                }
            )
            return result.get("sources", "")
        except Exception as e:
            logger.error(f"Error fetching source code: {e}")
            return None

    async def get_rule_details(self, rule_key: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a SonarQube rule.

        Args:
            rule_key: Rule identifier (e.g., java:S2259)

        Returns:
            Rule details including description and remediation
        """
        try:
            result = await self.mcp_client.call_tool(
                "sonarqube_get_rule",
                arguments={"ruleKey": rule_key}
            )
            return result
        except Exception as e:
            logger.error(f"Error fetching rule details for {rule_key}: {e}")
            return None

    async def add_comment(self, issue_key: str, comment: str) -> bool:
        """
        Add a comment to a SonarQube issue.

        Args:
            issue_key: Issue key
            comment: Comment text (supports markdown)

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.mcp_client.call_tool(
                "sonarqube_add_comment",
                arguments={
                    "issueKey": issue_key,
                    "text": comment
                }
            )
            logger.info(f"Added comment to issue {issue_key}")
            return True
        except Exception as e:
            logger.error(f"Error adding comment to {issue_key}: {e}")
            return False

    async def transition_issue(
        self,
        issue_key: str,
        transition: str,
        comment: Optional[str] = None
    ) -> bool:
        """
        Change the status of an issue.

        Args:
            issue_key: Issue key
            transition: Transition name (e.g., "wontfix", "falsepositive", "resolve")
            comment: Optional comment explaining the transition

        Returns:
            True if successful, False otherwise
        """
        try:
            params = {
                "issueKey": issue_key,
                "transition": transition
            }
            if comment:
                params["comment"] = comment

            await self.mcp_client.call_tool(
                "sonarqube_transition_issue",
                arguments=params
            )
            logger.info(f"Transitioned issue {issue_key} to {transition}")
            return True
        except Exception as e:
            logger.error(f"Error transitioning issue {issue_key}: {e}")
            return False

    async def assign_issue(
        self,
        issue_key: str,
        assignee: str,
        comment: Optional[str] = None
    ) -> bool:
        """
        Assign an issue to a user.

        Args:
            issue_key: Issue key
            assignee: Username to assign to
            comment: Optional comment

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.mcp_client.call_tool(
                "sonarqube_assign_issue",
                arguments={
                    "issueKey": issue_key,
                    "assignee": assignee
                }
            )

            if comment:
                await self.add_comment(issue_key, comment)

            logger.info(f"Assigned issue {issue_key} to {assignee}")
            return True
        except Exception as e:
            logger.error(f"Error assigning issue {issue_key}: {e}")
            return False

    async def search_similar_issues(
        self,
        rule_key: str,
        file_path: Optional[str] = None,
        resolved: bool = False
    ) -> List[SonarQubeFinding]:
        """
        Search for similar issues in the project history.

        Args:
            rule_key: Rule key to search for
            file_path: Optional file path filter
            resolved: Whether to include resolved issues

        Returns:
            List of similar findings
        """
        try:
            params = {
                "rules": rule_key,
                "resolved": "true" if resolved else "false"
            }

            if file_path:
                params["componentKeys"] = file_path

            result = await self.mcp_client.call_tool(
                "sonarqube_get_issues",
                arguments=params
            )

            findings = []
            for issue in result.get("issues", []):
                findings.append(self._parse_issue(issue))

            return findings
        except Exception as e:
            logger.error(f"Error searching similar issues: {e}")
            return []

    def _parse_issue(self, issue_data: Dict[str, Any]) -> SonarQubeFinding:
        """Parse raw issue data into SonarQubeFinding object."""
        return SonarQubeFinding(
            key=issue_data.get("key", ""),
            rule_key=issue_data.get("rule", ""),
            rule_name=issue_data.get("ruleName", ""),
            severity=issue_data.get("severity", ""),
            message=issue_data.get("message", ""),
            file_path=issue_data.get("component", "").split(":")[-1],  # Extract file path
            line=issue_data.get("line", 0),
            status=issue_data.get("status", ""),
            project=issue_data.get("project", ""),
            component=issue_data.get("component", ""),
            creation_date=issue_data.get("creationDate", ""),
            language=issue_data.get("language")
        )
