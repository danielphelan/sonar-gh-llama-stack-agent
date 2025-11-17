# 🤖 SonarQube Analysis Agent

An intelligent AI agent built on the **Llama Stack framework** that autonomously analyzes SonarQube security and quality findings, distinguishes false positives from genuine issues, prioritizes vulnerabilities by risk, and automatically generates pull requests with fixes.

## ✨ Features

- **🔍 Automated False Positive Detection**: Uses AI to analyze code context and identify false positives with high confidence
- **📊 Risk-Based Prioritization**: Scores findings by exploitability, business impact, and exposure (P0-P3)
- **🔧 Automatic Fix Generation**: Generates safe, minimal fixes for common patterns (null pointers, SQL injection, resource leaks, etc.)
- **🚀 Pull Request Creation**: Automatically creates PRs with detailed explanations and test suggestions
- **📝 SonarQube Integration**: Posts analysis comments and manages issue lifecycle
- **🤝 GitHub Copilot Integration**: Requests automated code review for generated fixes

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│              SonarQube Analysis Agent                    │
├─────────────────────────────────────────────────────────┤
│  Llama Stack Framework (Orchestration Layer)            │
│    ├── Agent Runtime                                     │
│    ├── Memory & Context Management                      │
│    └── Tool Integration Layer                           │
├─────────────────────────────────────────────────────────┤
│  LLM Provider: Ollama (Local Model Execution)           │
│    ├── Primary: deepseek-coder-v2 (33B)                │
│    ├── Secondary: codellama (13B)                       │
│    └── Fallback: llama3.1 (8B)                         │
├─────────────────────────────────────────────────────────┤
│  MCP Servers (Model Context Protocol)                   │
│    ├── SonarQube MCP Server                            │
│    └── GitHub MCP Server                               │
└─────────────────────────────────────────────────────────┘
```

## 📋 Prerequisites

### Required

- **Docker** and **Docker Compose** (for containerized deployment)
- **SonarQube** server (with API access)
- **GitHub** repository access (with PAT)
- **GPU** (NVIDIA) for optimal performance, or CPU (slower)

### Optional

- Python 3.10+ (for local development)
- Node.js 20+ (for MCP servers)

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourorg/sonarqube-analysis-agent
cd sonarqube-analysis-agent
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

**Required Configuration:**

```bash
# SonarQube
SONARQUBE_URL=https://sonarqube.company.com
SONARQUBE_TOKEN=squ_your_token_here
SONARQUBE_PROJECTS=project-key-1,project-key-2

# GitHub
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPOS=myorg/repo1,myorg/repo2
```

### 3. Start Services with Docker Compose

```bash
# Start Ollama and the agent
docker-compose -f docker/docker-compose.yml up -d

# Pull required Ollama models (first time only)
docker exec sonarqube-agent-ollama ollama pull deepseek-coder-v2:33b
docker exec sonarqube-agent-ollama ollama pull codellama:13b
docker exec sonarqube-agent-ollama ollama pull llama3.1:8b

# Verify models are downloaded
docker exec sonarqube-agent-ollama ollama list
```

### 4. Monitor Logs

```bash
# Follow agent logs
docker-compose -f docker/docker-compose.yml logs -f sonarqube-agent

# View Ollama logs
docker-compose -f docker/docker-compose.yml logs -f ollama
```

### 5. Stop Services

```bash
docker-compose -f docker/docker-compose.yml down
```

## 🛠️ Local Development Setup

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -e ".[dev]"
```

### 2. Run Locally

```bash
# Make sure Ollama is running (locally or via Docker)
# docker run -d -p 11434:11434 --name ollama ollama/ollama

# Update .env to point to local Ollama
export OLLAMA_HOST=http://localhost:11434

# Run the agent
python -m sonarqube_agent.main --log-level DEBUG

# Or run once (non-continuous mode)
python -m sonarqube_agent.main --once

# Dry run mode (no changes made)
python -m sonarqube_agent.main --dry-run
```

## ⚙️ Configuration

### Agent Behavior Configuration

Edit `config/agent-config.yaml`:

```yaml
behavior:
  false_positive:
    min_confidence: 0.85        # Confidence threshold for FP detection
    auto_mark: true             # Auto-mark as "won't fix"
    require_review_below: 0.70  # Human review if confidence < 70%

  fix_generation:
    min_confidence: 0.90        # Confidence threshold for fix PRs
    auto_create_pr: true        # Auto-create PRs
    supported_patterns:
      - "null_pointer"
      - "resource_leak"
      - "sql_injection"
      - "hardcoded_credentials"

  prioritization:
    auto_fix_priorities:        # Which priorities get auto-fixed
      - "P0"
      - "P1"

  rate_limiting:
    max_prs_per_hour: 5
    max_comments_per_hour: 20
    poll_interval_seconds: 300  # 5 minutes
```

### Model Selection Strategy

The agent automatically routes tasks to appropriate models:

| Task | Model | Size | Use Case |
|------|-------|------|----------|
| **Code Analysis & Fix Generation** | deepseek-coder-v2 | 33B | Deep code understanding |
| **False Positive Detection** | codellama | 13B | Fast pattern matching |
| **PR Descriptions & Comments** | llama3.1 | 8B | Text generation |

## 📊 Supported Fix Patterns

The agent can automatically fix these common patterns:

| Pattern | Languages | Example |
|---------|-----------|---------|
| **Null Pointer Dereference** | Java, Python, JavaScript | Add null checks, use Optional |
| **Resource Leaks** | Java, Python | try-with-resources, context managers |
| **SQL Injection** | Java, Python | Parameterized queries |
| **Hardcoded Credentials** | All | Environment variables |
| **Insecure Random** | Java, Python | SecureRandom, secrets module |
| **Path Traversal** | All | Input validation |
| **Weak Cryptography** | All | Strong algorithms |

## 🔐 Required Permissions

### SonarQube Token Scopes

- `Browse` - Read project issues
- `Administer Issues` - Change issue status, add comments
- `See Source Code` - Access code context

**Generate token at:** `https://your-sonarqube.com/account/security/`

### GitHub Token Scopes

- `repo` - Full repository access
- `pull_requests` - Create and manage PRs
- `contents:write` - Commit changes

**Generate token at:** `https://github.com/settings/tokens/new`

## 📈 Success Metrics

The agent tracks these metrics:

- **Findings Analyzed**: Total issues processed
- **False Positives Detected**: Issues correctly identified as FP
- **Fixes Generated**: Automated fixes created
- **PRs Created**: Pull requests submitted
- **Errors**: Analysis failures

View live statistics in logs:

```
==========================================
Agent Statistics:
  Findings Analyzed: 47
  False Positives: 28 (59%)
  Fixes Generated: 12
  PRs Created: 8
  Errors: 0
==========================================
```

## 🔄 Deployment Phases

### Phase 1: Read-Only Mode (Week 1-2)

Test analysis accuracy without making changes:

```yaml
# config/agent-config.yaml
behavior:
  false_positive:
    auto_mark: false  # Only comment, don't change status
  fix_generation:
    auto_create_pr: false  # Generate diffs but no PRs
```

### Phase 2: Supervised Mode (Week 3-4)

Create draft PRs requiring approval:

```bash
# Enable PR creation but keep manual approval
AUTO_CREATE_PR=true
# Review all PRs before merging
```

### Phase 3: Autonomous Mode (Week 5+)

Full automation with safety guardrails (current default configuration).

## 🐛 Troubleshooting

### Agent Not Detecting Findings

```bash
# Check SonarQube connection
curl -u $SONARQUBE_TOKEN: $SONARQUBE_URL/api/system/status

# Verify project keys
docker-compose logs sonarqube-agent | grep "projects"
```

### Ollama Models Not Working

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Re-pull models
docker exec sonarqube-agent-ollama ollama pull deepseek-coder-v2:33b

# Check GPU availability (optional)
docker exec sonarqube-agent-ollama nvidia-smi
```

### PRs Not Being Created

```bash
# Check GitHub token permissions
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

# Check rate limits
docker-compose logs sonarqube-agent | grep "rate limit"
```

### Memory Issues

```bash
# For large models, increase Docker memory limit
# Edit docker-compose.yml:
services:
  ollama:
    deploy:
      resources:
        limits:
          memory: 16G  # Increase as needed
```

## 📚 Documentation

- [Product Requirements Document](docs/PRD.md) - Full feature specifications
- [Architecture Guide](docs/ARCHITECTURE.md) - Technical deep dive
- [Development Guide](docs/DEVELOPMENT.md) - Contributing guidelines

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Llama Stack** - Agent orchestration framework
- **Ollama** - Local LLM execution
- **SonarQube** - Code quality and security analysis
- **MCP (Model Context Protocol)** - Tool integration standard

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourorg/sonarqube-agent/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourorg/sonarqube-agent/discussions)
- **Email**: security-team@yourcompany.com

---

**Made with ❤️ by the DevSecOps Team**
