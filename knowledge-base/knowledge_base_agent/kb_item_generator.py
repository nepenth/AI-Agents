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
import re # Import re for the new extraction function
from knowledge_base_agent.prompts import LLMPrompts, ReasoningPrompts # Added import

def _extract_json_from_text(text: str) -> Optional[str]:
    """
    Extracts a JSON string from a larger text block.
    Handles markdown code blocks and searches for the outermost curly braces.
    """
    if not text:
        return None

    # Attempt 1: Markdown code block (json)
    match_json_block = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match_json_block:
        try:
            json_str = match_json_block.group(1)
            json.loads(json_str) # Validate
            return json_str
        except json.JSONDecodeError:
            pass # Continue to next method

    # Attempt 2: Markdown code block (any language or no language)
    match_any_block = re.search(r"```\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match_any_block:
        try:
            json_str = match_any_block.group(1)
            json.loads(json_str) # Validate
            return json_str
        except json.JSONDecodeError:
            pass # Continue to next method

    # Attempt 3: Find the first '{' and last '}'
    try:
        start_index = text.find('{')
        end_index = text.rfind('}')
        if start_index != -1 and end_index != -1 and end_index > start_index:
            potential_json = text[start_index : end_index + 1]
            json.loads(potential_json) # Validate
            return potential_json
    except json.JSONDecodeError:
        pass # Not a valid JSON object

    return None


def _ensure_string_from_value(value: Any) -> str:
    """
    Ensures the value is a string. If it's a list, joins its elements.
    Strips whitespace from the final string. Handles None by returning empty string.
    """
    if isinstance(value, list):
        # Join list elements, ensuring each is a string, separated by double newlines for paragraphs
        return "\n\n".join(str(item).strip() for item in value if item is not None).strip()
    elif value is None:
        return ""
    return str(value).strip()


async def _generate_kb_content_json(
    tweet_id: str, # For logging (original bookmarked tweet ID)
    context_data: Dict[str, Any], 
    http_client: HTTPClient, 
    config: Config
) -> Dict[str, Any]:
    """Generates knowledge base content as a structured JSON object from tweet data."""
    # Use the centralized prompt for the standard path
    prompt = LLMPrompts.get_kb_item_generation_prompt_standard(context_data)
    
    # Check if the model supports reasoning mode
    use_reasoning = hasattr(config, 'text_model_thinking') and config.text_model_thinking
    
    if use_reasoning:
        logging.info(f"Tweet {tweet_id}: Using reasoning mode for KB content generation")
        
        # Create the messages list with system message and user prompt
        # Extract texts for reasoning format
        tweet_text = context_data.get('tweet_text', '')
        if not tweet_text and 'tweet_segments' in context_data:
            tweet_text = '\n\n'.join(context_data.get('tweet_segments', []))
        
        categories = {
            'main_category': context_data.get('main_category', ''),
            'sub_category': context_data.get('sub_category', ''),
            'item_name': context_data.get('item_name', '')
        }
        
        media_descriptions = context_data.get('all_media_descriptions', [])
        
        messages = [
            ReasoningPrompts.get_system_message(),
            ReasoningPrompts.get_kb_item_generation_prompt(tweet_text, categories, media_descriptions)
        ]
        
        current_model = config.text_model
        last_exception = None
        total_attempts = config.content_retries * 2
        
        for attempt in range(total_attempts):
            model_to_use = current_model
            is_primary_model_attempt = (model_to_use == config.text_model)
            attempt_num_for_model = (attempt % config.content_retries) + 1

            # Logic for switching to fallback model if needed
            if is_primary_model_attempt and attempt >= config.content_retries and config.fallback_model and config.fallback_model != config.text_model:
                logging.info(f"Tweet {tweet_id}: Switching to fallback model {config.fallback_model} for KB content JSON generation after {config.content_retries} attempts with {config.text_model}.")
                current_model = config.fallback_model
                model_to_use = current_model
                attempt_num_for_model = (attempt - config.content_retries) + 1

            logging.info(f"Tweet {tweet_id}: Attempt {attempt_num_for_model}/{config.content_retries} to generate KB content JSON using reasoning mode with model {model_to_use}.")
            
            try:
                raw_response_text = await http_client.ollama_chat(
                    model=model_to_use,
                    messages=messages,
                    temperature=0.2,
                    timeout=config.content_generation_timeout # Using the configured timeout
                )

                if not raw_response_text:
                    logging.warning(f"Tweet {tweet_id}: Empty raw response from {model_to_use} (attempt {attempt_num_for_model}).")
                    last_exception = ContentGenerationError("Generated content JSON is empty")
                    
                    # Add a correction message for the next attempt
                    if attempt < total_attempts - 1:
                        messages.append({
                            "role": "user", 
                            "content": "Your previous response was empty. Please generate a valid JSON response with the required structure."
                        })
                else:
                    # Use the new extraction function
                    json_str_from_response = _extract_json_from_text(raw_response_text)
                    if json_str_from_response:
                        try:
                            content_json = json.loads(json_str_from_response)
                            if not isinstance(content_json, dict) or "suggested_title" not in content_json or "sections" not in content_json:
                                logging.warning(f"Tweet {tweet_id}: Invalid JSON structure from {model_to_use} (attempt {attempt_num_for_model}). Missing key fields. Extracted JSON: {json_str_from_response[:500]}")
                                last_exception = ContentGenerationError("Generated content JSON lacks required structure (e.g., missing title or sections).")
                                if attempt < total_attempts - 1:
                                    messages.append({
                                        "role": "user", 
                                        "content": "Your JSON response is missing required fields. Please ensure your response includes 'suggested_title' and 'sections' fields."
                                    })
                            else:
                                logging.info(f"Tweet {tweet_id}: Successfully generated and parsed KB content JSON from {model_to_use} (attempt {attempt_num_for_model}) using reasoning mode.")
                                return content_json
                        except json.JSONDecodeError as e:
                            logging.warning(f"Tweet {tweet_id}: Failed to decode extracted JSON from {model_to_use} (attempt {attempt_num_for_model}): {e}. Extracted JSON: {json_str_from_response[:500]}")
                            last_exception = ContentGenerationError(f"Failed to decode extracted JSON: {e}")
                            if attempt < total_attempts - 1:
                                messages.append({
                                    "role": "user", 
                                    "content": f"Your response contained JSON that could not be parsed. Error: {e}. Please ensure you provide a valid JSON object."
                                })
                    else: # No JSON found by _extract_json_from_text
                        logging.warning(f"Tweet {tweet_id}: Could not extract valid JSON from {model_to_use} response (attempt {attempt_num_for_model}). Response: {raw_response_text[:500]}")
                        last_exception = ContentGenerationError("No valid JSON found in model response.")
                        if attempt < total_attempts - 1:
                            messages.append({
                                "role": "user",
                                "content": "Your response did not appear to contain a valid JSON object. Please ensure your entire response is, or contains, a single valid JSON object."
                            })
            
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
        
        err_msg = f"Tweet {tweet_id}: All {config.content_retries} attempts per model failed to generate valid KB content JSON using reasoning mode."
        if last_exception:
            logging.error(f"{err_msg} Last error: {last_exception}")
            raise ContentGenerationError(err_msg) from last_exception
        else: 
            logging.error(err_msg + " No specific last exception recorded.")
            raise ContentGenerationError(err_msg)
            
    else:
        # Standard non-reasoning mode (existing implementation)
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

                logging.info(f"Tweet {tweet_id}: Attempt {attempt_num_for_model}/{config.content_retries} to generate KB content JSON using model {model_to_use}.")
                
                try:
                    raw_response_text = await http_client.ollama_generate(
                        model=model_to_use,
                        prompt=prompt,
                        temperature=0.2, 
                        options={"json_mode": True},
                        timeout=config.content_generation_timeout # Using the configured timeout
                    )

                    if not raw_response_text:
                        logging.warning(f"Tweet {tweet_id}: Empty raw response from {model_to_use} (attempt {attempt_num_for_model}).")
                        last_exception = ContentGenerationError("Generated content JSON is empty")
                    else:
                        json_str_from_response = _extract_json_from_text(raw_response_text)
                        if json_str_from_response:
                            try:
                                content_json = json.loads(json_str_from_response)
                                if not isinstance(content_json, dict) or "suggested_title" not in content_json or "sections" not in content_json:
                                    logging.warning(f"Tweet {tweet_id}: Invalid JSON structure from {model_to_use} (attempt {attempt_num_for_model}). Missing key fields. Extracted JSON: {json_str_from_response[:500]}")
                                    last_exception = ContentGenerationError("Generated content JSON lacks required structure (e.g., missing title or sections).")
                                else:
                                    logging.info(f"Tweet {tweet_id}: Successfully generated and parsed KB content JSON from {model_to_use} (attempt {attempt_num_for_model}).")
                                    return content_json
                            except json.JSONDecodeError as e:
                                logging.warning(f"Tweet {tweet_id}: Failed to decode extracted JSON from {model_to_use} (attempt {attempt_num_for_model}): {e}. Extracted JSON: {json_str_from_response[:500]}")
                                last_exception = ContentGenerationError(f"Failed to decode extracted JSON: {e}")
                        else: # No JSON found by _extract_json_from_text
                            logging.warning(f"Tweet {tweet_id}: Could not extract valid JSON from {model_to_use} response (attempt {attempt_num_for_model}). Response: {raw_response_text[:500]}")
                            last_exception = ContentGenerationError("No valid JSON found in model response.")
                
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

    title_val = kb_json.get("suggested_title", "Knowledge Base Item")
    title = _ensure_string_from_value(title_val)
    lines.append(f"# {title}")
    lines.append("")

    introduction_val = kb_json.get("introduction", "")
    introduction = _ensure_string_from_value(introduction_val)
    if introduction:
        lines.append(f"## Introduction")
        lines.append(introduction)
        lines.append("")

    for section in kb_json.get("sections", []):
        heading_val = section.get("heading", "Section")
        heading = _ensure_string_from_value(heading_val)
        lines.append(f"## {heading}")
        lines.append("")

        for paragraph_val in section.get("content_paragraphs", []):
            paragraph = _ensure_string_from_value(paragraph_val)
            lines.append(paragraph)
            lines.append("")

        for code_block in section.get("code_blocks", []):
            lang = _ensure_string_from_value(code_block.get("language", "plain_text"))
            code = _ensure_string_from_value(code_block.get("code", ""))
            explanation_val = code_block.get("explanation", "")
            explanation = _ensure_string_from_value(explanation_val)
            if explanation:
                lines.append(f"_{explanation}_") 
                lines.append("")
            lines.append(f"```{lang}\n{code}\n```")
            lines.append("")

        for list_data in section.get("lists", []):
            list_type = _ensure_string_from_value(list_data.get("type", "bulleted"))
            prefix = "-" if list_type == "bulleted" else "1."
            for item_val in list_data.get("items", []):
                item_text = _ensure_string_from_value(item_val)
                lines.append(f"{prefix} {item_text}")
            lines.append("")
        
        for note_val in section.get("notes_or_tips", []):
            note = _ensure_string_from_value(note_val)
            lines.append(f"> **Note/Tip:** {note}") 
            lines.append("")

    takeaways_list = kb_json.get("key_takeaways", [])
    if takeaways_list: # Ensure it's actually a list before iterating
        lines.append("## Key Takeaways")
        lines.append("")
        for takeaway_val in takeaways_list:
            takeaway = _ensure_string_from_value(takeaway_val)
            lines.append(f"- {takeaway}")
        lines.append("")

    conclusion_val = kb_json.get("conclusion", "")
    conclusion = _ensure_string_from_value(conclusion_val)
    if conclusion:
        lines.append("## Conclusion")
        lines.append(conclusion)
        lines.append("")

    references_list = kb_json.get("external_references", [])
    if references_list: # Ensure it's actually a list
        lines.append("## External References")
        lines.append("")
        for ref in references_list:
            if isinstance(ref, dict): # Ensure ref is a dict before .get
                text_val = ref.get("text", ref.get("url", "Link"))
                url_val = ref.get("url", "#")
                text = _ensure_string_from_value(text_val)
                url = _ensure_string_from_value(url_val)
                lines.append(f"- [{text}]({url})")
            else: # Handle case where ref might not be a dict
                ref_str = _ensure_string_from_value(ref)
                lines.append(f"- {ref_str}") # Fallback to just listing it
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
        
        # Log the raw JSON received from the LLM for debugging
        logging.debug(f"KB_ITEM_GEN ({tweet_id}): Raw JSON from LLM: {json.dumps(kb_content_json, indent=2)}")

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