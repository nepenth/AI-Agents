from pathlib import Path
from typing import Callable, Any, Dict, List, Optional
import logging
from dataclasses import dataclass, field
import json
from knowledge_base_agent.config import Config

# Default User Preferences (can be overridden by UI)
# These guide the agent's operational choices during a run.
@dataclass
class UserPreferences:
    """
    Defines user preferences for an agent run, controlling which phases are executed
    and whether certain operations should be forced.
    """
    run_mode: str = "full_pipeline"  # Options: 'full_pipeline', 'fetch_only', 'git_sync_only'
    
    # Skip flags, primarily for 'full_pipeline' mode
    skip_fetch_bookmarks: bool = False  # If True, fetching new bookmarks is skipped.
    skip_process_content: bool = False # If True, processing of queued/selected content is skipped.
    skip_readme_generation: bool = True  # If True, README regeneration is skipped unless other conditions force it (e.g., new items and no skip flag). (Default True as README regen is not always desired)
    skip_git_push: bool = False         # If True, Git push is skipped. (Default False to enable pushing if git is configured)

    # Force flags
    force_recache_tweets: bool = False     # If True, forces re-downloading of tweet data during content processing.
    
    # Granular force flags for content processing phases
    force_reprocess_media: bool = False    # If True, forces re-analyzing media even if already processed
    force_reprocess_llm: bool = False      # If True, forces re-running LLM categorization & naming
    force_reprocess_kb_item: bool = False  # If True, forces regeneration of KB items
    
    # Legacy/combined flag - maintained for backward compatibility
    # When set to True, it will activate all the granular force flags above
    force_reprocess_content: bool = False  # If True, forces reprocessing all content phases

    def __post_init__(self):
        # Convert string 'on'/'off' (typically from HTML forms) to boolean for flag fields.
        # This ensures that values coming from web forms are correctly interpreted.
        
        # If the combined force_reprocess_content is True, set all granular force flags
        if self.force_reprocess_content:
            self.force_reprocess_media = True
            self.force_reprocess_llm = True
            self.force_reprocess_kb_item = True
        
        bool_flags = [
            'skip_fetch_bookmarks',
            'skip_process_content',
            'skip_readme_generation',
            'skip_git_push',
            'force_recache_tweets',
            'force_reprocess_content',
            'force_reprocess_media',
            'force_reprocess_llm', 
            'force_reprocess_kb_item'
        ]

        for flag_name in bool_flags:
            value = getattr(self, flag_name)
            if isinstance(value, str):
                # If the attribute is a string, convert 'on' (case-insensitive) to True,
                # and anything else (like 'off' or other strings) to False.
                setattr(self, flag_name, value.lower() == 'on')
            elif not isinstance(value, bool):
                # If it's not a string and not a bool (e.g., None or some other type),
                # coerce it to bool using Python's standard truthiness,
                # then ensure it's explicitly True/False. This handles cases where
                # the default value might be None and we want a clear boolean.
                # However, given the type hints, this path should ideally not be hit
                # if inputs conform to string or boolean.
                # For safety, we default to False if it's an unexpected type after initial coercion.
                setattr(self, flag_name, bool(value))

def check_knowledge_base_state(config) -> Dict[str, bool]:
    """Check the current state of the knowledge base."""
    state = {
        'has_kb_items': False,
        'has_readme': False,
        'has_processed_tweets': False,
        'has_cached_tweets': False
    }
    
    # Check for processed tweets in state file and its content
    if Path(config.processed_tweets_file).exists():
        try:
            with open(config.processed_tweets_file, 'r') as f:
                processed_tweets = json.load(f)
                state['has_processed_tweets'] = bool(processed_tweets)  # True only if there are actual tweets
        except (FileNotFoundError, json.JSONDecodeError):
            state['has_processed_tweets'] = False
    
    # Check for cached tweet data
    if list(config.media_cache_dir.glob("*.json")):
        state['has_cached_tweets'] = True
    
    # Check for README
    if (config.knowledge_base_dir / "README.md").exists():
        state['has_readme'] = True
    
    # Check for knowledge base items
    if list(config.knowledge_base_dir.glob("**/*.md")):
        state['has_kb_items'] = True
    
    return state

def prompt_for_preferences(config: Config) -> UserPreferences:
    """Prompt user for preferences."""
    prefs = UserPreferences()
    kb_state = check_knowledge_base_state(config)

    prefs.update_bookmarks = input("Fetch new bookmarks? (y/n): ").lower().startswith('y')
    
    # Prompt for processing queued content
    prefs.process_queued_content = input("Process all queued/unprocessed content? (y/n, default y): ").lower() not in ['n', 'no']

    # Only prompt for cache refresh if there is cached data
    if kb_state['has_cached_tweets']:
        prefs.force_recache_tweets = input("Force re-cache of all tweet data for unprocessed items? (y/n): ").lower().startswith('y')
    
    # README generation can be forced
    prefs.skip_readme_generation = input("Skip regeneration of all README files? (y/n): ").lower().startswith('y')

    # Git push preference
    if config.git_enabled:
        prefs.skip_git_push = input("Skip pushing changes to Git repository after processing? (y/n, default n): ").lower() not in ['n', 'no']
    else:
        prefs.skip_git_push = True # Ensure it's True if git is not enabled globally

    logging.info(f"User preferences set: {prefs}")
    return prefs 

def load_user_preferences(config: Optional[Config] = None) -> UserPreferences:
    """
    Loads default UserPreferences.
    
    Currently, this returns a new UserPreferences object with default values.
    It can be extended to load preferences from a file if needed, using the config.
    The `config` parameter is optional and not used in the current basic implementation
    but is included for future extensibility (e.g., loading from a path in config).
    """
    # logging.debug(f"Loading default UserPreferences. Config provided: {bool(config)}")
    return UserPreferences()

class LLMPrompts:
    @staticmethod
    def get_categorization_prompt_standard(context_content: str, formatted_existing_categories: str, is_thread: bool = False) -> str:
        source_type_indicator = "Tweet Thread Content" if is_thread else "Tweet Content"
        return (
            "You are an expert technical content curator and a seasoned software architect/principal engineer, "
            "specializing in software engineering, system design, and technical management. "
            "Your primary goal is to create a deeply technical and intuitively organized knowledge graph. "
            f"Your task is to categorize the following content ({source_type_indicator} and any associated media insights) "
            "and suggest a filename-compatible item name.\n\n"
            f"{source_type_indicator}:\n---\n{context_content}\n---\n\n"
            f"Existing Categories (use these as a guide or create specific new ones if necessary. Focus on depth and specificity):\n{formatted_existing_categories}\n\n"
            "Instructions:\n"
            "1. Main Category:\n"
            "   - Choose a HIGHLY SPECIFIC technical domain (e.g., \"backend_frameworks\", \"devops_automation\", \"cloud_architecture\", \"testing_patterns\").\n"
            "   - **CRITICAL: DO NOT use generic top-level terms like \"software_engineering\", \"programming\", \"devops\", \"cloud_computing\", \"web_development\", \"technology\", \"coding\", \"engineering\".** Strive for categories that reflect expert-level distinctions.\n"
            "   - The main category should represent the most specific technical area that is relevant, not a broad discipline.\n"
            "   - Example: Use \"concurrency_models\" instead of \"software_engineering\"; use \"api_design_patterns\" instead of \"programming\"; use \"kubernetes_networking\" instead of \"cloud_computing\".\n"
            "2. Sub Category:\n"
            "   - Specify an even more precise technical area (e.g., \"thread_safety_mechanisms\", \"circuit_breaker_implementation_strategies\", \"terraform_advanced_modules\").\n"
            "   - **CRITICAL: Sub-categories must be highly specific and technical. Never use generic terms.**\n"
            "3. Item Name:\n"
            "   - Create a concise, descriptive, filesystem-friendly title (3-7 words, e.g., \"java_atomiclong_vs_synchronized\", \"resilience4j_circuitbreaker_config\", \"terraform_eks_cluster_provisioning\").\n"
            "   - Format: lowercase with underscores, no special characters other than underscore.\n"
            "   - Avoid generic terms like \"guide\", \"overview\", \"notes\", \"details\", \"insights\". Focus on keywords that highlight the core technical concept.\n\n"
            "**Response Format (MUST be a valid JSON object, on a single line if possible, or pretty-printed):**\n"
            "```json\n"
            "{\n"
            "  \"main_category\": \"example_specific_main_category\",\n"
            "  \"sub_category\": \"example_highly_specific_sub_category\",\n"
            "  \"item_name\": \"example_descriptive_technical_item_name\"\n"
            "}\n"
            "```\n\n"
            "Examples of good JSON responses:\n"
            "```json\n"
            "{\n"
            "  \"main_category\": \"concurrency_patterns\",\n"
            "  \"sub_category\": \"thread_synchronization_java\",\n"
            "  \"item_name\": \"java_util_concurrent_locks_deep_dive\"\n"
            "}\n"
            "```\n"
            "```json\n"
            "{\n"
            "  \"main_category\": \"ci_cd_security\",\n"
            "  \"sub_category\": \"github_actions_secret_management\",\n"
            "  \"item_name\": \"oidc_auth_for_secure_cloud_access\"\n"
            "}\n"
            "```\n"
            "```json\n"
            "{\n"
            "  \"main_category\": \"database_internals\",\n"
            "  \"sub_category\": \"postgresql_mvcc_vacuum_process\",\n"
            "  \"item_name\": \"optimizing_vacuum_for_high_write_workloads\"\n"
            "}\n"
            "```\n"
            "Respond ONLY with the JSON object."
        )
    
    @staticmethod
    def get_kb_item_generation_prompt_standard(context_data: Dict[str, Any]) -> str:
        tweet_segments = context_data.get('tweet_segments', [])
        single_tweet_text = context_data.get('tweet_text', '')

        main_category = context_data.get('main_category', 'N/A')
        sub_category = context_data.get('sub_category', 'N/A')
        item_name_hint = context_data.get('item_name', 'N/A')
        
        all_urls = context_data.get('all_urls', [])
        all_media_descriptions = context_data.get('all_media_descriptions', [])

        source_content_md = ""
        if tweet_segments:
            source_content_md += "**Source Information (Tweet Thread):**\\n"
            for i, segment_text in enumerate(tweet_segments):
                source_content_md += f"- Segment {i+1}: \"{segment_text}\"\\n"
            source_content_md += "\\n"
        elif single_tweet_text:
            source_content_md += "**Source Information (Single Tweet):**\\n"
            source_content_md += f"- Tweet Text: \"{single_tweet_text}\"\\n\\n"

        media_context_md = ""
        if all_media_descriptions:
            media_context_md += "Associated Media Insights (derived from all images/videos in the thread/tweet):\\n"
            for i, desc in enumerate(all_media_descriptions):
                media_context_md += f"- Media {i+1}: {desc}\\n"
            media_context_md += "\\n"

        urls_context_md = ""
        if all_urls:
            urls_context_md += "Mentioned URLs (from all segments in the thread/tweet, for context, not necessarily for inclusion as external_references unless very specific and high-value):\\n"
            for url in all_urls:
                urls_context_md += f"- {url}\\n"
            urls_context_md += "\\n"

        return f"""
Your are an expert technical writer and a seasoned software architect/principal engineer, tasked with creating a structured knowledge base article.
Your primary goal is to create a deeply technical and intuitively organized knowledge graph for an expert audience.
The source content is from a tweet (or a thread of tweets) and associated media/links.
The target audience is technical (software engineers, data scientists, IT professionals).

{source_content_md}
- Category: {main_category} / {sub_category}
- Initial Topic/Keyword (for title inspiration): "{item_name_hint}"
{media_context_md}{urls_context_md}

**Your Task:**
Generate a comprehensive, domain-specific knowledge base article in JSON format.
Focus on creating content that's rich in technical details and best practices for the specific domain of {main_category}/{sub_category}.

Remember that this article will be part of a professional knowledge base that serves as a reference for experts in the field.
Extract meaningful techniques, patterns, or insights that would be valuable to practitioners in this domain.

The JSON object MUST conform to the following schema. Ensure all string values are plain text without any markdown.
**CRITICAL: For all fields defined as `string` below, provide a single string value. Do NOT provide a list of strings or an array unless the type is explicitly `array` (e.g., `content_paragraphs`, `code_blocks`, `lists`, `notes_or_tips`, `key_takeaways`, `external_references`).**

```json
{{
  "suggested_title": "string (A precise, domain-specific title that clearly indicates what knowledge the article contains, e.g., 'Advanced React Hooks: Deep Dive into useCallback')",
  "meta_description": "string (A concise, information-rich summary that captures the key knowledge presented. Max 160 characters.)",
  "introduction": "string (1-2 paragraphs establishing context, importance, and outlining the key points to be covered. Focus on the specific knowledge value. This must be a single string, potentially with newline characters \\n for paragraphs.)",
  "sections": [
    {{
      "heading": "string (Clear, descriptive section heading related to a specific aspect of the topic)",
      "content_paragraphs": [
        "string (Detailed technical explanation with concrete examples and context. Focus on one clear point per paragraph. Each element in this array is a single string.)"
      ],
      "code_blocks": [
        {{
          "language": "string (e.g., python, javascript, bash, json, yaml, Dockerfile, plain_text)",
          "code": "string (Clean, well-formatted code snippet that demonstrates a specific concept or technique. This must be a single string, potentially with newline characters \\n for multiple lines of code.)",
          "explanation": "string (Optional: Brief explanation of what this code demonstrates or how it works. This must be a single string.)"
        }}
      ],
      "lists": [
        {{
          "type": "bulleted | numbered",
          "items": [
            "string (Concise list item with clear, actionable information. Each element in this array is a single string.)"
          ]
        }}
      ],
      "notes_or_tips": [
        "string (A key insight, warning, or best practice related to this section. Each element in this array is a single string.)"
      ]
    }}
  ],
  "key_takeaways": [
    "string (A precise, actionable learning point that readers should remember. Make these substantive and specific. Each element in this array is a single string.)"
  ],
  "conclusion": "string (Summarize the key points and reinforce the practical applications of this knowledge. This must be a single string, potentially with newline characters \\n for paragraphs.)",
  "external_references": [
    {{"text": "string (Descriptive text for a highly relevant reference, e.g., 'Official React useCallback Documentation')", "url": "string (The complete URL)"}}
  ]
}}
```

**Guidelines for Domain-Specific Content (for {main_category}/{sub_category}):**
- **Depth over Breadth**: Provide substantial depth on specific techniques rather than shallow overviews.
- **Technical Precision**: Use accurate terminology and explain concepts with technical rigor.
- **Practical Focus**: Include realistic scenarios where this knowledge would be applied. For instance, if discussing database indexing, explain how it applies to query optimization in high-traffic applications.
- **Pattern Recognition**: Identify patterns, principles, or best practices that extend beyond basic usage. For example, when discussing API design, highlight patterns like idempotency or statelessness.
- **Context and Rationale**: Explain not just what to do but why it matters and the reasoning behind recommendations. What are the trade-offs? Under what conditions is a particular approach optimal?
- **Completeness**: Aim for a comprehensive treatment that would satisfy an expert seeking to deepen their knowledge. Assume your reader is intelligent and technically proficient.
- **Organization**: Structure information in a logical progression that builds understanding.

For {main_category}/{sub_category} content specifically:
- Incorporate established best practices and patterns specific to this domain.
- Reference appropriate design patterns, architectural approaches, or methodologies when relevant (e.g., if it's about distributed systems, mention CAP theorem implications or specific consensus algorithms if pertinent).
- Include concrete examples that illustrate practical application in real-world scenarios.
- Address common pitfalls or misconceptions in this specific area. What do junior engineers often get wrong? What are advanced considerations?

Respond ONLY with a single, valid JSON object that strictly adheres to the schema. Do not include any other text, explanations, or apologies before or after the JSON.
""".strip()

    @staticmethod
    def get_readme_introduction_prompt_standard(kb_stats: Dict[str, int], category_list: str) -> str:
        """Generate a README introduction prompt for standard models"""
        return (
            f"Generate an engaging introduction paragraph for a technical knowledge base README.md file.\n\n"
            f"Knowledge Base Statistics:\n"
            f"- Total Items: {kb_stats.get('total_items', 0)}\n"
            f"- Main Categories: {kb_stats.get('total_main_cats', 0)}\n"
            f"- Subcategories: {kb_stats.get('total_subcats', 0)}\n"
            f"- Media Files: {kb_stats.get('total_media', 0)}\n\n"
            f"Categories include: {category_list}\n\n"
            "The introduction should be engaging, concise, and highlight the value of the knowledge base for technical professionals. "
            "Explain what makes this collection valuable, how it's organized, and how users can benefit from it. "
            "Write in markdown format, and keep it to 3-5 sentences. Adopt the persona of a helpful technical guide."
        )

    @staticmethod
    def get_readme_category_description_prompt_standard(main_display: str, total_cat_items: int, active_subcats: List[str]) -> str:
        """Generate a README category description prompt for standard models"""
        return f"""Write a brief 1-2 sentence description for the '{main_display}' category in a technical knowledge base.
This category contains {total_cat_items} items across {len(active_subcats)} subcategories: {', '.join(sub.replace('_', ' ').title() for sub in active_subcats)}.
Keep it concise and informative. Focus on the type of technical knowledge or domain this category covers."""

class ReasoningPrompts:
    """
    Defines prompts specifically for models that support reasoning like Cogito.
    These prompts use the messages format for chat models with a system message
    that enables the thinking/reasoning capabilities.
    """
    
    @staticmethod
    def get_system_message() -> Dict[str, str]:
        """Returns the standard system message for reasoning models"""
        return {
            "role": "system",
            "content": "Enable deep thinking subroutine. Analyze problems step-by-step. Consider multiple angles and approaches before providing your final answer. Adopt the persona of a highly experienced principal software engineer and technical architect. Your goal is to create a deeply technical and intuitively organized knowledge graph."
        }
    
    @staticmethod
    def get_categorization_prompt(context_content: str, formatted_existing_categories: str, is_thread: bool = False) -> Dict[str, str]:
        """Generate a categorization prompt for reasoning models"""
        source_type_indicator = "Tweet Thread Content" if is_thread else "Tweet Content"
        
        return {
            "role": "user",
            "content": (
                f"As an expert technical content curator and seasoned software architect/principal engineer, your task is to categorize the following content ({source_type_indicator} and any associated media insights) "
                f"and suggest a filename-compatible item name. Your primary goal is to create a deeply technical and intuitively organized knowledge graph.\n\n"
                f"{source_type_indicator}:\n---\n{context_content}\n---\n\n"
                f"Existing Categories (use these as a guide or create specific new ones if necessary. Focus on depth and specificity for a technical audience):\n{formatted_existing_categories}\n\n"
                "Instructions:\n"
                "1. Main Category:\n"
                "   - Choose a HIGHLY SPECIFIC technical domain (e.g., \"backend_frameworks\", \"devops_automation\", \"cloud_architecture\", \"testing_patterns\").\n"
                "   - **CRITICAL: DO NOT use generic top-level terms like \"software_engineering\", \"programming\", \"devops\", \"cloud_computing\", \"web_development\", \"technology\", \"coding\", \"engineering\".** Strive for categories that reflect expert-level distinctions.\n"
                "   - The main category should represent the most specific technical area that is relevant, not a broad discipline.\n"
                "   - Example: Use \"concurrency_models\" instead of \"software_engineering\"; use \"api_design_patterns\" instead of \"programming\"; use \"kubernetes_networking\" instead of \"cloud_computing\".\n"
                "2. Sub Category:\n"
                "   - Specify an even more precise technical area (e.g., \"thread_safety_mechanisms\", \"circuit_breaker_implementation_strategies\", \"terraform_advanced_modules\").\n"
                "   - **CRITICAL: Sub-categories must be highly specific and technical. Never use generic terms.**\n"
                "3. Item Name:\n"
                "   - Create a concise, descriptive, filesystem-friendly title (3-7 words, e.g., \"java_atomiclong_vs_synchronized\", \"resilience4j_circuitbreaker_config\", \"terraform_eks_cluster_provisioning\").\n"
                "   - Format: lowercase with underscores, no special characters other than underscore.\n"
                "   - Avoid generic terms like \"guide\", \"overview\", \"notes\", \"details\", \"insights\". Focus on keywords that highlight the core technical concept.\n\n"
                "**Response Format (MUST be a valid JSON object, on a single line if possible, or pretty-printed):**\n"
                "```json\n"
                "{\n"
                "  \"main_category\": \"example_specific_main_category\",\n"
                "  \"sub_category\": \"example_highly_specific_sub_category\",\n"
                "  \"item_name\": \"example_descriptive_technical_item_name\"\n"
                "}\n"
                "```\n"
                "Think step-by-step. First understand the topic deeply, then brainstorm possible categories, then narrow down to the most specific and appropriate choices. Ensure the categories are suitable for an expert technical audience."
            )
        }
    
    @staticmethod
    def get_kb_item_generation_prompt(tweet_text: str, categories: Dict[str, str], media_descriptions: List[str] = None) -> Dict[str, str]:
        """Generate a knowledge base item generation prompt for reasoning models"""
        media_desc_text = ""
        if media_descriptions and len(media_descriptions) > 0:
            media_desc_text = "\n\nMedia Descriptions:\n" + "\n".join([f"- {desc}" for desc in media_descriptions])
        
        return {
            "role": "user",
            "content": (
                f"Create a structured knowledge base item for the following content. The content will be categorized under "
                f"'{categories['main_category']}/{categories['sub_category']}' with the item name '{categories['item_name']}'.\n\n"
                f"Content to process:\n---\n{tweet_text}{media_desc_text}\n---\n\n"
                "As a principal software engineer and technical architect, generate a well-structured, comprehensive knowledge base item in JSON format. "
                "Your goal is to produce expert-level content for a technical audience. The JSON must include these attributes:\n\n"
                "**CRITICAL INSTRUCTION FOR JSON STRUCTURE:** For all attributes listed below, if the description implies a single piece of text (like a title, a paragraph, a code snippet itself, an explanation, a list item), you **MUST** provide a single string value. Do **NOT** use an array or list of strings for such fields unless the attribute name or its description explicitly states it's an 'array' (e.g., `sections`, `content_paragraphs` (which is an array *of strings*), `code_blocks` (as a list of block objects), `lists` (as a list of list objects), `notes_or_tips` (as an array *of strings*), `key_takeaways` (as an array *of strings*), `external_references` (as a list of objects)). Pay close attention to the expected type for each field.\n\n"
                "- suggested_title: string (A precise, domain-specific title that clearly indicates what knowledge the article contains, e.g., 'Advanced React Hooks: Deep Dive into useCallback')."
                "- meta_description: string (A concise, information-rich summary capturing the key knowledge (max 160 chars).)"
                "- introduction: string (1-2 paragraphs establishing context, importance, and outlining key points. Focus on specific knowledge value. This must be a single string, potentially with newline characters \\n for paragraphs.)"
                "- sections: An array of sections, each with:\n"
                "  - heading: string (Clear, descriptive section heading, e.g., 'Optimizing PostgreSQL Write Performance'. This must be a single string.)"
                "  - content_paragraphs: Array of strings. (Detailed technical explanation with concrete examples and context. Focus on one clear point per paragraph. Each element in this array is a single string.)\n"
                "  - code_blocks: Array of objects (optional). Each with 'language' (string), 'code' (string - This must be a single string, potentially with newline characters \\n for multiple lines of code.), 'explanation' (string - Optional. Brief explanation of what this code demonstrates or how it works. This must be a single string.)\n"
                "  - lists: Array of objects (optional). Each with 'type' (string - 'bulleted' or 'numbered') and 'items' (Array of strings - for concise, actionable info. Each element in this array is a single string.)\n"
                "  - notes_or_tips: Array of strings (optional). (Key insights, warnings, or best practices. Each element in this array is a single string.)"
                "- key_takeaways: Array of strings. (Precise, actionable learning points that are substantive and specific (3-5 bullets). Each element in this array is a single string.)"
                "- conclusion: string (Summarize key points and reinforce practical applications. This must be a single string, potentially with newline characters \\n for paragraphs.)"
                "- external_references: Array of objects (optional). Each with 'text' (string) and 'url' (string) for highly relevant, authoritative sources."
                "\n"
                "The content should be comprehensive, technically accurate, and follow best practices for technical writing. "
                "Think step-by-step about what would make this knowledge useful to a software engineer or technical professional. Strive for depth and expert insights."
            )
        }
    
    @staticmethod
    def get_readme_generation_prompt(kb_stats: Dict[str, int], category_list: str) -> Dict[str, str]:
        """Generate a README introduction prompt for reasoning models"""
        return {
            "role": "user",
            "content": (
                f"Generate an engaging introduction paragraph for a technical knowledge base README.md file.\n\n"
                f"Knowledge Base Statistics:\n"
                f"- Total Items: {kb_stats.get('total_items', 0)}\n"
                f"- Main Categories: {kb_stats.get('total_main_cats', 0)}\n"
                f"- Subcategories: {kb_stats.get('total_subcats', 0)}\n"
                f"- Media Files: {kb_stats.get('total_media', 0)}\n\n"
                f"Categories include: {category_list}\n\n"
                "The introduction should be engaging, concise, and highlight the value of the knowledge base for technical professionals. "
                "Explain what makes this collection valuable, how it's organized, and how users can benefit from it. "
                "Write in markdown format, and keep it to 3-5 sentences. "
                "Think step-by-step about what would make this knowledge base appealing to technical users. Adopt the persona of an expert technical guide and knowledge architect."
            )
        }

    @staticmethod
    def get_readme_category_description_prompt(main_display: str, total_cat_items: int, active_subcats: List[str]) -> Dict[str, str]:
        """Generate a README category description prompt for reasoning models"""
        return {
            "role": "user",
            "content": f"Write a brief 1-2 sentence description for the '{main_display}' category in a technical knowledge base. "
                       f"This category contains {total_cat_items} items across {len(active_subcats)} subcategories: "
                       f"{', '.join(sub.replace('_', ' ').title() for sub in active_subcats)}. "
                       f"Think about what unifies these subcategories and what value they provide to technical users. "
                       f"Keep your description concise, informative, and under 160 characters. Focus on the specific technical domain or area of expertise this category represents."
        } 