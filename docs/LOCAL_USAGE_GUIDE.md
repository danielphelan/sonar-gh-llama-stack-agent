# Local Usage Guide - SonarQube Analysis Agent

This guide provides detailed, step-by-step instructions for running the SonarQube Analysis Agent on your local machine.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Option 1: Quick Start with Docker (Recommended)](#option-1-quick-start-with-docker-recommended)
- [Option 2: Local Python Development](#option-2-local-python-development)
- [Configuration Guide](#configuration-guide)
- [Running the Agent](#running-the-agent)
- [Verification and Monitoring](#verification-and-monitoring)
- [Troubleshooting](#troubleshooting)
- [Common Use Cases](#common-use-cases)

---

## Prerequisites

### Required Software

**For Docker Setup:**
- **Docker** (version 20.10+)
  - Download: https://docs.docker.com/get-docker/
  - Verify: `docker --version`
- **Docker Compose** (version 2.0+)
  - Usually included with Docker Desktop
  - Verify: `docker-compose --version`

**For Local Python Setup:**
- **Python 3.10+**
  - Download: https://www.python.org/downloads/
  - Verify: `python --version` or `python3 --version`
- **pip** (Python package manager)
  - Usually included with Python
  - Verify: `pip --version` or `pip3 --version`
- **Ollama** (for running LLM models locally)
  - Download: https://ollama.ai/download
  - Verify: `ollama --version`

### Required Access & Credentials

You will need:

1. **SonarQube Access**
   - SonarQube server URL (e.g., `https://sonarqube.company.com`)
   - SonarQube API token with permissions:
     - `Browse` - Read project issues
     - `Administer Issues` - Change issue status, add comments
     - `See Source Code` - Access code context
   - Generate at: `https://your-sonarqube.com/account/security/`
   - Project keys you want to monitor (e.g., `my-backend-service`)

2. **GitHub Access**
   - GitHub Personal Access Token (PAT) with scopes:
     - `repo` - Full repository access
     - `pull_requests` - Create and manage PRs
     - `contents:write` - Commit changes
   - Generate at: https://github.com/settings/tokens/new
   - Repository names in `owner/repo` format (e.g., `myorg/backend-service`)

### System Requirements

**Minimum:**
- 8 GB RAM
- 20 GB free disk space
- CPU: 4 cores

**Recommended (with GPU):**
- 16 GB RAM
- 50 GB free disk space
- NVIDIA GPU with 8+ GB VRAM
- CPU: 8+ cores

---

## Option 1: Quick Start with Docker (Recommended)

This is the easiest way to get started. Docker handles all dependencies and environment setup automatically.

### Step 1: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/yourorg/sonarqube-analysis-agent.git

# Navigate to the project directory
cd sonarqube-analysis-agent
```

### Step 2: Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file with your credentials
nano .env
# Or use your preferred editor: vim, code, etc.
```

**Edit these required fields in `.env`:**

```bash
# SonarQube Configuration
SONARQUBE_URL=https://sonarqube.company.com          # Your SonarQube URL
SONARQUBE_TOKEN=squ_your_actual_token_here           # Your SonarQube token
SONARQUBE_PROJECTS=project-key-1,project-key-2       # Comma-separated project keys

# GitHub Configuration
GITHUB_TOKEN=ghp_your_actual_token_here              # Your GitHub PAT
GITHUB_REPOS=myorg/repo1,myorg/repo2                 # Comma-separated repos

# Ollama Configuration (default is fine for Docker)
OLLAMA_HOST=http://ollama:11434
```

**Optional configuration (keep defaults to start):**

```bash
POLL_INTERVAL=300              # Check for new findings every 5 minutes
LOG_LEVEL=INFO                 # Logging verbosity: DEBUG, INFO, WARNING, ERROR
AUTO_CREATE_PR=true            # Automatically create pull requests
AUTO_MARK_FP=true              # Automatically mark false positives
DRY_RUN=false                  # Set to true to analyze without making changes
```

Save and close the file (Ctrl+X, then Y, then Enter in nano).

### Step 3: Run the Quick Setup Script

The easiest way to start:

```bash
# Make the setup script executable
chmod +x setup.sh

# Run the setup script
./setup.sh
```

This script will:
1. Check Docker installation
2. Create `.env` if it doesn't exist
3. Start Docker containers
4. Download required AI models (may take 10-30 minutes)
5. Start the agent

**Or manually start services:**

```bash
# Start all services (Ollama + Agent)
docker-compose -f docker/docker-compose.yml up -d

# Wait for Ollama to be ready (about 10 seconds)
sleep 10

# Download required AI models (first time only - this takes a while!)
docker exec sonarqube-agent-ollama ollama pull deepseek-coder-v2:33b
docker exec sonarqube-agent-ollama ollama pull codellama:13b
docker exec sonarqube-agent-ollama ollama pull llama3.1:8b
```

**Model download sizes:**
- `deepseek-coder-v2:33b` - ~19 GB (best for code analysis)
- `codellama:13b` - ~7 GB (fast triage)
- `llama3.1:8b` - ~4.7 GB (text generation)

### Step 4: Verify Everything is Running

```bash
# Check container status
docker-compose -f docker/docker-compose.yml ps

# You should see both containers running:
# - sonarqube-agent-ollama
# - sonarqube-agent

# Verify models are installed
docker exec sonarqube-agent-ollama ollama list

# Check agent logs
docker-compose -f docker/docker-compose.yml logs -f sonarqube-agent
```

Look for this in the logs:
```
Agent initialized successfully
Running agent in continuous mode...
```

Press `Ctrl+C` to stop viewing logs (the agent keeps running).

### Step 5: Managing the Agent

```bash
# View live logs
docker-compose -f docker/docker-compose.yml logs -f sonarqube-agent

# Restart the agent (after config changes)
docker-compose -f docker/docker-compose.yml restart sonarqube-agent

# Stop all services
docker-compose -f docker/docker-compose.yml down

# Start services again
docker-compose -f docker/docker-compose.yml up -d

# Remove everything (including downloaded models)
docker-compose -f docker/docker-compose.yml down -v
```

---

## Option 2: Local Python Development

This approach gives you more control and is better for development or when you don't want to use Docker.

### Step 1: Clone and Navigate

```bash
# Clone the repository
git clone https://github.com/yourorg/sonarqube-analysis-agent.git
cd sonarqube-analysis-agent
```

### Step 2: Set Up Python Environment

```bash
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
# On Linux/Mac:
source venv/bin/activate

# On Windows:
# venv\Scripts\activate

# Your prompt should now show (venv)
```

### Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install the agent and dependencies
pip install -r requirements.txt

# For development work, also install dev dependencies
pip install -e ".[dev]"
```

### Step 4: Install and Configure Ollama

**Install Ollama:**

```bash
# On Linux:
curl -fsSL https://ollama.ai/install.sh | sh

# On Mac:
brew install ollama

# On Windows:
# Download from https://ollama.ai/download
```

**Start Ollama:**

```bash
# Start Ollama server (in a separate terminal)
ollama serve

# Keep this terminal open!
```

**Download Models:**

In a new terminal (with venv activated):

```bash
# Download required models
ollama pull deepseek-coder-v2:33b
ollama pull codellama:13b
ollama pull llama3.1:8b

# Verify models are available
ollama list
```

### Step 5: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your credentials
nano .env
```

**Important: Update OLLAMA_HOST for local setup:**

```bash
# For local Ollama (not Docker)
OLLAMA_HOST=http://localhost:11434

# SonarQube Configuration
SONARQUBE_URL=https://sonarqube.company.com
SONARQUBE_TOKEN=squ_your_token_here
SONARQUBE_PROJECTS=project-key-1,project-key-2

# GitHub Configuration
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPOS=myorg/repo1,myorg/repo2
```

### Step 6: Run the Agent Locally

```bash
# Make sure venv is activated and Ollama is running!

# Run in continuous mode (polls every 5 minutes)
python -m sonarqube_agent.main

# Or run once (process current findings then exit)
python -m sonarqube_agent.main --once

# Run with debug logging
python -m sonarqube_agent.main --log-level DEBUG

# Run in dry-run mode (no changes made)
python -m sonarqube_agent.main --dry-run

# Combine options
python -m sonarqube_agent.main --once --log-level DEBUG --dry-run
```

---

## Configuration Guide

### Agent Configuration File

The main configuration is in `config/agent-config.yaml`. You can customize:

**False Positive Detection:**

```yaml
behavior:
  false_positive:
    min_confidence: 0.85           # Only mark as FP if 85%+ confident
    auto_mark: true                # Automatically mark as "won't fix"
    require_review_below: 0.70     # Assign to human if confidence < 70%
```

**Fix Generation:**

```yaml
  fix_generation:
    min_confidence: 0.90           # Only create PR if 90%+ confident
    auto_create_pr: true           # Automatically create PRs
    supported_patterns:            # Patterns the agent can fix
      - "null_pointer"
      - "resource_leak"
      - "sql_injection"
      - "hardcoded_credentials"
```

**Prioritization:**

```yaml
  prioritization:
    auto_fix_priorities:           # Automatically fix these priorities
      - "P0"
      - "P1"
```

**Rate Limiting (prevent overwhelming your systems):**

```yaml
  rate_limiting:
    max_prs_per_hour: 5            # Maximum 5 PRs per hour
    max_comments_per_hour: 20      # Maximum 20 comments per hour
    poll_interval_seconds: 300     # Check every 5 minutes
```

### Environment Variables Reference

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `SONARQUBE_URL` | SonarQube server URL | `https://sonar.company.com` | Yes |
| `SONARQUBE_TOKEN` | SonarQube API token | `squ_abc123...` | Yes |
| `SONARQUBE_PROJECTS` | Projects to monitor (comma-separated) | `project1,project2` | Yes |
| `GITHUB_TOKEN` | GitHub Personal Access Token | `ghp_abc123...` | Yes |
| `GITHUB_REPOS` | Repositories (comma-separated) | `org/repo1,org/repo2` | Yes |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` | Yes |
| `POLL_INTERVAL` | Seconds between checks | `300` | No |
| `LOG_LEVEL` | Logging verbosity | `INFO` | No |
| `AUTO_CREATE_PR` | Auto-create PRs | `true` or `false` | No |
| `AUTO_MARK_FP` | Auto-mark false positives | `true` or `false` | No |
| `DRY_RUN` | Analyze without changes | `true` or `false` | No |

---

## Running the Agent

### Command-Line Options

```bash
python -m sonarqube_agent.main [OPTIONS]
```

**Available Options:**

| Option | Description | Example |
|--------|-------------|---------|
| `--config PATH` | Path to config file | `--config /path/to/config.yaml` |
| `--log-level LEVEL` | Set logging level | `--log-level DEBUG` |
| `--log-file PATH` | Write logs to file | `--log-file /tmp/agent.log` |
| `--once` | Run once then exit | `--once` |
| `--created-after ISO_DATE` | Process findings after date | `--created-after 2024-01-01T00:00:00Z` |
| `--poll-interval SECONDS` | Override poll interval | `--poll-interval 600` |
| `--dry-run` | Analyze without making changes | `--dry-run` |

### Running Modes

**1. Continuous Mode (Default)**

Runs forever, checking for new findings every 5 minutes:

```bash
python -m sonarqube_agent.main
```

**2. One-Time Analysis**

Process current findings then exit:

```bash
python -m sonarqube_agent.main --once
```

**3. Dry Run (Safe Testing)**

Analyze and log what would be done, but don't make any changes:

```bash
python -m sonarqube_agent.main --dry-run
```

**4. Debug Mode**

Get detailed logs for troubleshooting:

```bash
python -m sonarqube_agent.main --log-level DEBUG
```

**5. Process Recent Findings Only**

Only process findings created after a specific date:

```bash
python -m sonarqube_agent.main --once --created-after 2024-01-01T00:00:00Z
```

---

## Verification and Monitoring

### Check if the Agent is Working

**1. Check SonarQube Connection:**

```bash
# Test SonarQube API access
curl -u ${SONARQUBE_TOKEN}: ${SONARQUBE_URL}/api/system/status
```

Expected output: `{"status":"UP",...}`

**2. Check Ollama:**

```bash
# For Docker:
curl http://localhost:11434/api/tags

# For local Ollama:
curl http://localhost:11434/api/tags
```

Expected output: JSON list of installed models

**3. Check GitHub Access:**

```bash
curl -H "Authorization: token ${GITHUB_TOKEN}" https://api.github.com/user
```

Expected output: Your GitHub user information

### Monitor Agent Activity

**View Logs (Docker):**

```bash
# Follow live logs
docker-compose -f docker/docker-compose.yml logs -f sonarqube-agent

# View last 100 lines
docker-compose -f docker/docker-compose.yml logs --tail=100 sonarqube-agent

# Save logs to file
docker-compose -f docker/docker-compose.yml logs sonarqube-agent > agent.log
```

**View Logs (Local):**

Logs are printed to stdout by default. To save to a file:

```bash
python -m sonarqube_agent.main --log-file /tmp/agent.log
```

**Look for Success Indicators:**

```
Agent initialized successfully
Running agent in continuous mode...
Processing 12 findings from SonarQube...
Analysis complete: 3 false positives, 2 fixes generated, 1 PR created
```

**Statistics Summary:**

The agent logs statistics periodically:

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

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: "Docker containers not starting"

**Symptoms:**
```
ERROR: Cannot connect to Docker daemon
```

**Solution:**
```bash
# Start Docker service
# On Linux:
sudo systemctl start docker

# On Mac/Windows:
# Start Docker Desktop application

# Verify Docker is running
docker ps
```

#### Issue: "Ollama models not downloading"

**Symptoms:**
```
Error: model not found
```

**Solution:**
```bash
# For Docker:
docker exec -it sonarqube-agent-ollama bash
ollama pull deepseek-coder-v2:33b
exit

# For local:
ollama pull deepseek-coder-v2:33b

# Check available space (models are large!)
df -h
```

#### Issue: "Out of memory / Container crashes"

**Symptoms:**
```
Killed
Container exited with code 137
```

**Solution:**

Increase Docker memory limit:

1. Open Docker Desktop Settings
2. Resources → Memory
3. Increase to at least 8 GB (16 GB recommended)
4. Apply & Restart

Or edit `docker-compose.yml`:

```yaml
services:
  ollama:
    deploy:
      resources:
        limits:
          memory: 16G
```

#### Issue: "SonarQube connection refused"

**Symptoms:**
```
ConnectionError: Failed to connect to SonarQube
```

**Solution:**
```bash
# Check URL is correct (no trailing slash)
echo $SONARQUBE_URL

# Test connection
curl -u ${SONARQUBE_TOKEN}: ${SONARQUBE_URL}/api/system/status

# Check token permissions
# Generate new token at: https://your-sonarqube.com/account/security/
```

#### Issue: "GitHub API rate limit exceeded"

**Symptoms:**
```
API rate limit exceeded
```

**Solution:**

Reduce rate limits in `config/agent-config.yaml`:

```yaml
behavior:
  rate_limiting:
    max_prs_per_hour: 3          # Reduce from 5
    max_comments_per_hour: 10     # Reduce from 20
    poll_interval_seconds: 600    # Increase to 10 minutes
```

#### Issue: "No findings being processed"

**Symptoms:**
```
Processing 0 findings from SonarQube...
```

**Possible causes:**

1. **Wrong project keys:**
   ```bash
   # List your projects
   curl -u ${SONARQUBE_TOKEN}: "${SONARQUBE_URL}/api/projects/search"

   # Update SONARQUBE_PROJECTS in .env with correct keys
   ```

2. **No issues matching severity filter:**

   Edit `config/agent-config.yaml`:
   ```yaml
   sonarqube:
     severities:
       - "CRITICAL"
       - "HIGH"
       - "MEDIUM"    # Add this to include more findings
   ```

3. **All issues already processed:**

   The agent tracks processed issues. This is normal after initial run.

#### Issue: "Python module not found"

**Symptoms:**
```
ModuleNotFoundError: No module named 'llama_stack'
```

**Solution:**
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep llama-stack
```

#### Issue: "GPU not available (Docker)"

**Symptoms:**
```
WARNING: No GPU found, falling back to CPU
```

**Solution:**

For CPU-only operation, comment out GPU settings in `docker-compose.yml`:

```yaml
services:
  ollama:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]
```

The agent will work on CPU, just slower.

### Getting Help

If you're still stuck:

1. **Check logs with debug level:**
   ```bash
   python -m sonarqube_agent.main --log-level DEBUG --dry-run
   ```

2. **Verify all prerequisites:**
   - Docker/Python version
   - Network connectivity to SonarQube and GitHub
   - Token permissions
   - Disk space for models

3. **Open an issue:**
   - GitHub Issues: https://github.com/yourorg/sonarqube-agent/issues
   - Include: logs, config (sanitized), error messages

---

## Common Use Cases

### Use Case 1: First-Time Setup and Testing

**Goal:** Test the agent safely without making changes.

```bash
# 1. Set up with dry-run mode
cp .env.example .env
# Edit .env with your credentials

# 2. Run in dry-run mode to see what would happen
python -m sonarqube_agent.main --once --dry-run --log-level INFO

# 3. Review the logs to see analysis results
# 4. When confident, remove --dry-run
```

### Use Case 2: Analyzing a Backlog of Issues

**Goal:** Process all existing findings from the past month.

```bash
# Process findings from the last 30 days
python -m sonarqube_agent.main --once --created-after 2024-01-01T00:00:00Z
```

### Use Case 3: Continuous Monitoring in Production

**Goal:** Run the agent 24/7 to monitor new findings.

**Docker (Recommended):**
```bash
# Start as daemon
docker-compose -f docker/docker-compose.yml up -d

# Agent runs continuously
# Check logs periodically
docker-compose -f docker/docker-compose.yml logs --tail=50 sonarqube-agent
```

**Local with systemd (Linux):**

Create `/etc/systemd/system/sonarqube-agent.service`:

```ini
[Unit]
Description=SonarQube Analysis Agent
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/sonarqube-analysis-agent
Environment="PATH=/path/to/sonarqube-analysis-agent/venv/bin"
ExecStart=/path/to/sonarqube-analysis-agent/venv/bin/python -m sonarqube_agent.main
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable sonarqube-agent
sudo systemctl start sonarqube-agent
sudo systemctl status sonarqube-agent
```

### Use Case 4: Development and Testing New Features

**Goal:** Develop or test agent modifications.

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install in editable mode with dev dependencies
pip install -e ".[dev]"

# 3. Make your changes to the code

# 4. Test with debug logging and dry-run
python -m sonarqube_agent.main --once --dry-run --log-level DEBUG

# 5. Run tests
pytest tests/

# 6. Format code
black src/
ruff check src/
```

### Use Case 5: Processing Only High-Priority Findings

**Goal:** Focus on critical security issues only.

Edit `config/agent-config.yaml`:

```yaml
sonarqube:
  severities:
    - "CRITICAL"    # Only process critical issues
  # Optionally filter by type
  types:
    - "VULNERABILITY"
    - "SECURITY_HOTSPOT"

behavior:
  prioritization:
    auto_fix_priorities:
      - "P0"        # Only auto-fix P0
```

Then run:
```bash
python -m sonarqube_agent.main
```

### Use Case 6: Weekly Security Review

**Goal:** Run weekly analysis and generate a report.

```bash
#!/bin/bash
# weekly-analysis.sh

# Set date range (last 7 days)
WEEK_AGO=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)

# Run analysis
python -m sonarqube_agent.main \
  --once \
  --created-after "$WEEK_AGO" \
  --log-file "weekly-report-$(date +%Y-%m-%d).log"

# The log file now contains the weekly analysis
echo "Weekly analysis complete: weekly-report-$(date +%Y-%m-%d).log"
```

Make it executable and schedule with cron:
```bash
chmod +x weekly-analysis.sh

# Add to crontab (run every Monday at 9 AM)
# crontab -e
0 9 * * 1 /path/to/weekly-analysis.sh
```

---

## Next Steps

1. **Start Small:** Begin with `--dry-run` mode on a single project
2. **Monitor Results:** Review logs and agent decisions for a few days
3. **Tune Configuration:** Adjust confidence thresholds based on accuracy
4. **Scale Up:** Add more projects and enable auto-fix for high-priority items
5. **Production Deployment:** Move to continuous mode with proper monitoring

## Additional Resources

- [Main README](../README.md) - Project overview and quick start
- [Agent Configuration](../config/agent-config.yaml) - Full configuration reference
- [Environment Variables](../.env.example) - All available environment variables
- [Contributing Guide](../CONTRIBUTING.md) - How to contribute
- [GitHub Issues](https://github.com/yourorg/sonarqube-agent/issues) - Report bugs or request features

---

**Happy analyzing!** 🤖 🔍
