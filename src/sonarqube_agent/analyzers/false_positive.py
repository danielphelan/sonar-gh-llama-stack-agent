"""
False Positive Detection Module

Analyzes code context to determine if a SonarQube finding is a false positive
by examining language guarantees, framework validations, and contextual guards.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FalsePositiveAnalysis:
    """Result of false positive analysis."""

    is_false_positive: bool
    confidence: float
    reasoning: str
    evidence: List[str]
    recommendation: str


class FalsePositiveDetector:
    """Detects false positives in SonarQube findings."""

    def __init__(self, llm_client: Any, model: str = "codellama:13b"):
        """
        Initialize false positive detector.

        Args:
            llm_client: LLM client for code analysis
            model: Model to use for analysis
        """
        self.llm_client = llm_client
        self.model = model

    async def analyze(
        self,
        finding: Any,
        code_context: str,
        rule_details: Optional[Dict[str, Any]] = None
    ) -> FalsePositiveAnalysis:
        """
        Analyze whether a finding is a false positive.

        Args:
            finding: SonarQubeFinding object
            code_context: Full code context around the issue
            rule_details: Optional rule details from SonarQube

        Returns:
            FalsePositiveAnalysis result
        """
        try:
            # Detect language and framework
            language = self._detect_language(finding.file_path)
            framework = self._detect_framework(code_context, language)

            # Build analysis prompt
            prompt = self._build_analysis_prompt(
                finding=finding,
                code_context=code_context,
                language=language,
                framework=framework,
                rule_details=rule_details
            )

            # Call LLM for analysis
            response = await self.llm_client.generate(
                prompt=prompt,
                model=self.model,
                temperature=0.1  # Low temperature for consistent analysis
            )

            # Parse response
            analysis = self._parse_response(response)

            logger.info(
                f"False positive analysis for {finding.key}: "
                f"{analysis.is_false_positive} (confidence: {analysis.confidence})"
            )

            return analysis

        except Exception as e:
            logger.error(f"Error in false positive analysis: {e}")
            # Return conservative result on error
            return FalsePositiveAnalysis(
                is_false_positive=False,
                confidence=0.0,
                reasoning=f"Analysis error: {str(e)}",
                evidence=[],
                recommendation="Manual review required due to analysis error"
            )

    def _build_analysis_prompt(
        self,
        finding: Any,
        code_context: str,
        language: str,
        framework: Optional[str],
        rule_details: Optional[Dict[str, Any]]
    ) -> str:
        """Build the analysis prompt for the LLM."""

        rule_description = ""
        if rule_details:
            rule_description = f"\n**Rule Description:**\n{rule_details.get('htmlDesc', '')}\n"

        framework_info = f"\nFramework: {framework}" if framework else ""

        prompt = f"""Analyze this SonarQube finding to determine if it's a FALSE POSITIVE.

**Finding Details:**
- Rule: {finding.rule_key} - {finding.rule_name}
- Severity: {finding.severity}
- Message: {finding.message}
- File: {finding.file_path}:{finding.line}
- Language: {language}{framework_info}
{rule_description}

**Code Context:**
```{language}
{code_context}
```

**Analysis Instructions:**
Determine if this is a false positive by considering:

1. **Language-level guarantees:**
   - Null safety features (Kotlin `?.`, TypeScript strict mode, etc.)
   - Type system protections (sealed classes, discriminated unions)
   - Compile-time guarantees

2. **Framework-level validations:**
   - Spring annotations (@NotNull, @Valid, @Validated)
   - Jakarta Bean Validation (@NotNull, @NotEmpty)
   - ORM validations (Hibernate, JPA)

3. **Contextual guards:**
   - Explicit null checks in surrounding code
   - Early return statements
   - Exception handling that prevents the issue

4. **Test vs Production context:**
   - Different rules apply in test code
   - Mock objects and test fixtures

**Response Format (JSON only):**
{{
    "is_false_positive": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "detailed explanation of why this is or isn't a false positive",
    "evidence": ["specific code line or pattern 1", "specific code line or pattern 2"],
    "recommendation": "what action should be taken (mark as won't fix, adjust rule, fix the issue)"
}}

Respond with ONLY valid JSON, no additional text.
"""

        return prompt

    def _parse_response(self, response: str) -> FalsePositiveAnalysis:
        """Parse LLM response into FalsePositiveAnalysis object."""
        try:
            # Extract JSON from response
            response = response.strip()

            # Try to find JSON in the response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                data = json.loads(json_str)
            else:
                data = json.loads(response)

            return FalsePositiveAnalysis(
                is_false_positive=data.get("is_false_positive", False),
                confidence=float(data.get("confidence", 0.0)),
                reasoning=data.get("reasoning", ""),
                evidence=data.get("evidence", []),
                recommendation=data.get("recommendation", "")
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}\nResponse: {response}")
            # Return conservative result
            return FalsePositiveAnalysis(
                is_false_positive=False,
                confidence=0.0,
                reasoning="Failed to parse analysis result",
                evidence=[],
                recommendation="Manual review required"
            )

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        extension_map = {
            '.java': 'java',
            '.kt': 'kotlin',
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.rb': 'ruby',
            '.php': 'php',
        }

        for ext, lang in extension_map.items():
            if file_path.endswith(ext):
                return lang

        return 'unknown'

    def _detect_framework(self, code_context: str, language: str) -> Optional[str]:
        """Detect framework from code context."""

        # Framework detection patterns
        framework_patterns = {
            'java': {
                'Spring': ['@SpringBootApplication', '@RestController', '@Service', '@Autowired'],
                'Jakarta EE': ['@ApplicationScoped', '@Inject', '@Path'],
                'Hibernate': ['@Entity', '@Table', '@Column'],
            },
            'python': {
                'Django': ['from django', 'models.Model', '@login_required'],
                'Flask': ['from flask import', '@app.route', 'Flask(__name__)'],
                'FastAPI': ['from fastapi import', '@app.get', 'FastAPI()'],
            },
            'javascript': {
                'React': ['import React', 'useState', 'useEffect'],
                'Vue': ['Vue.component', 'new Vue', 'export default {'],
                'Express': ['express()', 'app.get', 'app.post'],
            },
            'typescript': {
                'Angular': ['@Component', '@Injectable', '@NgModule'],
                'NestJS': ['@Controller', '@Injectable', '@Module'],
            }
        }

        if language in framework_patterns:
            for framework, patterns in framework_patterns[language].items():
                for pattern in patterns:
                    if pattern in code_context:
                        return framework

        return None

    def generate_comment(self, analysis: FalsePositiveAnalysis, finding: Any) -> str:
        """
        Generate a markdown comment for SonarQube explaining the false positive.

        Args:
            analysis: False positive analysis result
            finding: SonarQubeFinding object

        Returns:
            Markdown formatted comment
        """
        if not analysis.is_false_positive:
            return ""

        evidence_section = "\n".join([f"   - {ev}" for ev in analysis.evidence])

        comment = f"""🤖 **Automated Analysis: FALSE POSITIVE**

**Confidence:** {analysis.confidence:.0%}

**Reasoning:**
{analysis.reasoning}

**Evidence:**
{evidence_section}

**Recommendation:** {analysis.recommendation}

---
*Analyzed by SonarQube Analysis Agent v1.0*
*Analysis Date: {self._get_timestamp()}*
"""

        return comment

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
