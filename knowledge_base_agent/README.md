# Knowledge Base Agent

![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Directory Structure](#directory-structure)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Overview

The **Knowledge Base Agent** is an automated system designed to process tweets, extract and interpret their content and associated media, categorize them into predefined technical categories, and organize the information into a structured knowledge base. This knowledge base is maintained in a GitHub repository, ensuring version control and easy access.

### Key Capabilities

- **Tweet Processing**: Extracts text and media from bookmarked tweets.
- **Image Interpretation**: Utilizes AI models to generate concise descriptions of images.
- **Content Categorization**: Classifies content into structured categories and subcategories.
- **Automated Documentation**: Generates Markdown files (`content.md`) for each knowledge item.
- **GitHub Integration**: Automatically pushes updates to a GitHub repository, maintaining an up-to-date knowledge base.

## Features

- **Automated Tweet Extraction**: Reads bookmarked tweet URLs and extracts relevant data.
- **AI-Powered Image Descriptions**: Leverages vision models (e.g., Ollama) to interpret and describe images.
- **Robust Categorization System**: Employs a structured category management system to classify content accurately.
- **Dynamic Markdown Generation**: Creates well-formatted Markdown files for easy readability and navigation.
- **Git Integration**: Seamlessly integrates with GitHub for version control and repository management.
- **Error Handling & Logging**: Comprehensive logging mechanism to monitor and troubleshoot the pipeline.

## Architecture

![Architecture Diagram](docs/architecture_diagram.png) <!-- Placeholder for an actual diagram -->

1. **Input Layer**: Reads bookmarked tweet URLs from `data/bookmarks_links.txt`.
2. **Data Extraction**: Utilizes Playwright to fetch tweet text and associated media.
3. **Image Processing**: Downloads images and sends them to the vision model for interpretation.
4. **Categorization**: Combines tweet text and image descriptions to categorize the content.
5. **Documentation**: Generates Markdown files with structured content and organizes media assets.
6. **Version Control**: Commits and pushes changes to the specified GitHub repository.
7. **Logging**: Maintains detailed logs for monitoring and debugging purposes.

## Prerequisites

Before setting up the Knowledge Base Agent, ensure that the following prerequisites are met:

- **Operating System**: Linux, macOS, or Windows.
- **Python**: Version 3.8 or higher.
- **Git**: Installed and configured on your system.
- **GitHub Account**: Access to a GitHub repository where the knowledge base will be maintained.
- **Ollama Access**: Access to the Ollama AI models for image and text processing.
- **Playwright Browsers**: Necessary browsers installed for Playwright to function correctly.

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/knowledge-base-agent.git
cd knowledge-base-agent

python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt

playwright install

git lfs install

Populate the .env File

# AI Model Configuration
VISION_MODEL=your_vision_model_name
TEXT_MODEL=your_text_model_name

# Ollama Configuration
OLLAMA_URL=http://localhost:11434  # Replace with your actual Ollama URL

# GitHub Configuration
GITHUB_TOKEN=your_github_token
GITHUB_USER_NAME=your_github_username
GITHUB_USER_EMAIL=your_github_email
GITHUB_REPO_URL=https://github.com/yourusername/your-repo.git


Populate .gitignore
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Virtual Environment
venv/
env/
ENV/
env.bak/
venv.bak/

# Logs
*.log

# Environment Variables
.env

# Playwright Browsers
.playwright/

# Git LFS (if used)
*.jpg
*.jpeg
*.png
*.gif
*.mp4

# Temporary Images
temp_image_*.jpg

# Other
*.DS_Store
*.sqlite3



