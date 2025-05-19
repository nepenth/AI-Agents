from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import logging
from datetime import datetime
from knowledge_base_agent.exceptions import StorageError, ContentProcessingError, ContentGenerationError, KnowledgeBaseItemCreationError
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
from knowledge_base_agent.state_manager import StateManager
from knowledge_base_agent.types import KnowledgeBaseItem, CategoryInfo
from knowledge_base_agent.category_manager import CategoryManager
import copy
from mimetypes import guess_type
from knowledge_base_agent.media_processor import VIDEO_MIME_TYPES
import asyncio
import shutil
import json
from knowledge_base_agent.naming_utils import normalize_name_for_filesystem
from knowledge_base_agent.exceptions import AIError

def create_kb_content_generation_prompt(context_data: Dict[str, Any]) -> str:
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

    prompt = f"""
You are an expert technical writer tasked with creating a structured knowledge base article.
The source content is from a tweet (or a thread of tweets) and associated media/links.
The target audience is technical (software engineers, data scientists, IT professionals).

{source_content_md}
- Initial Topic/Keyword (for title inspiration): "{item_name_hint}"
- Category: {main_category} / {sub_category}
{media_context_md}{urls_context_md}
**Your Task:**
Generate a comprehensive, well-structured knowledge base article in JSON format.
The JSON object MUST conform to the following schema. Ensure all string values are plain text without any markdown.

```json
{{
  "suggested_title": "string (A polished, human-readable title for the article, inspired by '{item_name_hint}' but can be more descriptive. e.g., 'Understanding Asynchronous Execution in Python')",
  "meta_description": "string (1-2 sentence summary of the article, suitable for SEO or a brief preview. Max 160 characters.)",
  "introduction": "string (1-2 engaging paragraphs introducing the topic, its importance, and what the article will cover.)",
  "sections": [
    {{
      "heading": "string (Clear, concise heading for this section, e.g., 'Core Concepts of X', 'Setting up Y', 'Common Pitfalls')",
      "content_paragraphs": [
        "string (Detailed paragraph. Explain concepts clearly. Use technical terms accurately.)",
        "string (Another paragraph if needed for this section.)"
      ],
      "code_blocks": [
        {{
          "language": "string (e.g., python, javascript, bash, json, yaml, Dockerfile, plain_text)",
          "code": "string (The actual code snippet. Ensure it is correct and well-formatted.)",
          "explanation": "string (Optional: Brief explanation of what this code does or demonstrates.)"
        }}
      ],
      "lists": [
        {{
          "type": "bulleted | numbered",
          "items": [
            "string (List item 1)",
            "string (List item 2)"
          ]
        }}
      ],
      "notes_or_tips": [
        "string (A key note, tip, best practice, or warning related to this section.)"
      ]
    }}
  ],
  "key_takeaways": [
    "string (A concise key learning point or summary statement. Aim for 3-5 takeaways.)"
  ],
  "conclusion": "string (Concluding paragraph, summarizing the main points and perhaps suggesting further reading or next steps.)",
  "external_references": [
    {{"text": "string (Descriptive text for the link, e.g., 'Official Python Asyncio Docs')", "url": "string (The URL)"}}
  ]
}}
```

**Guidelines for Content Generation:**
- **Accuracy:** Ensure all technical information, code examples, and explanations are correct.
- **Clarity:** Write in clear, concise language. Define jargon if used.
- **Depth:** Go beyond surface-level explanations. Provide meaningful insights. Aim for 2-4 detailed sections.
- **Structure:** Organize content logically. Each section should have a clear purpose.
- **Completeness:** Populate all fields. Use empty lists `[]` for optional sub-fields if not applicable (e.g., `code_blocks: []`).
- **Title:** `suggested_title` must be a refined, descriptive title for the article.
- **Paragraphs:** `content_paragraphs` must be an array of strings.
- **Code:** If including code, specify the language. `plain_text` can be used for generic text blocks.
- **No Markdown in JSON Values:** All string values within the JSON MUST be plain text. Markdown formatting will be applied later.

Respond ONLY with a single, valid JSON object that strictly adheres to the schema. Do not include any other text, explanations, or apologies before or after the JSON.
"""
    return prompt.strip()


async def _generate_kb_content_json(
    tweet_id: str, # For logging (original bookmarked tweet ID)
    context_data: Dict[str, Any], 
    http_client: HTTPClient, 
    config: Config
) -> Dict[str, Any]:
    """Generates knowledge base content as a structured JSON object from tweet data."""
    prompt = create_kb_content_generation_prompt(context_data)
    
    current_model = config.text_model
    last_exception = None

    # Total attempts for primary model + fallback model
    total_attempts = config.content_retries * 2 

    for attempt in range(total_attempts):
        model_to_use = current_model
        is_primary_model_attempt = (model_to_use == config.text_model)
        attempt_num_for_model = (attempt % config.content_retries) + 1

        if not is_primary_model_attempt and attempt < config.content_retries: 
             pass # Should be on primary, logic error in original, corrected below
        elif is_primary_model_attempt and attempt >= config.content_retries and config.fallback_model and config.fallback_model != config.text_model:
            logging.info(f"Tweet {tweet_id}: Switching to fallback model {config.fallback_model} for KB content JSON generation after {config.content_retries} attempts with {config.text_model}.")
            current_model = config.fallback_model
            model_to_use = current_model # Ensure model_to_use is updated
            attempt_num_for_model = (attempt - config.content_retries) + 1
        # Corrected logic for model switching:
        # if attempt >= config.content_retries: # Time to switch to fallback if primary failed enough
        #     if config.fallback_model and config.fallback_model != config.text_model and current_model == config.text_model:
        #         logging.info(f"Tweet {tweet_id}: Switching to fallback model {config.fallback_model} for KB content JSON generation after {config.content_retries} attempts with {config.text_model}.")
        #         current_model = config.fallback_model
        #     model_to_use = current_model
        #     attempt_num_for_model = (attempt % config.content_retries) + 1 # Reset attempt count for this model
        # else:
        #     model_to_use = config.text_model
        #     attempt_num_for_model = attempt + 1


        logging.info(f"Tweet {tweet_id}: Attempt {attempt_num_for_model}/{config.content_retries} to generate KB content JSON using model {model_to_use}.")
        
        try:
            raw_response = await http_client.ollama_generate(
                model=model_to_use,
                prompt=prompt,
                temperature=0.2, 
                options={"json_mode": True} 
            )

            if not raw_response:
                logging.warning(f"Tweet {tweet_id}: Empty raw response from {model_to_use} (attempt {attempt_num_for_model}).")
                last_exception = ContentGenerationError("Generated content JSON is empty")
            else:
                try:
                    if raw_response.startswith("```json"):
                        raw_response = raw_response.split("```json")[1].split("```")[0].strip()
                    elif raw_response.startswith("```"):
                         raw_response = raw_response.split("```")[1].strip()
                    
                    content_json = json.loads(raw_response)
                    
                    if not isinstance(content_json, dict) or "suggested_title" not in content_json or "sections" not in content_json:
                        logging.warning(f"Tweet {tweet_id}: Invalid JSON structure from {model_to_use} (attempt {attempt_num_for_model}). Missing key fields. Response: {raw_response[:500]}")
                        last_exception = ContentGenerationError("Generated content JSON lacks required structure (e.g., missing title or sections).")
                    else:
                        logging.info(f"Tweet {tweet_id}: Successfully generated and parsed KB content JSON from {model_to_use} (attempt {attempt_num_for_model}).")
                        return content_json 
                        
                except json.JSONDecodeError as e:
                    logging.warning(f"Tweet {tweet_id}: Failed to decode JSON from {model_to_use} (attempt {attempt_num_for_model}): {e}. Response: {raw_response[:500]}")
                    last_exception = ContentGenerationError(f"Failed to decode JSON: {e}")
        
        except AIError as e: 
            logging.warning(f"Tweet {tweet_id}: AIError from {model_to_use} (attempt {attempt_num_for_model}): {e}")
            last_exception = e
        except Exception as e: 
            logging.error(f"Tweet {tweet_id}: Unexpected error during KB content JSON generation with {model_to_use} (attempt {attempt_num_for_model}): {e}", exc_info=True)
            last_exception = e

        is_last_overall_attempt = (attempt == total_attempts - 1)
        is_last_primary_no_effective_fallback = (
            is_primary_model_attempt and
            (attempt_num_for_model == config.content_retries) and
            (not config.fallback_model or config.fallback_model == config.text_model)
        )
        
        if is_last_overall_attempt or is_last_primary_no_effective_fallback:
            break 

        await asyncio.sleep(1.5 ** attempt_num_for_model) 

    err_msg = f"Tweet {tweet_id}: All {config.content_retries} attempts per model failed to generate valid KB content JSON."
    if last_exception:
        logging.error(f"{err_msg} Last error: {last_exception}")
        raise ContentGenerationError(err_msg) from last_exception
    else: 
        logging.error(err_msg + " No specific last exception recorded.")
        raise ContentGenerationError(err_msg)


def _convert_kb_json_to_markdown(kb_json: Dict[str, Any]) -> str:
    """Converts the structured JSON KB content to a Markdown string."""
    lines = []

    title = kb_json.get("suggested_title", "Knowledge Base Item")
    lines.append(f"# {title.strip()}")
    lines.append("")

    introduction = kb_json.get("introduction", "")
    if introduction:
        lines.append(f"## Introduction")
        lines.append(introduction.strip())
        lines.append("")

    for section in kb_json.get("sections", []):
        heading = section.get("heading", "Section")
        lines.append(f"## {heading.strip()}")
        lines.append("")

        for paragraph in section.get("content_paragraphs", []):
            lines.append(paragraph.strip())
            lines.append("")

        for code_block in section.get("code_blocks", []):
            lang = code_block.get("language", "plain_text")
            code = code_block.get("code", "")
            explanation = code_block.get("explanation", "")
            if explanation:
                lines.append(f"_{explanation.strip()}_") 
                lines.append("")
            lines.append(f"```{lang}\n{code.strip()}\n```")
            lines.append("")

        for list_data in section.get("lists", []):
            list_type = list_data.get("type", "bulleted")
            prefix = "-" if list_type == "bulleted" else "1."
            for item_text in list_data.get("items", []):
                lines.append(f"{prefix} {item_text.strip()}")
            lines.append("")
        
        for note in section.get("notes_or_tips", []):
            lines.append(f"> **Note/Tip:** {note.strip()}") 
            lines.append("")

    takeaways = kb_json.get("key_takeaways", [])
    if takeaways:
        lines.append("## Key Takeaways")
        lines.append("")
        for takeaway in takeaways:
            lines.append(f"- {takeaway.strip()}")
        lines.append("")

    conclusion = kb_json.get("conclusion", "")
    if conclusion:
        lines.append("## Conclusion")
        lines.append(conclusion.strip())
        lines.append("")

    references = kb_json.get("external_references", [])
    if references:
        lines.append("## External References")
        lines.append("")
        for ref in references:
            text = ref.get("text", ref.get("url", "Link"))
            url = ref.get("url", "#")
            lines.append(f"- [{text.strip()}]({url.strip()})")
        lines.append("")
        
    return "\n".join(lines)


async def create_knowledge_base_item(
    tweet_id: str, # This is the original bookmarked tweet_id, serves as the ID for the KB item
    tweet_data: Dict[str, Any], 
    config: Config, 
    http_client: HTTPClient, 
    state_manager: Optional[StateManager] = None 
) -> KnowledgeBaseItem:
    """Creates a KnowledgeBaseItem from tweet_data (which may represent a thread) using JSON-based content generation."""
    try:
        logging.debug(f"KB_ITEM_GEN: Entered for tweet_id: {tweet_id}")
        
        categories_processed = tweet_data.get('categories_processed', False)
        categories = tweet_data.get('categories', {})

        logging.debug(f"KB_ITEM_GEN ({tweet_id}): categories_processed='{categories_processed}', categories_data='{categories}'")

        if not categories_processed:
            error_msg = f"Categories not processed for tweet {tweet_id}. 'categories_processed' flag is '{categories_processed}'."
            logging.error(f"KB_ITEM_GEN ({tweet_id}): Validation failed (flag check). {error_msg}")
            raise KnowledgeBaseItemCreationError(error_msg)

        # Now, categories_processed is True. Check the 'categories' dictionary.
        required_keys = ['main_category', 'sub_category', 'item_name']
        # Check if all required keys exist AND have non-empty string values
        missing_or_empty_keys = [key for key in required_keys if not categories.get(key)]

        if not categories or missing_or_empty_keys: # Check if categories dict itself is empty, or if keys are missing/empty
            error_msg = (f"Categories data is incomplete or missing for tweet {tweet_id}. "
                         f"Processed: {categories_processed}, Categories Dict: {categories}, Missing/Empty Values for Keys: {missing_or_empty_keys}")
            logging.error(f"KB_ITEM_GEN ({tweet_id}): Validation failed (data check). {error_msg}")
            raise KnowledgeBaseItemCreationError(error_msg)
        
        # If we reach here, categories_processed is True and categories dict has the required keys with non-empty values.
        ai_generated_item_name = str(categories['item_name'])

        # --- Assemble context for LLM, handling single tweets vs. threads ---
        all_texts_for_llm = []
        all_media_for_llm_item_object = [] # For the final KBItem object
        all_media_descriptions_for_llm_prompt = []
        all_urls_for_llm_prompt = []
        
        # The `tweet_data` top-level `full_text`, `media`, `image_descriptions`, `urls` should now be lists if it's a thread,
        # or direct values if not. PlaywrightFetcher and TweetCacher were updated to reflect this.
        # For kb_item_generator, we expect tweet_data to contain `thread_data` if it's a thread.

        if tweet_data.get("is_thread", False) and "thread_data" in tweet_data:
            logging.info(f"Tweet {tweet_id} is a thread. Assembling content from {len(tweet_data['thread_data'])} segments.")
            for segment in tweet_data["thread_data"]:
                all_texts_for_llm.append(segment.get("full_text", ""))
                segment_media = segment.get("media", []) # This media list contains dicts with 'downloaded_path' and 'description'
                for media_item in segment_media:
                    if media_item.get("downloaded_path"):
                        all_media_for_llm_item_object.append(media_item["downloaded_path"])
                    if media_item.get("description"):
                        all_media_descriptions_for_llm_prompt.append(media_item["description"])
                all_urls_for_llm_prompt.extend(segment.get("urls", []))
        else: # Single tweet
            logging.info(f"Tweet {tweet_id} is a single tweet. Using top-level data.")
            all_texts_for_llm.append(tweet_data.get('full_text', ''))
            # For single tweet, try 'downloaded_media', then fallback to 'all_downloaded_media_for_thread'
            media_paths_to_use = tweet_data.get('downloaded_media')
            if not media_paths_to_use: # If downloaded_media is None or empty list
                media_paths_to_use = tweet_data.get('all_downloaded_media_for_thread', [])
            all_media_for_llm_item_object.extend(media_paths_to_use)
            
            all_media_descriptions_for_llm_prompt.extend(tweet_data.get('image_descriptions', []))
            all_urls_for_llm_prompt.extend(tweet_data.get('urls', []))

        # Deduplicate URLs and descriptions (order might change but not critical for prompt)
        all_urls_for_llm_prompt = sorted(list(set(all_urls_for_llm_prompt)))
        all_media_descriptions_for_llm_prompt = list(dict.fromkeys(all_media_descriptions_for_llm_prompt)) # Preserve order, unique

        context_for_llm = {
            'tweet_segments': all_texts_for_llm, # Use this new key for the prompt
            'all_urls': all_urls_for_llm_prompt,
            'all_media_descriptions': all_media_descriptions_for_llm_prompt,
            'main_category': categories['main_category'],
            'sub_category': categories['sub_category'],
            'item_name': ai_generated_item_name 
        }
        if not tweet_data.get("is_thread", False): # For single tweet, pass original tweet_text for prompt simplicity if preferred
             context_for_llm['tweet_text'] = tweet_data.get('full_text', '')


        kb_content_json = await _generate_kb_content_json(tweet_id, context_for_llm, http_client, config)
        markdown_content = _convert_kb_json_to_markdown(kb_content_json)
        display_title = kb_content_json.get("suggested_title", ai_generated_item_name).strip()
        if not display_title: display_title = ai_generated_item_name

        meta_description = kb_content_json.get("meta_description", "").strip()
        # Fallback for meta_description using the first text segment if it's a thread, or full_text if single
        primary_text_for_fallback_desc = all_texts_for_llm[0] if all_texts_for_llm else ""
        if not meta_description and primary_text_for_fallback_desc:
            meta_description = primary_text_for_fallback_desc[:160].strip() + "..." if len(primary_text_for_fallback_desc) > 160 else primary_text_for_fallback_desc.strip()
        
        category_info = CategoryInfo(
            main_category=str(categories['main_category']),
            sub_category=str(categories['sub_category']),
            item_name=ai_generated_item_name, 
            description=meta_description 
        )
        
        current_time = datetime.now()
        
        # Determine author and creation time from the first segment of the thread or the tweet itself
        source_author = tweet_data.get('author', '')
        source_created_at = tweet_data.get('created_at', current_time.isoformat())
        if tweet_data.get("is_thread", False) and tweet_data.get("thread_data"):
            first_segment = tweet_data["thread_data"][0]
            source_author = first_segment.get('author', source_author)
            source_created_at = first_segment.get('created_at', source_created_at)

        # Construct necessary paths before creating KnowledgeBaseItem
        # ai_generated_item_name is already filesystem-safe from categorization phase.
        # Categories main/sub should also be filesystem safe or normalized by CategoryManager if needed.
        # For this construction, we assume they are.
        relative_item_dir_path = Path("kb-generated") / str(categories['main_category']) / str(categories['sub_category']) / ai_generated_item_name
        kb_item_readme_path = relative_item_dir_path / "README.md"
        kb_item_path_rel_project_root_str = str(kb_item_readme_path)

        target_media_paths_relative_to_item_dir = []
        if all_media_for_llm_item_object: # This list contains full paths to cached media
            for i, cache_path_str in enumerate(all_media_for_llm_item_object):
                cache_path = Path(cache_path_str)
                # Use the original filename from the cache path for the target item's media directory.
                # markdown_writer.py will handle copying this file to "media/<target_filename>"
                target_filename = cache_path.name 
                target_media_paths_relative_to_item_dir.append(f"media/{target_filename}")
        
        kb_media_paths_rel_item_dir_json_str = json.dumps(target_media_paths_relative_to_item_dir)

        kb_item = KnowledgeBaseItem(
            display_title=display_title, 
            description=meta_description, 
            markdown_content=markdown_content,
            raw_json_content=json.dumps(kb_content_json, indent=2),
            category_info=category_info,
            source_tweet={ 
                'url': f"https://twitter.com/i/web/status/{tweet_id}",
                'author': source_author,
                'created_at': source_created_at
            },
            source_media_cache_paths=all_media_for_llm_item_object,
            kb_media_paths_rel_item_dir=kb_media_paths_rel_item_dir_json_str,
            kb_item_path_rel_project_root=kb_item_path_rel_project_root_str,
            image_descriptions=all_media_descriptions_for_llm_prompt,
            created_at=current_time,
            last_updated=current_time
        )
        
        logging.info(f"Successfully created KnowledgeBaseItem structure for tweet/thread {tweet_id} with title '{display_title}' (fs_name: '{ai_generated_item_name}')")
        return kb_item

    except KnowledgeBaseItemCreationError:
        raise
    except Exception as e:
        logging.error(f"Unexpected error creating knowledge base item for tweet {tweet_id}: {e}", exc_info=True)
        raise KnowledgeBaseItemCreationError(f"Failed to create knowledge base item for {tweet_id}: {str(e)}") from e

# Removed old functions
"""
Removed old functions:
- generate_content(tweet_data: Dict[str, Any], http_client: HTTPClient, text_model: str, fallback_model: str = "") -> str:
- async def create_knowledge_base_entry(...) -> None:
- def infer_basic_category(text: str) -> Tuple[str, str]:
"""