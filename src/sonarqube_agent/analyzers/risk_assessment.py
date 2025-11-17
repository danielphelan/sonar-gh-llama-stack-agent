"""
Risk Assessment Module

Prioritizes security findings by exploitability, business impact, and exposure.
Calculates risk scores to determine which issues should be fixed first.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)


@dataclass
class RiskAssessment:
    """Result of risk assessment analysis."""

    risk_score: float
    priority: str  # P0, P1, P2, P3
    exploitability: int  # 1-10
    impact: int  # 1-10
    exposure: int  # 1-10
    confidence: float  # 0.0-1.0
    justification: str
    business_context: str
    recommended_sla: str  # e.g., "24 hours", "1 week"


class RiskAssessor:
    """Assesses risk level of security findings."""

    # Rule categories and their base exploitability scores
    RULE_EXPLOITABILITY = {
        # Critical - Remote code execution, SQL injection
        'sql_injection': 10,
        'code_injection': 10,
        'command_injection': 10,
        'deserialization': 9,

        # High - Authentication/Authorization
        'auth_bypass': 9,
        'privilege_escalation': 8,
        'session_fixation': 8,

        # Medium-High - Data exposure
        'xss': 7,
        'path_traversal': 7,
        'xxe': 8,
        'ssrf': 7,

        # Medium - Crypto and secrets
        'weak_crypto': 6,
        'hardcoded_secret': 6,
        'insecure_random': 5,

        # Low-Medium - Logic and validation
        'null_pointer': 3,
        'resource_leak': 4,
        'race_condition': 5,
    }

    # File path patterns indicating business impact
    HIGH_IMPACT_PATHS = [
        r'payment',
        r'auth',
        r'login',
        r'user',
        r'account',
        r'billing',
        r'order',
        r'transaction',
        r'admin',
        r'security',
    ]

    MEDIUM_IMPACT_PATHS = [
        r'api',
        r'service',
        r'controller',
        r'handler',
    ]

    LOW_IMPACT_PATHS = [
        r'test',
        r'mock',
        r'util',
        r'helper',
        r'config',
    ]

    def __init__(self, llm_client: Any, model: str = "codellama:13b"):
        """
        Initialize risk assessor.

        Args:
            llm_client: LLM client for code analysis
            model: Model to use for contextual analysis
        """
        self.llm_client = llm_client
        self.model = model

    async def assess(
        self,
        finding: Any,
        code_context: str,
        rule_details: Optional[Dict[str, Any]] = None
    ) -> RiskAssessment:
        """
        Assess the risk level of a finding.

        Args:
            finding: SonarQubeFinding object
            code_context: Code context around the issue
            rule_details: Optional rule details from SonarQube

        Returns:
            RiskAssessment result
        """
        try:
            # Calculate exploitability
            exploitability = self._calculate_exploitability(finding, rule_details)

            # Calculate business impact
            impact = self._calculate_impact(finding, code_context)

            # Calculate exposure
            exposure = self._calculate_exposure(finding, code_context)

            # Use LLM for contextual analysis
            contextual_analysis = await self._get_contextual_analysis(
                finding, code_context, exploitability, impact, exposure
            )

            # Calculate final risk score
            confidence = contextual_analysis.get("confidence", 0.8)
            risk_score = (exploitability * impact * exposure) / 100.0 * confidence

            # Determine priority
            priority = self._calculate_priority(risk_score)

            # Determine SLA
            sla = self._calculate_sla(priority)

            return RiskAssessment(
                risk_score=risk_score,
                priority=priority,
                exploitability=exploitability,
                impact=impact,
                exposure=exposure,
                confidence=confidence,
                justification=contextual_analysis.get("justification", ""),
                business_context=contextual_analysis.get("business_context", ""),
                recommended_sla=sla
            )

        except Exception as e:
            logger.error(f"Error in risk assessment: {e}")
            # Return conservative high-risk assessment on error
            return RiskAssessment(
                risk_score=7.0,
                priority="P1",
                exploitability=7,
                impact=7,
                exposure=7,
                confidence=0.5,
                justification=f"Assessment error: {str(e)}",
                business_context="Unknown",
                recommended_sla="1 week"
            )

    def _calculate_exploitability(
        self,
        finding: Any,
        rule_details: Optional[Dict[str, Any]]
    ) -> int:
        """Calculate exploitability score (1-10)."""

        # Map rule key to category
        rule_key = finding.rule_key.lower()

        for category, score in self.RULE_EXPLOITABILITY.items():
            if category.replace('_', '') in rule_key.replace(':', '').replace('-', ''):
                return score

        # Check rule type from SonarQube
        if rule_details:
            rule_type = rule_details.get("type", "").lower()
            if "vulnerability" in rule_type:
                return 7
            elif "security" in rule_type:
                return 6
            elif "bug" in rule_type:
                return 4

        # Default based on severity
        severity_map = {
            "CRITICAL": 8,
            "HIGH": 6,
            "MEDIUM": 4,
            "LOW": 2,
        }
        return severity_map.get(finding.severity, 5)

    def _calculate_impact(self, finding: Any, code_context: str) -> int:
        """Calculate business impact score (1-10)."""

        file_path = finding.file_path.lower()
        score = 5  # Default medium impact

        # Check high-impact patterns
        for pattern in self.HIGH_IMPACT_PATHS:
            if re.search(pattern, file_path):
                score = 9
                break

        # Check medium-impact patterns
        if score == 5:
            for pattern in self.MEDIUM_IMPACT_PATHS:
                if re.search(pattern, file_path):
                    score = 6
                    break

        # Check low-impact patterns
        for pattern in self.LOW_IMPACT_PATHS:
            if re.search(pattern, file_path):
                score = min(score, 3)
                break

        # Check for sensitive operations in code
        sensitive_keywords = {
            'password': 9,
            'credit_card': 10,
            'ssn': 10,
            'encrypt': 8,
            'decrypt': 8,
            'token': 7,
            'session': 7,
            'database': 7,
            'sql': 7,
        }

        code_lower = code_context.lower()
        for keyword, keyword_score in sensitive_keywords.items():
            if keyword in code_lower:
                score = max(score, keyword_score)

        return min(score, 10)

    def _calculate_exposure(self, finding: Any, code_context: str) -> int:
        """Calculate exposure score (1-10)."""

        score = 5  # Default medium exposure

        # Check if it's a public API endpoint
        api_indicators = [
            '@RestController',
            '@GetMapping',
            '@PostMapping',
            '@RequestMapping',
            '@Path',  # JAX-RS
            'app.route',  # Flask
            '@app.get',  # FastAPI
            'router.get',  # Express
        ]

        for indicator in api_indicators:
            if indicator in code_context:
                score = 9
                break

        # Check if it's internal/protected
        if 'private ' in code_context or 'internal ' in code_context:
            score = min(score, 5)

        # Check if it's test code
        if 'test' in finding.file_path.lower():
            score = 1

        # Check for authentication/authorization guards
        auth_patterns = [
            '@PreAuthorize',
            '@Secured',
            '@RolesAllowed',
            'require_login',
            'login_required',
            '@login_required',
        ]

        for pattern in auth_patterns:
            if pattern in code_context:
                score = max(1, score - 3)  # Reduces exposure
                break

        return min(score, 10)

    async def _get_contextual_analysis(
        self,
        finding: Any,
        code_context: str,
        exploitability: int,
        impact: int,
        exposure: int
    ) -> Dict[str, Any]:
        """Use LLM to provide contextual analysis of the risk."""

        prompt = f"""Analyze the business context and risk of this security finding.

**Finding:**
- Rule: {finding.rule_key}
- Severity: {finding.severity}
- Message: {finding.message}
- File: {finding.file_path}:{finding.line}

**Calculated Scores:**
- Exploitability: {exploitability}/10
- Impact: {impact}/10
- Exposure: {exposure}/10

**Code Context:**
```
{code_context[:1000]}
```

Provide a brief analysis in JSON format:
{{
    "justification": "1-2 sentence explanation of the risk",
    "business_context": "What business function this code serves",
    "confidence": 0.0-1.0
}}

Respond with ONLY valid JSON.
"""

        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                model=self.model,
                temperature=0.1
            )

            # Parse JSON from response
            import json
            response = response.strip()
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                return json.loads(response)

        except Exception as e:
            logger.error(f"Error in contextual analysis: {e}")
            return {
                "justification": "Automated risk assessment based on rule severity and code location",
                "business_context": "Unknown",
                "confidence": 0.7
            }

    def _calculate_priority(self, risk_score: float) -> str:
        """Calculate priority level from risk score."""
        if risk_score >= 8.0:
            return "P0"
        elif risk_score >= 6.0:
            return "P1"
        elif risk_score >= 4.0:
            return "P2"
        else:
            return "P3"

    def _calculate_sla(self, priority: str) -> str:
        """Calculate recommended SLA from priority."""
        sla_map = {
            "P0": "24 hours",
            "P1": "1 week",
            "P2": "2 weeks",
            "P3": "1 month"
        }
        return sla_map.get(priority, "2 weeks")

    def generate_comment(self, assessment: RiskAssessment, finding: Any) -> str:
        """Generate markdown comment for SonarQube."""

        comment = f"""📊 **Risk Assessment**

**Priority:** {assessment.priority} | **Risk Score:** {assessment.risk_score:.1f}/10
**Recommended SLA:** {assessment.recommended_sla}

**Risk Breakdown:**
- Exploitability: {assessment.exploitability}/10
- Business Impact: {assessment.impact}/10
- Exposure: {assessment.exposure}/10
- Confidence: {assessment.confidence:.0%}

**Analysis:**
{assessment.justification}

**Business Context:** {assessment.business_context}

---
*Analyzed by SonarQube Analysis Agent v1.0*
"""

        return comment
