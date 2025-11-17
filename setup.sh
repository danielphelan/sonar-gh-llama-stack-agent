#!/bin/bash
# Quick setup script for SonarQube Analysis Agent

set -e

echo "======================================"
echo "SonarQube Analysis Agent - Quick Setup"
echo "======================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your credentials:"
    echo "   - SONARQUBE_URL"
    echo "   - SONARQUBE_TOKEN"
    echo "   - SONARQUBE_PROJECTS"
    echo "   - GITHUB_TOKEN"
    echo "   - GITHUB_REPOS"
    echo ""
    read -p "Press Enter after you've configured .env file..."
else
    echo "✅ .env file already exists"
fi

# Start services
echo ""
echo "🚀 Starting services..."
docker-compose -f docker/docker-compose.yml up -d

echo ""
echo "⏳ Waiting for Ollama to start..."
sleep 5

# Check if models are already pulled
echo ""
echo "📥 Checking Ollama models..."

MODELS_NEEDED=("deepseek-coder-v2:33b" "codellama:13b" "llama3.1:8b")
MODELS_TO_PULL=()

for model in "${MODELS_NEEDED[@]}"; do
    if docker exec sonarqube-agent-ollama ollama list | grep -q "$model"; then
        echo "✅ $model already installed"
    else
        MODELS_TO_PULL+=("$model")
    fi
done

if [ ${#MODELS_TO_PULL[@]} -gt 0 ]; then
    echo ""
    echo "📥 Downloading required models (this may take a while)..."
    for model in "${MODELS_TO_PULL[@]}"; do
        echo "   Pulling $model..."
        docker exec sonarqube-agent-ollama ollama pull "$model"
    done
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🔍 To view logs:"
echo "   docker-compose -f docker/docker-compose.yml logs -f sonarqube-agent"
echo ""
echo "🛑 To stop services:"
echo "   docker-compose -f docker/docker-compose.yml down"
echo ""
echo "📊 The agent is now running in continuous mode!"
echo "   It will poll SonarQube every 5 minutes for new findings."
echo ""
