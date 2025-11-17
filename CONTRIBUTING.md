# Contributing to SonarQube Analysis Agent

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a branch** for your changes
4. **Make your changes** and test them
5. **Submit a pull request**

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/sonarqube-analysis-agent
cd sonarqube-analysis-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run linting
black src/
ruff check src/
mypy src/
```

## Code Standards

- **Python Style**: Follow PEP 8, enforced by `black` and `ruff`
- **Type Hints**: Use type hints for all function signatures
- **Documentation**: Add docstrings for all public functions and classes
- **Testing**: Write tests for new features

## Pull Request Process

1. **Update documentation** if you change functionality
2. **Add tests** for new features
3. **Ensure all tests pass**: `pytest tests/`
4. **Run linting**: `black . && ruff check . && mypy .`
5. **Update CHANGELOG.md** with your changes
6. **Submit PR** with clear description of changes

## Adding New Fix Patterns

To add support for a new fix pattern:

1. **Add pattern to `fix_generator.py`**:
   ```python
   FIXABLE_PATTERNS = {
       'your_pattern': ['RULE_KEY_1', 'RULE_KEY_2'],
   }
   ```

2. **Add pattern-specific guidance**:
   ```python
   def _get_pattern_guidance(self, pattern: str, language: str):
       guidance = {
           'your_pattern': {
               'java': "Specific guidance for Java",
               'python': "Specific guidance for Python"
           }
       }
   ```

3. **Add tests** in `tests/test_fix_generator.py`

4. **Update documentation** in README.md

## Reporting Bugs

When reporting bugs, please include:

- **Python version**
- **Docker version** (if applicable)
- **Agent version**
- **Error logs** (from `logs/agent.log`)
- **Steps to reproduce**
- **Expected vs actual behavior**

## Feature Requests

We welcome feature requests! Please:

- **Search existing issues** first
- **Describe the use case** clearly
- **Explain why** the feature would be valuable
- **Provide examples** if applicable

## Code Review

All submissions require review. We use GitHub pull requests for this purpose.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
