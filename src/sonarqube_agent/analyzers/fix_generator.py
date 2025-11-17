"""
Fix Generation Module

Automatically generates code fixes for common security and quality patterns.
Validates fixes before proposing them to ensure they're safe and functional.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import difflib

logger = logging.getLogger(__name__)


@dataclass
class FixResult:
    """Result of fix generation."""

    fixed_code: str
    diff: str
    explanation: str
    test_suggestions: List[str]
    validation: 'FixValidation'
    confidence: float


@dataclass
class FixValidation:
    """Validation result for a generated fix."""

    is_safe: bool
    checks_passed: List[str]
    checks_failed: List[str]
    warnings: List[str]


class FixGenerator:
    """Generates automated fixes for security and quality issues."""

    # Patterns that can be auto-fixed
    FIXABLE_PATTERNS = {
        'null_pointer': ['S2259', 'S2637', 'NP_'],
        'resource_leak': ['S2095', 'OBL_'],
        'sql_injection': ['S3649', 'S2077', 'SQL_'],
        'hardcoded_credentials': ['S2068', 'S6290'],
        'insecure_random': ['S2245', 'S2119'],
        'path_traversal': ['S2083', 'PATH_'],
        'weak_crypto': ['S4426', 'S5542'],
    }

    def __init__(self, llm_client: Any, model: str = "deepseek-coder-v2:33b"):
        """
        Initialize fix generator.

        Args:
            llm_client: LLM client for code generation
            model: Model to use (default: deepseek-coder-v2 for best code understanding)
        """
        self.llm_client = llm_client
        self.model = model

    async def generate_fix(
        self,
        finding: Any,
        code_context: str,
        full_file_content: str,
        rule_details: Optional[Dict[str, Any]] = None
    ) -> Optional[FixResult]:
        """
        Generate a fix for a security/quality finding.

        Args:
            finding: SonarQubeFinding object
            code_context: Code context around the issue (±20 lines)
            full_file_content: Complete file content
            rule_details: Optional rule details from SonarQube

        Returns:
            FixResult if fix can be generated, None otherwise
        """
        try:
            # Check if this pattern is fixable
            pattern = self._identify_pattern(finding.rule_key)
            if not pattern:
                logger.info(f"Rule {finding.rule_key} is not in fixable patterns")
                return None

            logger.info(f"Generating fix for pattern: {pattern}")

            # Detect language
            language = self._detect_language(finding.file_path)

            # Build fix generation prompt
            prompt = self._build_fix_prompt(
                finding=finding,
                code_context=code_context,
                full_file=full_file_content,
                pattern=pattern,
                language=language,
                rule_details=rule_details
            )

            # Generate fix using LLM
            response = await self.llm_client.generate(
                prompt=prompt,
                model=self.model,
                temperature=0.1  # Low temperature for consistent code generation
            )

            # Parse the response
            fix_data = self._parse_fix_response(response)

            if not fix_data:
                logger.warning("Failed to parse fix response")
                return None

            # Create diff
            diff = self._create_diff(code_context, fix_data['fixed_code'])

            # Validate the fix
            validation = self._validate_fix(
                original=code_context,
                fixed=fix_data['fixed_code'],
                finding=finding,
                language=language
            )

            # Create result
            result = FixResult(
                fixed_code=fix_data['fixed_code'],
                diff=diff,
                explanation=fix_data.get('explanation', ''),
                test_suggestions=fix_data.get('test_suggestions', []),
                validation=validation,
                confidence=fix_data.get('confidence', 0.8)
            )

            logger.info(
                f"Fix generated for {finding.key}. "
                f"Safe: {validation.is_safe}, Confidence: {result.confidence}"
            )

            return result

        except Exception as e:
            logger.error(f"Error generating fix: {e}")
            return None

    def _identify_pattern(self, rule_key: str) -> Optional[str]:
        """Identify the fix pattern from rule key."""
        rule_key_upper = rule_key.upper()

        for pattern, rule_indicators in self.FIXABLE_PATTERNS.items():
            for indicator in rule_indicators:
                if indicator.upper() in rule_key_upper:
                    return pattern

        return None

    def _build_fix_prompt(
        self,
        finding: Any,
        code_context: str,
        full_file: str,
        pattern: str,
        language: str,
        rule_details: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for fix generation."""

        rule_description = ""
        if rule_details:
            rule_description = f"\n**Rule Description:**\n{rule_details.get('htmlDesc', '')[:500]}\n"

        pattern_guidance = self._get_pattern_guidance(pattern, language)

        prompt = f"""Generate a MINIMAL, TARGETED fix for this {pattern} issue in {language}.

**Finding:**
- Rule: {finding.rule_key}
- Message: {finding.message}
- File: {finding.file_path}:{finding.line}
{rule_description}

**Current Code (with context):**
```{language}
{code_context}
```

**Pattern-Specific Guidance:**
{pattern_guidance}

**Fix Requirements:**
1. Make MINIMAL changes - only fix the specific issue
2. Preserve all existing functionality
3. Follow {language} idioms and best practices
4. Add brief comments explaining the fix
5. Handle edge cases appropriately
6. Do NOT change unrelated code
7. Ensure the fix is production-ready

**Response Format (JSON only):**
{{
    "fixed_code": "the complete fixed code section (same scope as input)",
    "explanation": "brief explanation of what was changed and why",
    "test_suggestions": ["test case 1", "test case 2", "test case 3"],
    "confidence": 0.0-1.0
}}

Respond with ONLY valid JSON containing the fixed code.
"""

        return prompt

    def _get_pattern_guidance(self, pattern: str, language: str) -> str:
        """Get pattern-specific guidance for fix generation."""

        guidance = {
            'null_pointer': {
                'java': """
- Add null checks before dereferencing
- Use Optional<T> where appropriate
- Consider Objects.requireNonNull() for parameters
- Add @Nullable/@NotNull annotations if applicable
                """,
                'python': """
- Add 'if x is not None:' checks
- Use Optional type hints
- Consider default values with 'or'
                """,
                'javascript': """
- Use optional chaining (?.)
- Add null/undefined checks
- Use nullish coalescing (??)
                """
            },
            'resource_leak': {
                'java': """
- Use try-with-resources for AutoCloseable resources
- Ensure close() is called in finally block
- Consider using try-with-resources with multiple resources
                """,
                'python': """
- Use 'with' statement for context managers
- Ensure resources are properly closed
                """
            },
            'sql_injection': {
                'java': """
- Replace string concatenation with PreparedStatement
- Use parameterized queries with ? placeholders
- NEVER concatenate user input into SQL strings
                """,
                'python': """
- Use parameterized queries with %s or named parameters
- Use ORM query builders when possible
- NEVER use string formatting (f-strings, %) for SQL
                """
            },
            'hardcoded_credentials': {
                'java': """
- Move credentials to environment variables
- Use System.getenv() or properties files
- Consider Spring @Value annotation
                """,
                'python': """
- Use os.getenv() for environment variables
- Use python-dotenv for .env files
- Never commit actual secrets
                """
            },
            'insecure_random': {
                'java': """
- Replace Random with SecureRandom
- Use java.security.SecureRandom for security-sensitive operations
                """,
                'python': """
- Replace random with secrets module
- Use secrets.token_bytes() or secrets.token_hex()
                """
            }
        }

        pattern_guidance = guidance.get(pattern, {})
        lang_guidance = pattern_guidance.get(language, "")

        if not lang_guidance:
            # Generic guidance
            lang_guidance = f"Fix the {pattern} issue following {language} best practices"

        return lang_guidance

    def _parse_fix_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response into fix data."""
        try:
            response = response.strip()

            # Extract JSON
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                return json.loads(response)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse fix response: {e}\nResponse: {response[:500]}")
            return None

    def _create_diff(self, original: str, fixed: str) -> str:
        """Create a unified diff between original and fixed code."""
        original_lines = original.splitlines(keepends=True)
        fixed_lines = fixed.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            fixed_lines,
            fromfile='original',
            tofile='fixed',
            lineterm=''
        )

        return ''.join(diff)

    def _validate_fix(
        self,
        original: str,
        fixed: str,
        finding: Any,
        language: str
    ) -> FixValidation:
        """Validate that the fix is safe and appropriate."""

        checks_passed = []
        checks_failed = []
        warnings = []

        # Check 1: Code length shouldn't change drastically
        original_lines = len(original.splitlines())
        fixed_lines = len(fixed.splitlines())

        if abs(fixed_lines - original_lines) > original_lines * 0.5:
            warnings.append(
                f"Significant size change: {original_lines} -> {fixed_lines} lines"
            )
        else:
            checks_passed.append("Code size change is reasonable")

        # Check 2: Should not remove error handling
        error_handling_keywords = ['try', 'catch', 'except', 'finally', 'throw', 'raise']
        original_error_handling = sum(1 for kw in error_handling_keywords if kw in original.lower())
        fixed_error_handling = sum(1 for kw in error_handling_keywords if kw in fixed.lower())

        if fixed_error_handling < original_error_handling:
            warnings.append("Error handling may have been removed")
        else:
            checks_passed.append("Error handling preserved")

        # Check 3: Should not remove important logic
        # Check for function calls, variable assignments
        import re

        original_assignments = len(re.findall(r'\w+\s*=', original))
        fixed_assignments = len(re.findall(r'\w+\s*=', fixed))

        if fixed_assignments < original_assignments * 0.8:
            warnings.append("Significant logic may have been removed")
        else:
            checks_passed.append("Logic structure preserved")

        # Check 4: Basic syntax validation
        if self._has_obvious_syntax_errors(fixed, language):
            checks_failed.append("Potential syntax errors detected")
        else:
            checks_passed.append("No obvious syntax errors")

        # Check 5: Fix should actually change something
        if original.strip() == fixed.strip():
            checks_failed.append("No changes were made")
        else:
            checks_passed.append("Code was modified")

        # Determine if safe
        is_safe = len(checks_failed) == 0 and len(warnings) < 2

        return FixValidation(
            is_safe=is_safe,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            warnings=warnings
        )

    def _has_obvious_syntax_errors(self, code: str, language: str) -> bool:
        """Check for obvious syntax errors."""

        # Check for unmatched braces/brackets
        if language in ['java', 'javascript', 'typescript', 'c', 'cpp', 'csharp', 'go']:
            if code.count('{') != code.count('}'):
                return True
            if code.count('(') != code.count(')'):
                return True

        if code.count('[') != code.count(']'):
            return True

        # Check for incomplete strings
        # Count unescaped quotes
        import re
        double_quotes = len(re.findall(r'(?<!\\)"', code))
        single_quotes = len(re.findall(r"(?<!\\)'", code))

        if double_quotes % 2 != 0 or single_quotes % 2 != 0:
            return True

        return False

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
        }

        for ext, lang in extension_map.items():
            if file_path.endswith(ext):
                return lang

        return 'unknown'
