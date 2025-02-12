# Knowledge Base Agent

A tool to build and maintain a technical knowledge base by processing tweet content and generating a structured Markdown repository.

## Features

- **Tweet Processing:** Extracts tweet text and metadata from tweet URLs
- **Knowledge Organization:** Organizes technical knowledge into categories and subcategories
- **Markdown Generation:** Generates individual Markdown files for each knowledge item and maintains a root README that indexes all content
- **Interactive Categorization:** Allows manual categorization of items during processing
- **Structured Knowledge Base:** Creates and maintains a hierarchical directory structure for organized knowledge storage

## Requirements

- Python 3.8 or higher

## Setup

### 1. Set Up a Virtual Environment

```bash
python -m venv venv
```

Activate the virtual environment:

**On Windows:**
```bash
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
source venv/bin/activate
```

### 2. Clone the Repository

```bash
git clone <repo_url>
cd knowledge_base_agent
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Project Structure

The project consists of several key components:

- `KnowledgeBaseAgent`: Main class that coordinates the knowledge base operations
- `CategoryManager`: Handles category and subcategory management
- `TweetManager`: Manages tweet processing and tracking
- `MarkdownWriter`: Generates markdown content and maintains the knowledge base structure

### 5. Directory Structure

```
knowledge-base/
├── cloud_computing/
│   ├── aws/
│   ├── best_practices/
│   └── ...
├── software_engineering/
│   ├── best_practices/
│   └── ...
└── README.md
```

## Usage

Run the main program using:

```bash
python -m knowledge_base_agent.main
```

During execution, you will be prompted to:

1. Configure categories and subcategories (if not already set up)
2. Process new tweets and categorize them
3. Review and organize content into the knowledge base

The process will:
- Create a structured knowledge base directory
- Generate markdown files for each knowledge item
- Maintain an indexed README of all content
- Organize content by categories and subcategories

## Project Components

### KnowledgeBaseAgent
- Coordinates the overall process
- Manages initialization and configuration
- Handles tweet processing workflow

### CategoryManager
- Manages knowledge base categories and subcategories
- Maintains category hierarchy
- Provides category-related utilities

### TweetManager
- Handles tweet processing
- Tracks processed vs unprocessed tweets
- Manages tweet metadata

### MarkdownWriter
- Generates markdown content
- Creates and updates the root README
- Maintains consistent formatting

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.