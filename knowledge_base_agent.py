import os
import json
import base64
import requests
import re
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from dataclasses import dataclass
from typing import List, Dict, Set, Optional
import nest_asyncio
import logging
import uuid
import datetime
import subprocess
import shutil

# Apply nest_asyncio to allow nested event loops in environments like Jupyter
nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    filename='agent_program.log',
    level=logging.DEBUG,  # Set to DEBUG for detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# -----------------------------
# Setup and Configuration
# -----------------------------

# Load environment variables from .env file
load_dotenv()

# Read model names from environment variables
VISION_MODEL = os.getenv("VISION_MODEL")
TEXT_MODEL = os.getenv("TEXT_MODEL") 

# Read Ollama URL from environment variables
OLLAMA_URL = os.getenv("OLLAMA_URL")

# Read GitHub configuration from environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USER_NAME = os.getenv("GITHUB_USER_NAME")
GITHUB_USER_EMAIL = os.getenv("GITHUB_USER_EMAIL")
GITHUB_REPO_URL = os.getenv("GITHUB_REPO_URL")

# Ensure necessary directories exist
KNOWLEDGE_BASE_DIR = Path("knowledge-base")
CATEGORIES_FILE = Path("data/categories.json")
BOOKMARKS_FILE = Path("data/bookmarks_links.txt")
PROCESSED_TWEETS_FILE = Path("data/processed_tweets.json")

KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
CATEGORIES_FILE.parent.mkdir(parents=True, exist_ok=True)
PROCESSED_TWEETS_FILE.parent.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Verify Environment Variables
# -----------------------------

def verify_env_vars():
    missing_vars = []
    if not OLLAMA_URL:
        missing_vars.append("OLLAMA_URL")
    if not TEXT_MODEL:
        missing_vars.append("TEXT_MODEL")
    if not GITHUB_TOKEN:
        missing_vars.append("GITHUB_TOKEN")
    if not GITHUB_USER_NAME:
        missing_vars.append("GITHUB_USER_NAME")
    if not GITHUB_USER_EMAIL:
        missing_vars.append("GITHUB_USER_EMAIL")
    if not GITHUB_REPO_URL:
        missing_vars.append("GITHUB_REPO_URL")
    if missing_vars:
        logging.error(f"Missing environment variables: {', '.join(missing_vars)}")
        print(f"Error: Missing environment variables: {', '.join(missing_vars)}")
        exit(1)  # Exit the script as these variables are critical
    else:
        logging.debug(f"All essential environment variables are set.")
        print(f"All essential environment variables are set.")

# Call the verification function
verify_env_vars()

# Log the loaded TEXT_MODEL
logging.debug(f"Loaded TEXT_MODEL: {TEXT_MODEL}")
print(f"Loaded TEXT_MODEL: {TEXT_MODEL}")

# Initialize Category Manager
category_manager = None  # Initialize to None for proper order
print(f"Loaded Initialized Category Manager")

# -----------------------------
# Category Management System
# -----------------------------

@dataclass
class Category:
    name: str
    subcategories: Set[str]
    description: str
    keywords: Set[str]

class CategoryManager:
    def __init__(self, categories_file: Path):
        self.categories_file = categories_file
        self.categories: Dict[str, Category] = {}
        self._initialize_default_categories()
        self.load_categories()

    def _initialize_default_categories(self):
        """Initialize the default category structure with descriptions and keywords."""
        default_structure = {
            # Engineering & Development
            "software_engineering": {
                "subcategories": {
                    "design_patterns", "code_quality", "best_practices",
                    "algorithms", "documentation", "code_review"
                },
                "description": "Core software engineering principles and practices",
                "keywords": {
                    "clean code", "patterns", "solid principles", "engineering",
                    "software design", "development practices"
                }
            },
            "system_design": {
                "subcategories": {
                    "architecture", "scalability", "distributed_systems",
                    "system_patterns", "integration", "apis"
                },
                "description": "System architecture and design principles",
                "keywords": {
                    "architecture", "systems", "design", "scale", "distributed",
                    "integration patterns"
                }
            },

            # DevOps & Infrastructure
            "devops": {
                "subcategories": {
                    "ci_cd", "automation", "deployment", "monitoring",
                    "infrastructure", "configuration"
                },
                "description": "DevOps practices and tools",
                "keywords": {
                    "pipeline", "continuous integration", "deployment", "devops",
                    "automation", "infrastructure"
                }
            },
            "cloud_computing": {
                "subcategories": {
                    "aws", "azure", "gcp", "cloud_native", "serverless",
                    "containers"
                },
                "description": "Cloud platforms and services",
                "keywords": {
                    "cloud", "aws", "azure", "serverless", "containers",
                    "kubernetes"
                }
            },

            # Data & Analytics
            "data_engineering": {
                "subcategories": {
                    "data_pipelines", "etl", "data_modeling", "data_quality",
                    "data_integration", "data_governance"
                },
                "description": "Data engineering and processing",
                "keywords": {
                    "data", "pipelines", "etl", "modeling", "integration",
                    "processing"
                }
            },
            "machine_learning": {
                "subcategories": {
                    "ml_ops", "model_deployment", "ai_engineering",
                    "model_architecture", "training_pipelines"
                },
                "description": "Machine learning engineering",
                "keywords": {
                    "ml", "ai", "models", "training", "inference", "mlops"
                }
            },

            # Security & Performance
            "security": {
                "subcategories": {
                    "authentication", "authorization", "encryption",
                    "security_patterns", "devsecops", "compliance"
                },
                "description": "Security engineering and practices",
                "keywords": {
                    "security", "auth", "encryption", "compliance", "devsecops",
                    "protection"
                }
            },
            "performance": {
                "subcategories": {
                    "optimization", "scaling", "caching", "load_balancing",
                    "performance_testing", "efficiency"
                },
                "description": "Performance engineering",
                "keywords": {
                    "performance", "optimization", "scaling", "efficiency",
                    "speed", "latency"
                }
            },

            # Management & Process
            "engineering_management": {
                "subcategories": {
                    "team_leadership", "technical_strategy", "mentoring",
                    "process_improvement", "engineering_culture"
                },
                "description": "Engineering management and leadership",
                "keywords": {
                    "leadership", "management", "team", "strategy", "culture",
                    "mentoring"
                }
            },
            "agile_practices": {
                "subcategories": {
                    "scrum", "kanban", "lean", "estimation",
                    "sprint_planning", "retrospectives"
                },
                "description": "Agile methodologies and practices",
                "keywords": {
                    "agile", "scrum", "kanban", "sprints", "planning",
                    "ceremonies"
                }
            }
        }

        for cat_name, details in default_structure.items():
            self.categories[cat_name] = Category(
                name=cat_name,
                subcategories=details["subcategories"],
                description=details["description"],
                keywords=set(word.lower() for word in details["keywords"])
            )

    def save_categories(self):
        """Save categories to JSON file."""
        categories_dict = {
            name: {
                "subcategories": list(cat.subcategories),
                "description": cat.description,
                "keywords": list(cat.keywords)
            }
            for name, cat in self.categories.items()
        }
        
        with self.categories_file.open('w', encoding='utf-8') as f:
            json.dump(categories_dict, f, indent=4)
        logging.info(f"Saved {len(self.categories)} categories to {self.categories_file}")
        print(f"Saved {len(self.categories)} categories to {self.categories_file}")

    
    def load_categories(self):
        """Load categories from JSON file if it exists."""
        if self.categories_file.exists():
            try:
                with self.categories_file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.categories = {
                        name: Category(
                            name=name,
                            subcategories=set(details["subcategories"]),
                            description=details["description"],
                            keywords=set(word.lower() for word in details["keywords"])
                        )
                        for name, details in data.items()
                    }
                logging.info(f"Loaded {len(self.categories)} categories from file")
                print(f"Loaded {len(self.categories)} categories from file")
            except Exception as e:
                logging.error(f"Error loading categories: {e}")
                print(f"Error loading categories: {e}")
        else:
            self.save_categories()
            logging.info("Created new categories file with defaults")
            print("Created new categories file with defaults")


    def add_category(self, name: str, description: str, keywords: Set[str]) -> bool:
        """Add a new category with validation."""
        name = self._normalize_name(name)
        if name in self.categories:
            return False
        
        self.categories[name] = Category(
            name=name,
            subcategories=set(),
            description=description,
            keywords=set(word.lower() for word in keywords)
        )
        self.save_categories()
        return True

    def add_subcategory(self, category: str, subcategory: str) -> bool:
        """Add a subcategory to an existing category."""
        if category not in self.categories:
            return False
        
        subcategory = self._normalize_name(subcategory)
        self.categories[category].subcategories.add(subcategory)
        self.save_categories()
        return True

    def get_category_suggestions(self, content: str, num_suggestions: int = 3) -> List[tuple]:
        """
        Get category suggestions based on content keyword matching.
        Returns list of (category, subcategory, score) tuples.
        """
        content_words = set(self._normalize_name(content).split('_'))
        suggestions = []

        for cat_name, category in self.categories.items():
            # Calculate match score based on keyword overlap
            keyword_matches = len(content_words & category.keywords)
            if keyword_matches > 0:
                # Find best matching subcategory
                best_subcategory = None
                best_subscore = 0
                
                for subcategory in category.subcategories:
                    subscore = len(content_words & set(subcategory.split('_')))
                    if subscore > best_subscore:
                        best_subscore = subscore
                        best_subcategory = subcategory

                score = keyword_matches + (best_subscore * 0.5)
                suggestions.append((cat_name, best_subcategory or "best_practices", score))

        # Sort by score and return top suggestions
        return sorted(suggestions, key=lambda x: x[2], reverse=True)[:num_suggestions]

    def _normalize_name(self, name: str) -> str:
        """Normalize category/subcategory names."""
        return name.lower().replace(' ', '_').strip('_')

    def get_all_categories(self) -> List[str]:
        """Get list of all category names."""
        return sorted(self.categories.keys())

    def get_subcategories(self, category: str) -> List[str]:
        """Get list of subcategories for a given category."""
        if category in self.categories:
            return sorted(self.categories[category].subcategories)
        return []

    def get_category_info(self, category: str) -> Optional[Category]:
        """Get detailed information about a category."""
        return self.categories.get(category)

# Initialize Category Manager after defining the class
category_manager = CategoryManager(CATEGORIES_FILE)
print(f"Initialized Category Manager with {len(category_manager.categories)} categories.")

# -----------------------------
# Category Validation and Normalization
# -----------------------------

def validate_category(name: str) -> bool:
    """
    Validates that the category name meets the criteria:
    - 1-5 words
    - No special characters except underscores and hyphens
    """
    if not name:
        return False
    # Check for allowed characters: letters, numbers, spaces, hyphens, underscores
    if not re.match(r'^[\w\s-]{1,50}$', name):
        return False
    # Check word count
    if not (1 <= len(name.split()) <= 5):
        return False
    return True

def normalize_name_for_filesystem(name: str, max_length: int = 30) -> str:
    """
    Creates a safe, normalized name for filesystem use.
    Args:
        name: The name to normalize
        max_length: Maximum length for the normalized name
    Returns:
        A filesystem-safe name
    """
    # Remove newlines and extra whitespace
    name = ' '.join(name.split())
    
    # Convert to lowercase and replace spaces with underscores
    name = name.lower().replace(' ', '_')
    
    # Remove any characters that aren't alphanumeric, underscore, or hyphen
    name = re.sub(r'[^\w-]', '', name)
    
    # Remove consecutive underscores or hyphens
    name = re.sub(r'[-_]+', '_', name)
    
    # Trim to max length while keeping whole words
    if len(name) > max_length:
        name = name[:max_length].rsplit('_', 1)[0]
    
    # Remove leading/trailing underscores or hyphens
    name = name.strip('_-')
    
    # Ensure we have a valid name
    if not name:
        return f"unnamed_{uuid.uuid4().hex[:8]}"
    
    return name

def safe_directory_name(name: str) -> str:
    """
    Creates a safe directory name, ensuring uniqueness if needed.
    """
    # First normalize the name
    safe_name = normalize_name_for_filesystem(name)
    
    # If the name is empty after normalization, use a UUID
    if not safe_name:
        return f"unnamed_{uuid.uuid4().hex[:8]}"
        
    return safe_name

def validate_directory_name(name: str) -> bool:
    """
    Validates the directory name to ensure it meets filesystem requirements.
    """
    # Define maximum length
    MAX_LENGTH = 50
    if len(name) > MAX_LENGTH:
        return False
    # Check for invalid characters (already handled in normalization, but double-check)
    if re.search(r'[<>:"/\\|?*]', name):
        return False
    return True

def process_category_response(response: str, tweet_id: str) -> tuple:
    """
    Process and validate the category response from the AI.
    Returns tuple of (main_category, sub_category, item_name)
    """
    try:
        # Split into category and name parts
        if '|' not in response:
            raise ValueError("Response doesn't contain expected '|' separator")
            
        category_part, item_name = [x.strip() for x in response.split('|', 1)]
        
        # Split category into main and sub
        if '/' not in category_part:
            raise ValueError("Category doesn't contain expected '/' separator")
            
        main_category, sub_category = [x.strip() for x in category_part.split('/', 1)]
        
        # Normalize all parts
        main_category = normalize_name_for_filesystem(main_category)
        sub_category = normalize_name_for_filesystem(sub_category)
        item_name = normalize_name_for_filesystem(item_name)
        
        # Further ensure item_name length
        if len(item_name) > 25:  # Adjust as needed
            unique_suffix = tweet_id[:6]
            item_name = f"{item_name[:20]}_{unique_suffix}"
        
        # Final validation
        if not validate_directory_name(item_name):
            raise ValueError("Item name failed final validation.")
        
        return (main_category, sub_category, item_name)
        
    except Exception as e:
        logging.error(f"Error processing category response: {e}")
        # Fallback to default values
        return ("software_engineering", "best_practices", f"tech_note_{tweet_id[:8]}")

# -----------------------------
# Git Helper Functions
# -----------------------------

def run_git_command(cmd, cwd, capture_output=False):
    """
    Runs a git command in the specified directory.
    """
    try:
        if capture_output:
            result = subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, cwd=cwd, check=True)
            return None
    except subprocess.CalledProcessError as e:
        logging.error(f"Git command {' '.join(cmd)} failed: {e}")
        print(f"Git command {' '.join(cmd)} failed: {e}")
        return None

def push_to_github(knowledge_base_dir: Path, github_repo_url: str, github_token: str, git_user_name: str, git_user_email: str):
    """
    Force pushes the knowledge-base directory to the specified GitHub repository using the provided token.
    This will overwrite the remote repository's history with the local repository's history.
    """
    # Define remote URL with token for authentication
    if "@" not in github_repo_url:
        remote_url = github_repo_url.replace("https://", f"https://{github_token}@")
    else:
        # If already contains authentication
        remote_url = github_repo_url

    # Check if knowledge_base_dir is a git repository
    if not (knowledge_base_dir / ".git").exists():
        # Initialize git repository with main branch
        run_git_command(["git", "init", "-b", "main"], cwd=knowledge_base_dir)
        logging.info("Initialized new git repository with main branch.")
        print("Initialized new git repository with main branch.")
        
        # Set remote
        run_git_command(["git", "remote", "add", "origin", remote_url], cwd=knowledge_base_dir)
        logging.info(f"Added remote origin: {remote_url}")
        print(f"Added remote origin: {remote_url}")
        
    else:
        logging.info("Git repository already initialized.")
        print("Git repository already initialized.")
    
    # Configure user name and email locally
    run_git_command(["git", "config", "user.name", git_user_name], cwd=knowledge_base_dir)
    run_git_command(["git", "config", "user.email", git_user_email], cwd=knowledge_base_dir)
    logging.info("Configured git user name and email.")
    print("Configured git user name and email.")
    
    # Disable global excludes and attributes by setting them to local files
    run_git_command(["git", "config", "core.excludesFile", "/dev/null"], cwd=knowledge_base_dir)
    run_git_command(["git", "config", "core.attributesFile", "/dev/null"], cwd=knowledge_base_dir)
    logging.info("Configured core.excludesFile and core.attributesFile to local settings.")
    print("Configured core.excludesFile and core.attributesFile to local settings.")
    
    # Verify local git config
    local_email = run_git_command(["git", "config", "--get", "user.email"], cwd=knowledge_base_dir, capture_output=True)
    local_name = run_git_command(["git", "config", "--get", "user.name"], cwd=knowledge_base_dir, capture_output=True)
    print(f"Local Git Config - Name: {local_name}, Email: {local_email}")
    logging.info(f"Local Git Config - Name: {local_name}, Email: {local_email}")
    
    # Stage all changes
    run_git_command(["git", "add", "-A"], cwd=knowledge_base_dir)
    logging.info("Staged all changes.")
    print("Staged all changes.")
    
    # Attempt to commit changes
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_message = f"Update knowledge base: {timestamp}"
    commit_result = run_git_command(["git", "commit", "-m", commit_message], cwd=knowledge_base_dir)
    
    if commit_result is None:
        # If no changes to commit, create an empty commit
        logging.info("No changes detected. Creating an empty commit to force push.")
        print("No changes detected. Creating an empty commit to force push.")
        run_git_command(["git", "commit", "--allow-empty", "-m", f"Empty commit: {timestamp}"], cwd=knowledge_base_dir)
        logging.info("Created an empty commit.")
        print("Created an empty commit.")
    else:
        logging.info(f"Committed changes with message: {commit_message}")
        print(f"Committed changes with message: {commit_message}")
    
    # Force push changes to overwrite remote history
    push_result = run_git_command(["git", "push", "origin", "main", "--force"], cwd=knowledge_base_dir)
    if push_result is not None:
        logging.info("Force pushed changes to GitHub.")
        print("Force pushed changes to GitHub.")
    else:
        logging.error("Failed to force push changes to GitHub.")
        print("Failed to force push changes to GitHub.")

# -----------------------------
# Tweet Parsing
# -----------------------------

def parse_tweet_id_from_url(url: str) -> Optional[str]:
    """
    Extracts the tweet ID from a given Twitter URL.
    Example:
    Input: "https://x.com/user/status/1234567890123456789"
    Output: "1234567890123456789"
    """
    match = re.search(r"/status/(\d+)", url)
    if match:
        return match.group(1)
    else:
        logging.warning(f"Could not parse tweet ID from URL: {url}")
        print(f"Could not parse tweet ID from URL: {url}")
        return None

def load_tweet_urls_from_links(file_path: Path) -> list:
    """
    Reads the bookmarks_links.txt file and extracts tweet URLs.
    Ensures that only valid tweet URLs are returned.
    """
    tweet_urls = []
    if not file_path.exists():
        logging.error(f"{file_path} does not exist.")
        print(f"{file_path} does not exist.")
        return tweet_urls

    with file_path.open('r', encoding='utf-8') as f:
        for line_number, line in enumerate(f, start=1):
            url = line.strip()
            if not url:
                continue
            tweet_id = parse_tweet_id_from_url(url)
            if tweet_id:
                tweet_urls.append(url)
            else:
                logging.warning(f"Line {line_number}: Invalid URL format.")
                print(f"Line {line_number}: Invalid URL format.")
    logging.info(f"Extracted {len(tweet_urls)} tweet URLs from {file_path}.")
    print(f"Extracted {len(tweet_urls)} tweet URLs from {file_path}.")
    return tweet_urls

# -----------------------------
# Fetching Tweet Data using Playwright (Async)
# -----------------------------

async def fetch_tweet_data_playwright(tweet_id: str) -> dict:
    """
    Fetches tweet text and media URLs using Playwright.
    Returns a dict with 'full_text' and 'extended_media' fields.
    """
    tweet_url = f"https://x.com/i/status/{tweet_id}"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(tweet_url, timeout=60000)  # 60 seconds timeout

            # Wait for the tweet content to load
            await page.wait_for_selector('article div[data-testid="tweetText"]', timeout=30000)

            # Extract tweet text
            tweet_text_elements = await page.query_selector_all('article div[data-testid="tweetText"]')
            tweet_text = " ".join([await el.inner_text() for el in tweet_text_elements])

            # Extract media URLs (images and videos)
            media_urls = []
            # Images
            image_elements = await page.query_selector_all('article div[data-testid="tweetPhoto"] img')
            for media in image_elements:
                src = await media.get_attribute('src')
                if src:
                    media_urls.append(src)
            # Videos
            video_elements = await page.query_selector_all('article div[data-testid="tweetVideo"] video')
            for media in video_elements:
                src = await media.get_attribute('src')
                if src:
                    media_urls.append(src)

            await browser.close()

        # Structure the result to match existing pipeline
        result_dict = {
            "full_text": tweet_text,
            "extended_media": [{"media_url_https": url} for url in media_urls]
        }

        logging.info(f"Fetched tweet ID {tweet_id}: '{tweet_text[:50]}...' with {len(media_urls)} media items.")
        print(f"Fetched tweet ID {tweet_id}: '{tweet_text[:50]}...' with {len(media_urls)} media items.")
        return result_dict

    except Exception as e:
        logging.error(f"Playwright failed for Tweet ID {tweet_id}: {e}")
        print(f"Playwright failed for Tweet ID {tweet_id}: {e}")
        return {}

# -----------------------------
# Image Interpretation using Ollama
# -----------------------------

def interpret_image(ollama_url: str, image_path: Path, vision_model: str) -> str:
    """
    Sends an image to the specified vision model for a concise description.
    Uses the /api/chat endpoint with a single user message containing base64 images.
    """
    try:
        with image_path.open("rb") as f:
            img_data = f.read()
        encoded_img = base64.b64encode(img_data).decode("utf-8")

        payload = {
            "model": vision_model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": "Provide a concise and accurate description of the image.",
                    "images": [encoded_img]
                }
            ]
        }

        resp = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        if 'message' in data and 'content' in data['message']:
            description = data['message']['content'].strip()
            logging.info(f"Image {image_path.name} interpreted: {description}")
            print(f"Image {image_path.name} interpreted: {description}")
            return description
        else:
            description = data.get("response", "").strip()
            logging.info(f"Image {image_path.name} interpreted: {description}")
            print(f"Image {image_path.name} interpreted: {description}")
            return description
    except requests.RequestException as e:
        logging.error(f"HTTP Error during image interpretation for {image_path.name}: {e}")
        print(f"HTTP Error during image interpretation for {image_path.name}: {e}")
        if 'resp' in locals():
            try:
                error_content = resp.content.decode('utf-8', errors='ignore')
                logging.error(f"Response Content: {error_content}")
                print(f"Response Content: {error_content}")
            except:
                logging.error("Unable to decode response content.")
                print("Unable to decode response content.")
        return "Error in processing image"

# -----------------------------
# Text Categorization and Naming using Ollama
# -----------------------------

async def categorize_and_name_content(ollama_url: str, combined_text: str, text_model: str, tweet_id: str, max_retries=3) -> tuple:
    """
    Enhanced categorization using CategoryManager and Ollama.
    """
    try:
        # Get initial category suggestions from CategoryManager
        suggestions = category_manager.get_category_suggestions(combined_text)
        
        # Create prompt with suggested categories
        suggested_cats = ", ".join([f"{cat}/{sub}" for cat, sub, _ in suggestions])
        
        prompt_text = (
            "You are an expert technical content curator specializing in software engineering, "
            "system design, and technical management.\n\n"
            
            f"Based on initial analysis, these categories were suggested: {suggested_cats}\n\n"
            
            "Task 1 - Choose or refine the categorization:\n"
            "- Confirm one of the suggested categories.\n"
            "- Or propose a more accurate category from our structure.\n"
            "- Do not use 'general' or 'other' as categories.\n"
            "- Keep category names short and specific.\n\n"
            
            "Task 2 - Create a specific technical title:\n"
            "- Make it clear and descriptive.\n"
            "- Focus on the key technical concept.\n"
            "- Use 2-5 words maximum.\n"
            "- Make it easily searchable.\n"
            "- Make it functionally specific.\n"
            "- Keep it concise.\n\n"
            
            "Response Format (exactly as shown):\n"
            "Category/Subcategory | Title\n\n"
            f"Content to Categorize:\n{combined_text}\n\n"
            "Response:"
        )

        # Try categorization with Ollama
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    f"{ollama_url}/api/generate",
                    json={"prompt": prompt_text, "model": text_model, "stream": False},
                    timeout=120
                )
                resp.raise_for_status()
                response = resp.json().get("response", "").strip()
                
                logging.debug(f"AI Response for Tweet ID {tweet_id}: {response}")
                
                main_category, sub_category, item_name = process_category_response(response, tweet_id)
                
                # Validate against category manager
                if main_category in category_manager.get_all_categories():
                    valid_subs = category_manager.get_subcategories(main_category)
                    if not valid_subs or sub_category in valid_subs:
                        return (main_category, sub_category, item_name)

            except Exception as e:
                logging.error(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        # If we reach here, use the highest scored suggestion from CategoryManager
        if suggestions:
            main_cat, sub_cat, _ = suggestions[0]
            timestamp = datetime.datetime.now().strftime("%Y%m%d")
            return (main_cat, sub_cat, f"tech_insight_{timestamp}_{tweet_id[:8]}")

        # Ultimate fallback
        return ("software_engineering", "best_practices", f"technical_note_{tweet_id}")

    except Exception as e:
        logging.error(f"Error in categorization: {e}")
        return ("software_engineering", "best_practices", f"technical_note_{tweet_id}")

# Additional helper function for cleaning text before categorization
def clean_text_for_categorization(text: str) -> str:
    """
    Clean and prepare text for categorization.
    """
    # Remove URLs
    text = re.sub(r'http\S+', '', text)
    # Remove special characters but keep spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    return text.lower()

# -----------------------------
# Processing State Management
# -----------------------------

def load_processed_tweets(file_path: Path) -> dict:
    """
    Loads the processed_tweets.json file.
    Returns a dictionary mapping tweet IDs to metadata.
    Validates each entry to ensure item_name is safe.
    Invalid entries are skipped.
    """
    if not file_path.exists():
        logging.info(f"{file_path} does not exist. Initializing empty processed tweets tracking.")
        print(f"{file_path} does not exist. Initializing empty processed tweets tracking.")
        return {}
    processed = {}
    try:
        with file_path.open('r', encoding='utf-8') as f:
            data = json.load(f)
            for tweet_id, entry in data.items():
                item_name = entry.get("item_name", "")
                main_category = entry.get("main_category", "")
                sub_category = entry.get("sub_category", "")
                if not (main_category and sub_category and item_name):
                    logging.warning(f"Tweet ID {tweet_id} has incomplete data. Skipping.")
                    print(f"Tweet ID {tweet_id} has incomplete data. Skipping.")
                    continue
                if not validate_directory_name(item_name):
                    logging.warning(f"Tweet ID {tweet_id} has invalid item_name '{item_name}'. Skipping.")
                    print(f"Tweet ID {tweet_id} has invalid item_name '{item_name}'. Skipping.")
                    continue
                processed[tweet_id] = entry
        logging.info(f"Loaded {len(processed)} processed tweets from {file_path}.")
        print(f"Loaded {len(processed)} processed tweets from {file_path}.")
    except Exception as e:
        logging.error(f"Failed to load {file_path}: {e}")
        print(f"Failed to load {file_path}: {e}")
    return processed

def save_processed_tweets(file_path: Path, processed_tweets: dict):
    """
    Saves the processed_tweets dictionary to the JSON file.
    """
    try:
        with file_path.open('w', encoding='utf-8') as f:
            json.dump(processed_tweets, f, indent=4)
        logging.info(f"Saved {len(processed_tweets)} processed tweets to {file_path}.")
        print(f"Saved {len(processed_tweets)} processed tweets to {file_path}.")
    except Exception as e:
        logging.error(f"Failed to save {file_path}: {e}")
        print(f"Failed to save {file_path}: {e}")

# -----------------------------
# New Addition: Delete Knowledge Base Item for a Tweet
# -----------------------------

def delete_knowledge_base_item(tweet_id: str, processed_tweets: dict):
    """
    Deletes the knowledge base item associated with the given tweet_id.
    """
    if tweet_id not in processed_tweets:
        return
    entry = processed_tweets[tweet_id]
    main_category = entry["main_category"]
    sub_category = entry["sub_category"]
    item_name = entry["item_name"]
    tweet_folder = KNOWLEDGE_BASE_DIR / main_category / sub_category / item_name

    # Log the item_name before attempting to delete
    logging.debug(f"Attempting to delete folder: {tweet_folder}")
    print(f"Attempting to delete folder: {tweet_folder}")

    if tweet_folder.exists() and tweet_folder.is_dir():
        try:
            shutil.rmtree(tweet_folder)
            logging.info(f"Deleted knowledge base item: {tweet_folder}")
            print(f"Deleted knowledge base item: {tweet_folder}")
        except Exception as e:
            logging.error(f"Failed to delete directory {tweet_folder}: {e}")
            print(f"Failed to delete directory {tweet_folder}: {e}")
    else:
        logging.warning(f"Knowledge base item {tweet_folder} does not exist or is not a directory.")
        print(f"Knowledge base item {tweet_folder} does not exist or is not a directory.")

# -----------------------------
# Tweet Processing Pipeline
# -----------------------------

async def process_tweet(tweet: dict, ollama_url: str, vision_model: str, text_model: str, tweet_id: str) -> dict:
    """
    Process a tweet to categorize, name, and prepare for storage.
    """
    tweet_text = tweet.get("full_text", "")
    extended_media = tweet.get("extended_media", [])
    image_descriptions = []
    image_files = []

    # Download & interpret each image
    for i, media_obj in enumerate(extended_media):
        image_url = media_obj.get("media_url_https")
        if not image_url:
            continue

        local_img_path = Path(f"temp_image_{i}.jpg")
        try:
            resp = requests.get(image_url, stream=True, timeout=60)
            resp.raise_for_status()
            with local_img_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info(f"Downloaded image {i+1}: {image_url}")
            print(f"Downloaded image {i+1}: {image_url}")

            # Interpret the image
            desc = interpret_image(ollama_url, local_img_path, vision_model)
            image_descriptions.append(desc)
            image_files.append(local_img_path)
        except requests.RequestException as e:
            logging.error(f"Error downloading image {image_url}: {e}")
            print(f"Error downloading image {image_url}: {e}")
        except Exception as e:
            logging.error(f"Error processing image {image_url}: {e}")
            print(f"Error processing image {image_url}: {e}")

    # Combine text + image descriptions for final categorization and naming
    combined_text = clean_text_for_categorization(tweet_text)
    if tweet_text:
        combined_text += f"\nTweet text: {tweet_text}\n\n"
    for idx, desc in enumerate(image_descriptions):
        combined_text += f"Image {idx+1} interpretation: {desc}\n\n"

    # Categorize and name the content (now with await)
    main_category, sub_category, item_name = await categorize_and_name_content(
        ollama_url, combined_text, text_model, tweet_id
    )

    return {
        "main_category": main_category,
        "sub_category": sub_category,
        "item_name": item_name,
        "tweet_text": tweet_text,
        "image_descriptions": image_descriptions,
        "image_files": image_files
    }

# -----------------------------
# Markdown Generation
# -----------------------------

def sanitize_markdown_cell(text: str) -> str:
    """
    Sanitize text to be safely included in a Markdown table cell.
    Escapes pipe characters and trims whitespace.
    """
    return text.replace('|', '&#124;').strip()

def format_links_in_text(text: str) -> str:
    """
    Finds URLs in the text and formats them as markdown links.
    """
    url_pattern = re.compile(r'(https?://\S+)')
    return url_pattern.sub(r'[\1](\1)', text)

def write_tweet_markdown(
    root_dir: Path,
    tweet_id: str,
    main_category: str,
    sub_category: str,
    item_name: str,
    tweet_text: str,
    image_files: list,
    image_descriptions: list,
    tweet_url: str
):
    """
    Writes a 'content.md' in knowledge-base/<main_category>/<sub_category>/<item_name>/,
    moves images into that folder, and references them in the markdown.
    """
    # Ensure item_name is safe for directory naming
    safe_item_name = safe_directory_name(item_name)
    if not safe_item_name:
        # This should not happen as item_name is validated, but added as a safeguard
        logging.warning(f"Generated item name '{item_name}' resulted in unsafe directory name. Using tweet ID as name.")
        safe_item_name = f"tweet_{tweet_id}"

    # Ensure uniqueness by appending a UUID if directory exists
    tweet_folder = root_dir / main_category / sub_category / safe_item_name
    if tweet_folder.exists():
        unique_suffix = uuid.uuid4().hex[:6]
        safe_item_name = f"{safe_item_name}_{unique_suffix}"
        tweet_folder = root_dir / main_category / sub_category / safe_item_name
        logging.warning(f"Directory already exists. New directory name: {safe_item_name}")
        print(f"Directory already exists. New directory name: {safe_item_name}")

    tweet_folder.mkdir(parents=True, exist_ok=True)

    # Format links in tweet text
    formatted_tweet_text = format_links_in_text(tweet_text)

    lines = [
        f"# {item_name}",
        "",
        f"**Tweet URL:** [{tweet_url}]({tweet_url})",
        "",
        f"**Tweet Text:** {formatted_tweet_text}",
        ""
    ]

    for i, desc in enumerate(image_descriptions):
        img_name = f"image_{i+1}.jpg"
        lines.append(f"**Image {i+1} Description:** {desc}")
        lines.append(f"![Image {i+1}](./{img_name})")
        lines.append("")

    # Write the content.md
    content_md_path = tweet_folder / "content.md"
    content_md_path.write_text("\n".join(lines), encoding="utf-8")
    logging.info(f"Written Markdown to {content_md_path}")
    print(f"Written Markdown to {content_md_path}")

    # Move images into that folder
    for i, img_path in enumerate(image_files):
        img_name = f"image_{i+1}.jpg"
        final_path = tweet_folder / img_name
        try:
            img_path.rename(final_path)
            logging.info(f"Moved image to {final_path}")
            print(f"Moved image to {final_path}")
        except Exception as e:
            logging.error(f"Error moving {img_path} to {final_path}: {e}")
            print(f"Error moving {img_path} to {final_path}: {e}")

    # Clean up temporary images
    for img_path in image_files:
        if img_path.exists():
            img_path.unlink()
            logging.info(f"Deleted temporary file: {img_path}")
            print(f"Deleted temporary file: {img_path}")

def generate_root_readme(root_dir: Path):
    """
    Generates an enhanced root-level README.md with better organization and navigation.
    """
    readme_path = root_dir / "README.md"
    
    # Collect all items first for statistics and quick navigation
    total_items = 0
    total_categories = 0
    total_subcategories = 0
    knowledge_tree = {}
    
    # First pass: collect statistics and build knowledge tree
    for main_category in sorted(root_dir.iterdir()):
        if not (main_category.is_dir() and not main_category.name.startswith(".")):
            continue
            
        total_categories += 1
        knowledge_tree[main_category.name] = {}
        
        for sub_category in sorted(main_category.iterdir()):
            if not (sub_category.is_dir() and not sub_category.name.startswith(".")):
                continue
                
            total_subcategories += 1
            items = [item for item in sorted(sub_category.iterdir()) 
                    if item.is_dir() and not item.name.startswith(".")]
            
            knowledge_tree[main_category.name][sub_category.name] = []
            
            for item in items:
                content_md = item / "content.md"
                if content_md.exists():
                    total_items += 1
                    with content_md.open('r', encoding='utf-8') as f:
                        content_lines = f.readlines()
                    
                    # Extract title and metadata
                    title = next((line[2:].strip() for line in content_lines 
                                if line.startswith("# ")), item.name)
                    
                    knowledge_tree[main_category.name][sub_category.name].append({
                        'title': title,
                        'path': content_md,
                        'item_dir': item
                    })
    
    # Generate README content
    lines = [
        "# Technical Knowledge Base",
        "",
        "## Overview",
        "",
        f"📚 **Total Knowledge Items:** {total_items}  ",
        f"📂 **Categories:** {total_categories}  ",
        f"📁 **Subcategories:** {total_subcategories}",
        "",
        "## Quick Navigation",
        "",
        "- [Knowledge Tree](#knowledge-tree)",
        "- [Detailed Contents](#detailed-contents)",
        "",
        "## Knowledge Tree",
        ""
    ]
    
    # Generate tree structure
    for main_cat, subcats in knowledge_tree.items():
        main_cat_display = main_cat.replace('_', ' ').title()
        lines.append(f"- 📂 **{main_cat_display}**")
        
        for sub_cat, items in subcats.items():
            sub_cat_display = sub_cat.replace('_', ' ').title()
            lines.append(f"  - 📁 {sub_cat_display}")
            
            for item in items:
                relative_path = item['path'].relative_to(root_dir).as_posix()
                lines.append(f"    - 📄 [{item['title']}](./{relative_path})")
                
        lines.append("")
    
    lines.extend([
        "## Detailed Contents",
        "",
        "_Each section below contains detailed descriptions and links to the knowledge base items._",
        ""
    ])
    
    # Generate detailed content
    for main_cat, subcats in knowledge_tree.items():
        main_cat_display = main_cat.replace('_', ' ').title()
        lines.append(f"### 📂 {main_cat_display}")
        lines.append("")
        
        # Add category description if available
        cat_info = category_manager.get_category_info(main_cat)
        if cat_info and cat_info.description:
            lines.append(f"_{cat_info.description}_")
            lines.append("")
        
        for sub_cat, items in subcats.items():
            if not items:
                continue
                
            sub_cat_display = sub_cat.replace('_', ' ').title()
            lines.append(f"#### 📁 {sub_cat_display}")
            lines.append("")
            
            # Initialize table
            lines.extend([
                "| Item | Description | Keywords |",
                "|------|-------------|----------|"
            ])
            
            for item in items:
                content_md = item['path']
                
                try:
                    with content_md.open('r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Extract description and keywords
                    tweet_text = re.search(r'\*\*Tweet Text:\*\* (.*?)(?:\n\n|\Z)', 
                                        content, re.DOTALL)
                    description = tweet_text.group(1) if tweet_text else "No description available."
                    
                    # Extract image descriptions
                    img_descriptions = re.findall(r'\*\*Image \d+ Description:\*\* (.*?)\n', 
                                               content)
                    
                    # Generate keywords using first image description
                    keywords = []
                    if img_descriptions:
                        keywords = [word.strip().lower() for word in img_descriptions[0].split()
                                  if len(word) > 3][:5]
                    
                    # Prepare table row
                    relative_path = content_md.relative_to(root_dir).as_posix()
                    title_link = f"[{item['title']}](./{relative_path})"
                    
                    # Truncate description if too long
                    desc_truncated = description[:100] + "..." if len(description) > 100 else description
                    desc_truncated = sanitize_markdown_cell(desc_truncated)
                    
                    # Format keywords
                    keyword_text = ", ".join(keywords) if keywords else "N/A"
                    
                    lines.append(f"| {title_link} | {desc_truncated} | {keyword_text} |")
                    
                except Exception as e:
                    logging.error(f"Error processing {content_md}: {e}")
                    lines.append(f"| {item['title']} | Error processing content | N/A |")
            
            lines.append("")  # Add empty line after table
    
    # Add footer
    lines.extend([
        "---",
        "",
        "Last updated: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "",
        "_This README is automatically generated by the Knowledge Base Agent._"
    ])
    
    # Write to README.md
    readme_content = "\n".join(lines)
    readme_path.write_text(readme_content, encoding="utf-8")
    logging.info(f"Generated enhanced root README.md at {readme_path}")
    print(f"Generated enhanced root README.md at {readme_path}")
    
    return total_items, total_categories, total_subcategories  # Return statistics for potential use

# -----------------------------
# Cleanup Function to Remove Existing 'untitled_*' Directories
# -----------------------------

def clean_untitled_directories(root_dir: Path):
    """
    Removes all directories starting with 'untitled_' within the knowledge-base.
    """
    for main_category in root_dir.iterdir():
        if main_category.is_dir() and not main_category.name.startswith("."):
            for sub_category in main_category.iterdir():
                if sub_category.is_dir() and not sub_category.name.startswith("."):
                    for item in sub_category.iterdir():
                        if item.is_dir() and item.name.startswith("untitled_"):
                            try:
                                shutil.rmtree(item)
                                logging.info(f"Removed unwanted directory: {item}")
                                print(f"Removed unwanted directory: {item}")
                            except Exception as e:
                                logging.error(f"Failed to remove directory {item}: {e}")
                                print(f"Failed to remove directory {item}: {e}")

# -----------------------------
# Main Execution (Asynchronous)
# -----------------------------

async def main_async():
    """Main execution function with improved error handling and logging."""
    try:
        # Load processed tweets with validation
        processed_tweets = load_processed_tweets(PROCESSED_TWEETS_FILE)

        # -----------------------------
        # New Addition: Prompt for Reprocessing
        # -----------------------------
        if processed_tweets:
            user_input = input(f"Found {len(processed_tweets)} previously processed tweets. Do you want to reprocess them? (y/n): ").strip().lower()
            if user_input == 'y':
                for tweet_id in list(processed_tweets.keys()):
                    delete_knowledge_base_item(tweet_id, processed_tweets)
                    # Remove tweet from processed_tweets to allow reprocessing
                    del processed_tweets[tweet_id]
                # Save the updated processed_tweets
                save_processed_tweets(PROCESSED_TWEETS_FILE, processed_tweets)
                print("Reprocessing enabled. Previously processed tweets will be processed again.")
            else:
                print("Skipping reprocessing of previously processed tweets.")

        # Clean up existing 'untitled_*' directories before processing
        clean_untitled_directories(KNOWLEDGE_BASE_DIR)

        # Load tweet URLs from bookmarks_links.txt
        tweet_urls = load_tweet_urls_from_links(BOOKMARKS_FILE)
        if not tweet_urls:
            logging.error("No valid tweet URLs found. Exiting.")
            print("No valid tweet URLs found. Exiting.")
            return

        logging.info(f"Starting processing of {len(tweet_urls)} tweets...\n")
        print(f"Starting processing of {len(tweet_urls)} tweets...\n")

        # Process each tweet
        for idx, tweet_url in enumerate(tweet_urls, start=1):
            tweet_id = parse_tweet_id_from_url(tweet_url)
            if not tweet_id:
                logging.warning(f"Skipping invalid tweet URL: {tweet_url}\n")
                print(f"Skipping invalid tweet URL: {tweet_url}\n")
                continue

            # Check if tweet has already been processed
            if tweet_id in processed_tweets:
                logging.info(f"Skipping already processed tweet ID {tweet_id}.")
                print(f"Skipping already processed tweet ID {tweet_id}.\n")
                continue

            logging.info(f"Processing tweet #{idx}: ID {tweet_id}")
            print(f"Processing tweet #{idx}: ID {tweet_id}")
            
            try:
                # Fetch tweet data using Playwright
                tweet_data = await fetch_tweet_data_playwright(tweet_id)
                if not tweet_data:
                    logging.warning(f"Skipping tweet ID {tweet_id} due to missing data.\n")
                    print(f"Skipping tweet ID {tweet_id} due to missing data.\n")
                    continue

                # Process the tweet (interpret images, categorize, generate item name)
                result = await process_tweet(tweet_data, OLLAMA_URL, VISION_MODEL, TEXT_MODEL, tweet_id)
                if not result:
                    logging.warning(f"Skipping tweet ID {tweet_id} due to processing failure.\n")
                    print(f"Skipping tweet ID {tweet_id} due to processing failure.\n")
                    continue

                main_category = result["main_category"]
                sub_category = result["sub_category"]
                item_name = result["item_name"]
                tweet_text = result["tweet_text"]
                image_descriptions = result["image_descriptions"]
                image_files = result["image_files"]

                # Write Markdown and organize images
                write_tweet_markdown(
                    root_dir=KNOWLEDGE_BASE_DIR,
                    tweet_id=tweet_id,
                    main_category=main_category,
                    sub_category=sub_category,
                    item_name=item_name,
                    tweet_text=tweet_text,
                    image_files=image_files,
                    image_descriptions=image_descriptions,
                    tweet_url=tweet_url
                )

                # Update processed_tweets dictionary
                processed_tweets[tweet_id] = {
                    "item_name": item_name,
                    "main_category": main_category,
                    "sub_category": sub_category,
                    "timestamp": datetime.datetime.now().isoformat()
                }

                logging.info(f"Successfully processed tweet #{idx} => Category: {main_category}/{sub_category}, Item Name: {item_name}\n")
                print(f"Successfully processed tweet #{idx} => Category: {main_category}/{sub_category}, Item Name: {item_name}\n")

                # Optional: Implement a short delay to prevent rate limiting
                await asyncio.sleep(2)  # Sleep for 2 seconds

            except Exception as e:
                logging.error(f"Unexpected error processing tweet ID {tweet_id}: {e}\n")
                print(f"Unexpected error processing tweet ID {tweet_id}: {e}\n")

        # Save the updated processed_tweets
        save_processed_tweets(PROCESSED_TWEETS_FILE, processed_tweets)

        logging.info("All tweets have been processed.")
        print("All tweets have been processed.")

        # Generate the root README.md before pushing to GitHub
        generate_root_readme(KNOWLEDGE_BASE_DIR)

        # After generating README.md, force push to GitHub
        if GITHUB_TOKEN:
            push_to_github(
                knowledge_base_dir=KNOWLEDGE_BASE_DIR,
                github_repo_url=GITHUB_REPO_URL,
                github_token=GITHUB_TOKEN,
                git_user_name=GITHUB_USER_NAME,
                git_user_email=GITHUB_USER_EMAIL
            )
        else:
            logging.warning("GitHub token not found. Skipping GitHub push.")
            print("GitHub token not found. Skipping GitHub push.")

    except Exception as e:
        logging.error(f"Main execution error: {e}")
        raise  # Re-raise the exception after logging

# Execute the main asynchronous function
if __name__ == "__main__":
    asyncio.run(main_async())
