# Knowledge Base Agent - Getting Started Guide

**Version**: 2.0  
**Last Updated**: January 2025

---

## Table of Contents

1. [Introduction](#introduction)
2. [System Requirements](#system-requirements)
3. [Development Environment Setup](#development-environment-setup)
4. [Configuration](#configuration)
5. [Running the System](#running-the-system)
6. [Basic Usage](#basic-usage)
7. [Development Workflow](#development-workflow)
8. [Troubleshooting](#troubleshooting)
9. [Next Steps](#next-steps)

---

## Introduction

The Knowledge Base Agent is an AI-driven system that automates the creation and maintenance of structured knowledge bases from Twitter bookmarks. This guide will help you set up your development environment, run the system locally, and understand the basic usage patterns.

### Key Features

- **Automated Content Processing**: Fetches and processes Twitter bookmarks
- **AI-Powered Categorization**: Uses LLMs to categorize content
- **Knowledge Base Generation**: Creates structured Markdown documentation
- **Conversational AI**: RAG-powered chat interface for knowledge base interaction
- **Real-time Monitoring**: Live progress tracking and system monitoring

---

## System Requirements

### Hardware Requirements

- **CPU**: 4+ cores recommended (8+ cores for optimal performance)
- **RAM**: 16GB minimum (32GB+ recommended)
- **GPU**: NVIDIA GPU with 8GB+ VRAM (24GB+ recommended for larger models)
- **Storage**: 20GB+ free space for application and data

### Software Requirements

- **Operating System**: Linux (Ubuntu 22.04+ recommended), macOS, or Windows with WSL2
- **Python**: 3.10 or higher
- **Redis**: 6.2 or higher
- **Ollama**: 0.1.27 or higher (for local LLM execution)
- **Git**: 2.30 or higher

---

## Development Environment Setup

### 1. Clone the Repository

```bash
# Clone the repository
git clone https://github.com/your-org/knowledge-base-agent.git
cd knowledge-base-agent
```

### 2. Set Up Python Environment

```bash
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Install System Dependencies

#### Ubuntu/Debian

```bash
# Install Redis
sudo apt update
sudo apt install redis-server

# Start Redis service
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Verify Redis is running
redis-cli ping  # Should return "PONG"
```

#### macOS

```bash
# Install Redis using Homebrew
brew install redis

# Start Redis service
brew services start redis

# Verify Redis is running
redis-cli ping  # Should return "PONG"
```

### 4. Install Ollama

#### Linux

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve &

# Pull required models (this may take a while)
ollama pull llama3.1:70b-instruct-q4_0
ollama pull llava:13b
ollama pull mxbai-embed-large
```

#### macOS

```bash
# Download and install Ollama from https://ollama.ai/download
# Or use Homebrew
brew install ollama

# Start Ollama
ollama serve &

# Pull required models
ollama pull llama3.1:70b-instruct-q4_0
ollama pull llava:13b
ollama pull mxbai-embed-large
```

### 5. Verify Installation

```bash
# Check Python version
python --version  # Should be 3.10+

# Check Redis connection
redis-cli ping    # Should return "PONG"

# Check Ollama models
ollama list       # Should show installed models

# Check GPU availability (if applicable)
nvidia-smi        # Should show GPU information
```

---

## Configuration

### 1. Create Environment File

```bash
# Copy the example environment file
cp .env.example .env

# Edit the environment file
nano .env  # or your preferred editor
```

### 2. Essential Configuration Variables

Here are the key variables you need to configure:

```bash
# Core Configuration
OLLAMA_URL=http://localhost:11434
TEXT_MODEL=llama3.1:70b-instruct-q4_0
VISION_MODEL=llava:13b
EMBEDDING_MODEL=mxbai-embed-large

# Twitter/X Configuration (required for bookmark fetching)
X_BEARER_TOKEN=your_twitter_bearer_token_here
X_BOOKMARKS_URL=https://api.twitter.com/2/users/your_user_id/bookmarks

# GitHub Configuration (optional, for auto-commit/push)
GITHUB_TOKEN=your_github_token_here
GITHUB_REPO_URL=https://github.com/your-username/your-repo.git

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# GPU Configuration (adjust based on your hardware)
OLLAMA_NUM_GPU=-1  # Use all available GPUs
OLLAMA_MAIN_GPU=0  # Primary GPU index
```

### 3. Twitter API Setup

To fetch bookmarks, you'll need Twitter API credentials:

1. Go to [Twitter Developer Portal](https://developer.twitter.com/)
2. Create a new app or use an existing one
3. Generate a Bearer Token
4. Add the token to your `.env` file as `X_BEARER_TOKEN`

### 4. Hardware Optimization

Run the hardware detection to optimize settings:

```bash
# Generate optimized Ollama settings
python -c "
from knowledge_base_agent.config import Config
from knowledge_base_agent.hardware_detection import HardwareDetector

config = Config()
detector = HardwareDetector(config)
optimization = detector.generate_ollama_optimization('performance')
print('Add these to your .env file:')
for key, value in optimization['env_vars'].items():
    print(f'{key}={value}')
"
```

---

## Running the System

### 1. Initialize the Database

```bash
# Initialize the database
python -c "
from knowledge_base_agent.models import db
from knowledge_base_agent.app import create_app
app = create_app()
with app.app_context():
    db.create_all()
    print('Database initialized successfully')
"
```

### 2. Start Redis and Ollama

```bash
# Start Redis (if not already running)
redis-server &

# Start Ollama (if not already running)
ollama serve &
```

### 3. Start Celery Worker

```bash
# Start Celery worker in a separate terminal
celery -A knowledge_base_agent.celery_app worker --loglevel=info
```

### 4. Start the Web Application

```bash
# Start the Flask web application
python -m knowledge_base_agent.app
```

The application will be available at `http://localhost:5000`.

### 5. Alternative: Use the Service Scripts

For production-like setup, you can use the provided service scripts:

```bash
# Install as system services
sudo ./install-services.sh

# Manage services
./manage-services.sh start    # Start all services
./manage-services.sh stop     # Stop all services
./manage-services.sh status   # Check service status
./manage-services.sh restart  # Restart all services
```

---

## Basic Usage

### 1. Web Interface

Open your browser and navigate to `http://localhost:5000`.

#### Dashboard Overview

- **Agent Status**: Shows current agent state and progress
- **System Information**: Hardware stats, GPU usage, model information
- **Recent Logs**: Live log stream from agent operations
- **Configuration**: Environment variables and preferences

#### Running the Agent

1. Click on the **"Agent Control"** section
2. Configure your preferences:
   - **Run Mode**: Choose from full pipeline, fetch only, synthesis only, etc.
   - **Force Options**: Force regeneration of specific components
   - **Skip Options**: Skip certain phases of processing
3. Click **"Start Agent"** to begin processing

#### Monitoring Progress

- Watch the **progress bar** for overall completion
- Monitor **live logs** for detailed operation information
- Check **GPU stats** if using GPU acceleration
- View **phase updates** to see which stage is currently running

### 2. API Usage

#### Start Agent via API

```bash
curl -X POST http://localhost:5000/api/agent/start \
  -H "Content-Type: application/json" \
  -d '{
    "preferences": {
      "run_mode": "full_pipeline",
      "skip_readme_generation": true,
      "synthesis_mode": "comprehensive"
    }
  }'
```

#### Check Agent Status

```bash
curl http://localhost:5000/api/agent/status
```

#### Get Knowledge Base Items

```bash
curl http://localhost:5000/api/kb/all
```

### 3. Chat Interface

#### Using the Web Chat

1. Navigate to the **Chat** section in the web interface
2. Select your preferred model from the dropdown
3. Type your question about the knowledge base content
4. The system will provide answers based on your processed content

#### Chat via API

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the key concepts in React hooks?",
    "session_id": "my_session",
    "model": "llama3.1:70b-instruct-q4_0"
  }'
```

### 4. Typical Workflow

1. **Initial Setup**: Configure Twitter credentials and preferences
2. **First Run**: Execute full pipeline to process all bookmarks
3. **Regular Updates**: Run incremental updates to process new bookmarks
4. **Content Exploration**: Use chat interface to explore generated knowledge base
5. **Customization**: Adjust preferences and regenerate specific content as needed

---

## Development Workflow

### 1. Project Structure

```
knowledge-base-agent/
├── knowledge_base_agent/          # Main application package
│   ├── __init__.py
│   ├── app.py                     # Flask application factory
│   ├── config.py                  # Configuration management
│   ├── models.py                  # Database models
│   ├── agent.py                   # Main agent orchestrator
│   ├── content_processor.py       # Content processing logic
│   ├── state_manager.py           # State management and validation
│   ├── tasks/                     # Celery tasks
│   ├── api/                       # REST API routes
│   └── utils/                     # Utility modules
├── docs/                          # Documentation
├── data/                          # Data storage
├── kb-generated/                  # Generated knowledge base
├── logs/                          # Log files
├── migrations/                    # Database migrations
└── requirements.txt               # Python dependencies
```

### 2. Making Changes

#### Code Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the existing code patterns

3. **Test your changes**:
   ```bash
   # Run basic functionality test
   python -c "from knowledge_base_agent.config import Config; print('Config loads successfully')"
   
   # Test database connection
   python -c "
   from knowledge_base_agent.models import db
   from knowledge_base_agent.app import create_app
   app = create_app()
   with app.app_context():
       print('Database connection successful')
   "
   ```

4. **Commit and push**:
   ```bash
   git add .
   git commit -m "Add: your feature description"
   git push origin feature/your-feature-name
   ```

#### Configuration Changes

- **Environment Variables**: Add new variables to `.env.example` and document them
- **Database Schema**: Create migrations using Flask-Migrate
- **Dependencies**: Update `requirements.txt` when adding new packages

### 3. Debugging

#### Enable Debug Logging

```bash
# Set debug level in environment
export LOG_LEVEL=DEBUG

# Or add to .env file
echo "LOG_LEVEL=DEBUG" >> .env
```

#### Common Debug Commands

```bash
# Check Celery worker status
celery -A knowledge_base_agent.celery_app inspect active

# Monitor Redis activity
redis-cli monitor

# Check Ollama model status
ollama ps

# View recent logs
tail -f logs/agent_$(date +%Y%m%d)_*.log
```

#### Using the Python Debugger

```python
# Add breakpoints in your code
import pdb; pdb.set_trace()

# Or use the more modern debugger
import ipdb; ipdb.set_trace()
```

---

## Troubleshooting

### Common Issues

#### 1. Ollama Connection Failed

**Symptoms**: `Connection refused` errors when trying to use LLM models

**Solutions**:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve &

# Check if models are installed
ollama list

# Pull missing models
ollama pull llama3.1:70b-instruct-q4_0
```

#### 2. Redis Connection Issues

**Symptoms**: `Connection refused` errors, Celery tasks not executing

**Solutions**:
```bash
# Check Redis status
redis-cli ping

# Start Redis if not running
redis-server &

# Check Redis configuration
redis-cli config get "*"
```

#### 3. GPU Not Detected

**Symptoms**: Models running slowly, GPU utilization at 0%

**Solutions**:
```bash
# Check GPU availability
nvidia-smi

# Check CUDA installation
nvcc --version

# Verify Ollama GPU settings
echo $OLLAMA_NUM_GPU
echo $OLLAMA_MAIN_GPU

# Test GPU with Ollama
ollama run llama3.1:70b-instruct-q4_0 "Hello" --verbose
```

#### 4. Twitter API Authentication

**Symptoms**: `401 Unauthorized` errors when fetching bookmarks

**Solutions**:
- Verify your Bearer Token is correct
- Check that your Twitter app has the necessary permissions
- Ensure the user ID in the bookmarks URL is correct

#### 5. Database Migration Issues

**Symptoms**: Database schema errors, missing tables

**Solutions**:
```bash
# Initialize database
python -c "
from knowledge_base_agent.models import db
from knowledge_base_agent.app import create_app
app = create_app()
with app.app_context():
    db.create_all()
"

# Or use Flask-Migrate if available
flask db upgrade
```

### Performance Issues

#### 1. Slow Processing

**Potential Causes**:
- Insufficient GPU memory
- Too many concurrent requests
- Network latency to Ollama

**Solutions**:
- Reduce `MAX_CONCURRENT_REQUESTS` in environment
- Increase `OLLAMA_KEEP_ALIVE` to keep models loaded
- Use smaller models for testing

#### 2. High Memory Usage

**Solutions**:
- Reduce batch sizes in processing
- Enable `OLLAMA_LOW_VRAM=true` for GPU memory constraints
- Monitor and adjust `OLLAMA_NUM_CTX` for context window size

### Getting Help

#### 1. Check Logs

```bash
# Application logs
tail -f logs/agent_$(date +%Y%m%d)_*.log

# Web server logs
tail -f logs/web.log

# Celery logs
tail -f logs/celery.log
```

#### 2. System Information

```bash
# Get comprehensive system info
curl http://localhost:5000/api/system/info
```

#### 3. Debug Mode

```bash
# Run with debug enabled
export FLASK_DEBUG=1
export LOG_LEVEL=DEBUG
python -m knowledge_base_agent.app
```

---

## Next Steps

### 1. Explore the Documentation

- **[Architecture Guide](ARCHITECTURE.md)**: Understand the system architecture
- **[API Reference](API_REFERENCE.md)**: Detailed API documentation
- **[Environment Variables](environment_variables.md)**: Complete configuration reference

### 2. Customize Your Setup

- **Model Selection**: Experiment with different Ollama models
- **Processing Preferences**: Adjust synthesis modes and processing options
- **Hardware Optimization**: Fine-tune GPU and performance settings

### 3. Advanced Features

- **Custom Categories**: Modify categorization logic
- **Synthesis Templates**: Create custom synthesis formats
- **Integration**: Build custom integrations using the API
- **Monitoring**: Set up advanced monitoring and alerting

### 4. Contributing

- **Report Issues**: Use GitHub issues for bug reports
- **Feature Requests**: Propose new features and improvements
- **Pull Requests**: Contribute code improvements and fixes
- **Documentation**: Help improve documentation and examples

### 5. Production Deployment

- **Security**: Implement authentication and authorization
- **Scaling**: Set up multiple Celery workers and Redis clustering
- **Monitoring**: Implement comprehensive logging and monitoring
- **Backup**: Set up automated backups for data and configuration

---

**Happy coding! 🚀**

For additional help, check the documentation in the `docs/` directory or reach out to the development team.

---

**Document Version**: 2.0  
**Last Updated**: January 2025