"""
Agent Core Module

Main orchestration logic for the SonarQube Analysis Agent.
Coordinates finding analysis, fix generation, and PR creation.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ..integrations.sonarqube import SonarQubeClient, SonarQubeFinding
from ..integrations.github import GitHubClient, PullRequest
from ..analyzers.false_positive import FalsePositiveDetector, FalsePositiveAnalysis
from ..analyzers.risk_assessment import RiskAssessor, RiskAssessment
from ..analyzers.fix_generator import FixGenerator, FixResult
from ..utils.pr_templates import PRTemplateGenerator

logger = logging.getLogger(__name__)


class SonarQubeAgent:
    """
    Main agent that analyzes SonarQube findings and generates automated fixes.
    """

    def __init__(
        self,
        sonarqube_client: SonarQubeClient,
        github_client: GitHubClient,
        llm_client: Any,
        config: Dict[str, Any]
    ):
        """
        Initialize the SonarQube Analysis Agent.

        Args:
            sonarqube_client: SonarQube MCP client
            github_client: GitHub MCP client
            llm_client: LLM client for analysis
            config: Agent configuration dictionary
        """
        self.sonarqube = sonarqube_client
        self.github = github_client
        self.llm_client = llm_client
        self.config = config

        # Initialize analyzers
        self.fp_detector = FalsePositiveDetector(llm_client)
        self.risk_assessor = RiskAssessor(llm_client)
        self.fix_generator = FixGenerator(llm_client)

        # Behavior configuration
        self.behavior = config.get("behavior", {})
        self.fp_config = self.behavior.get("false_positive", {})
        self.fix_config = self.behavior.get("fix_generation", {})
        self.priority_config = self.behavior.get("prioritization", {})
        self.rate_limit_config = self.behavior.get("rate_limiting", {})

        # Rate limiting tracking
        self.prs_created_this_hour = 0
        self.comments_posted_this_hour = 0
        self.rate_limit_reset_time = datetime.now() + timedelta(hours=1)

        # Statistics
        self.stats = {
            "findings_analyzed": 0,
            "false_positives_detected": 0,
            "fixes_generated": 0,
            "prs_created": 0,
            "errors": 0
        }

    async def run_continuous(self, poll_interval: Optional[int] = None) -> None:
        """
        Run the agent in continuous polling mode.

        Args:
            poll_interval: Poll interval in seconds (default from config)
        """
        interval = poll_interval or self.rate_limit_config.get("poll_interval_seconds", 300)

        logger.info(f"Starting SonarQube Analysis Agent in continuous mode (poll every {interval}s)")

        last_run_time = None

        while True:
            try:
                # Reset rate limits if needed
                self._reset_rate_limits_if_needed()

                # Fetch new findings
                findings = await self._fetch_new_findings(last_run_time)

                logger.info(f"Found {len(findings)} new issues to analyze")

                # Process each finding
                for finding in findings:
                    try:
                        await self.process_finding(finding)
                    except Exception as e:
                        logger.error(f"Error processing finding {finding.key}: {e}", exc_info=True)
                        self.stats["errors"] += 1

                last_run_time = datetime.now().isoformat()

                # Log statistics
                self._log_statistics()

                # Wait for next poll
                logger.info(f"Sleeping for {interval} seconds...")
                await asyncio.sleep(interval)

            except KeyboardInterrupt:
                logger.info("Shutting down agent...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def run_once(self, created_after: Optional[str] = None) -> None:
        """
        Run the agent once (for testing or scheduled jobs).

        Args:
            created_after: Only process findings created after this timestamp
        """
        logger.info("Running SonarQube Analysis Agent (single run)")

        findings = await self._fetch_new_findings(created_after)

        logger.info(f"Found {len(findings)} issues to analyze")

        for finding in findings:
            try:
                await self.process_finding(finding)
            except Exception as e:
                logger.error(f"Error processing finding {finding.key}: {e}", exc_info=True)
                self.stats["errors"] += 1

        self._log_statistics()

    async def process_finding(self, finding: SonarQubeFinding) -> None:
        """
        Complete workflow for processing a single SonarQube finding.

        Args:
            finding: SonarQubeFinding object to process
        """
        logger.info(f"[{finding.key}] Processing finding: {finding.rule_name}")

        self.stats["findings_analyzed"] += 1

        # PHASE 1: Fetch code context
        code_context = await self._get_code_context(finding)
        if not code_context:
            logger.warning(f"[{finding.key}] Could not fetch code context")
            return

        # Get rule details
        rule_details = await self.sonarqube.get_rule_details(finding.rule_key)

        # PHASE 2: False Positive Detection
        logger.info(f"[{finding.key}] Running false positive analysis...")

        fp_analysis = await self.fp_detector.analyze(
            finding=finding,
            code_context=code_context,
            rule_details=rule_details
        )

        min_confidence = self.fp_config.get("min_confidence", 0.85)

        if fp_analysis.is_false_positive and fp_analysis.confidence >= min_confidence:
            logger.info(
                f"[{finding.key}] FALSE POSITIVE detected "
                f"(confidence: {fp_analysis.confidence:.0%})"
            )
            await self._handle_false_positive(finding, fp_analysis)
            self.stats["false_positives_detected"] += 1
            return

        # PHASE 3: Risk Assessment
        logger.info(f"[{finding.key}] Calculating risk score...")

        risk_assessment = await self.risk_assessor.assess(
            finding=finding,
            code_context=code_context,
            rule_details=rule_details
        )

        logger.info(
            f"[{finding.key}] Risk Score: {risk_assessment.risk_score:.1f} "
            f"(Priority: {risk_assessment.priority})"
        )

        # Post risk assessment comment
        if self._check_rate_limit("comment"):
            risk_comment = self.risk_assessor.generate_comment(risk_assessment, finding)
            await self.sonarqube.add_comment(finding.key, risk_comment)
            self.comments_posted_this_hour += 1

        # PHASE 4: Fix Generation (for high-priority issues)
        auto_fix_priorities = self.priority_config.get("auto_fix_priorities", ["P0", "P1"])

        if risk_assessment.priority in auto_fix_priorities:
            logger.info(f"[{finding.key}] Attempting to generate automated fix...")

            # Get full file content
            full_file = await self._get_full_file(finding)

            if full_file:
                fix_result = await self.fix_generator.generate_fix(
                    finding=finding,
                    code_context=code_context,
                    full_file_content=full_file,
                    rule_details=rule_details
                )

                if fix_result and fix_result.validation.is_safe:
                    min_fix_confidence = self.fix_config.get("min_confidence", 0.90)

                    if fix_result.confidence >= min_fix_confidence:
                        logger.info(f"[{finding.key}] Fix generated successfully")
                        await self._create_fix_pr(finding, fix_result, risk_assessment)
                        self.stats["fixes_generated"] += 1
                        self.stats["prs_created"] += 1
                    else:
                        logger.warning(
                            f"[{finding.key}] Fix confidence too low: "
                            f"{fix_result.confidence:.0%} < {min_fix_confidence:.0%}"
                        )
                        await self._escalate_to_human(
                            finding, risk_assessment, "Low confidence fix"
                        )
                else:
                    logger.warning(f"[{finding.key}] Could not generate safe fix")
                    await self._escalate_to_human(
                        finding, risk_assessment, "Complex fix required"
                    )
        else:
            logger.info(
                f"[{finding.key}] Priority {risk_assessment.priority} - "
                f"not auto-fixing (tracking only)"
            )

    async def _fetch_new_findings(
        self,
        created_after: Optional[str]
    ) -> list[SonarQubeFinding]:
        """Fetch new findings from SonarQube."""
        return await self.sonarqube.get_issues(
            severity=None,  # Use configured severities
            status="OPEN",
            created_after=created_after
        )

    async def _get_code_context(
        self,
        finding: SonarQubeFinding,
        context_lines: int = 20
    ) -> Optional[str]:
        """Get code context around the finding."""
        try:
            # Try to get from SonarQube first
            from_line = max(1, finding.line - context_lines)
            to_line = finding.line + context_lines

            code = await self.sonarqube.get_source_code(
                component=finding.component,
                from_line=from_line,
                to_line=to_line
            )

            if code:
                return code

            # Fallback: try GitHub
            repo = self.github.extract_repo_from_component(finding.component)
            if repo:
                full_file = await self.github.get_file_contents(
                    repo=repo,
                    path=finding.file_path,
                    ref="main"
                )

                if full_file:
                    lines = full_file.splitlines()
                    context_lines_list = lines[from_line-1:to_line]
                    return "\n".join(context_lines_list)

            return None

        except Exception as e:
            logger.error(f"Error fetching code context: {e}")
            return None

    async def _get_full_file(self, finding: SonarQubeFinding) -> Optional[str]:
        """Get full file content from GitHub."""
        try:
            repo = self.github.extract_repo_from_component(finding.component)
            if not repo:
                logger.warning(f"Could not determine repository for {finding.component}")
                return None

            return await self.github.get_file_contents(
                repo=repo,
                path=finding.file_path,
                ref="main"
            )
        except Exception as e:
            logger.error(f"Error fetching full file: {e}")
            return None

    async def _handle_false_positive(
        self,
        finding: SonarQubeFinding,
        analysis: FalsePositiveAnalysis
    ) -> None:
        """Handle a false positive finding."""

        # Generate and post comment
        if self._check_rate_limit("comment"):
            comment = self.fp_detector.generate_comment(analysis, finding)
            await self.sonarqube.add_comment(finding.key, comment)
            self.comments_posted_this_hour += 1

        # Mark as won't fix if configured and high confidence
        auto_mark = self.fp_config.get("auto_mark", True)
        require_review_below = self.fp_config.get("require_review_below", 0.70)

        if auto_mark and analysis.confidence > require_review_below:
            await self.sonarqube.transition_issue(
                issue_key=finding.key,
                transition="wontfix",
                comment="Marked as false positive by automated analysis"
            )
            logger.info(f"[{finding.key}] Marked as won't fix")
        elif analysis.confidence <= require_review_below:
            # Low confidence - assign for human review
            logger.info(f"[{finding.key}] Low confidence - assigning for review")
            # Could assign to a team here if configured

    async def _create_fix_pr(
        self,
        finding: SonarQubeFinding,
        fix_result: FixResult,
        risk_assessment: RiskAssessment
    ) -> Optional[PullRequest]:
        """Create a pull request with the fix."""

        if not self._check_rate_limit("pr"):
            logger.warning("PR rate limit reached, skipping PR creation")
            return None

        try:
            repo = self.github.extract_repo_from_component(finding.component)
            if not repo:
                logger.error("Could not determine repository")
                return None

            # Create branch name
            branch_name = f"sonarqube-fix/{finding.rule_key.replace(':', '-')}-{finding.key[:8]}"

            # Create branch
            logger.info(f"[{finding.key}] Creating branch: {branch_name}")
            await self.github.create_branch(
                repo=repo,
                branch_name=branch_name,
                from_branch="main"
            )

            # Commit fix
            commit_message = f"fix: resolve {finding.rule_name} in {finding.file_path}"

            logger.info(f"[{finding.key}] Committing fix...")
            await self.github.create_or_update_file(
                repo=repo,
                branch=branch_name,
                path=finding.file_path,
                content=fix_result.fixed_code,
                message=commit_message
            )

            # Generate PR
            pr_title = PRTemplateGenerator.generate_pr_title(finding)
            pr_body = PRTemplateGenerator.generate_pr_body(
                finding=finding,
                fix_result=fix_result,
                risk_assessment=risk_assessment
            )
            pr_labels = PRTemplateGenerator.get_pr_labels(finding, risk_assessment)

            logger.info(f"[{finding.key}] Creating pull request...")
            pr = await self.github.create_pull_request(
                repo=repo,
                title=pr_title,
                body=pr_body,
                head=branch_name,
                base="main",
                labels=pr_labels
            )

            if pr:
                self.prs_created_this_hour += 1

                # Request Copilot review if configured
                if self.fix_config.get("request_copilot_review", True):
                    await self.github.request_copilot_review(repo, pr.number)

                # Link PR in SonarQube
                if self._check_rate_limit("comment"):
                    pr_comment = f"🤖 Automated fix PR created: {pr.html_url}"
                    await self.sonarqube.add_comment(finding.key, pr_comment)
                    self.comments_posted_this_hour += 1

                logger.info(f"[{finding.key}] PR created: {pr.html_url}")
                return pr

        except Exception as e:
            logger.error(f"Error creating PR: {e}", exc_info=True)
            return None

    async def _escalate_to_human(
        self,
        finding: SonarQubeFinding,
        risk_assessment: RiskAssessment,
        reason: str
    ) -> None:
        """Escalate issue to human review."""

        comment = f"""⚠️ **Escalated for Human Review**

**Reason:** {reason}

**Priority:** {risk_assessment.priority} (Risk Score: {risk_assessment.risk_score:.1f}/10)

This issue requires manual attention.
"""

        if self._check_rate_limit("comment"):
            await self.sonarqube.add_comment(finding.key, comment)
            self.comments_posted_this_hour += 1

        logger.info(f"[{finding.key}] Escalated: {reason}")

    def _check_rate_limit(self, operation: str) -> bool:
        """Check if operation is within rate limits."""
        self._reset_rate_limits_if_needed()

        if operation == "pr":
            max_prs = self.rate_limit_config.get("max_prs_per_hour", 5)
            return self.prs_created_this_hour < max_prs
        elif operation == "comment":
            max_comments = self.rate_limit_config.get("max_comments_per_hour", 20)
            return self.comments_posted_this_hour < max_comments

        return True

    def _reset_rate_limits_if_needed(self) -> None:
        """Reset rate limit counters if hour has elapsed."""
        if datetime.now() >= self.rate_limit_reset_time:
            self.prs_created_this_hour = 0
            self.comments_posted_this_hour = 0
            self.rate_limit_reset_time = datetime.now() + timedelta(hours=1)

    def _log_statistics(self) -> None:
        """Log current statistics."""
        logger.info("=" * 60)
        logger.info("Agent Statistics:")
        logger.info(f"  Findings Analyzed: {self.stats['findings_analyzed']}")
        logger.info(f"  False Positives: {self.stats['false_positives_detected']}")
        logger.info(f"  Fixes Generated: {self.stats['fixes_generated']}")
        logger.info(f"  PRs Created: {self.stats['prs_created']}")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info("=" * 60)
