import logging
from collections import defaultdict
from pathlib import Path

from ..config import Config
from ..exceptions import IndexerError
from ..types import TweetData # Import TweetData for type hint
from ..utils import file_io
from .state import StateManager

logger = logging.getLogger(__name__)

async def generate_root_readme(state_manager: StateManager, config: Config):
    """
    Generates the root README.md file summarizing the knowledge base structure.
    """
    logger.info("Generating root README.md for the knowledge base...")
    kb_root = config.knowledge_base_dir.resolve()
    readme_path = kb_root / "README.md"

    try:
        # Get all successfully generated items
        all_items = state_manager.get_all_tweet_data().values()
        generated_items = [
            item for item in all_items
            if item.kb_item_created and item.main_category and item.sub_category and item.item_name
        ]

        if not generated_items:
            logger.warning("No generated KB items found to include in the index.")
            # Write an empty or placeholder README?
            await file_io.write_text_atomic_async(readme_path, "# Knowledge Base\n\n(No items generated yet)")
            return

        # Group items by category/sub-category
        structure = defaultdict(lambda: defaultdict(list))
        for item in sorted(generated_items, key=lambda x: (x.main_category or "", x.sub_category or "", x.item_name or "")):
             structure[item.main_category][item.sub_category].append(item)

        # Build Markdown content
        md_lines = ["# Knowledge Base Index\n"]
        for main_cat, sub_cats in sorted(structure.items()):
            md_lines.append(f"\n## {main_cat}\n")
            for sub_cat, items in sorted(sub_cats.items()):
                md_lines.append(f"\n### {sub_cat}\n")
                for item in items:
                    # Link using the relative path stored in item.kb_item_path
                    link_path = item.kb_item_path.as_posix() # Use forward slashes for Markdown links
                    md_lines.append(f"- [{item.item_name}]({link_path}/README.md)") # Link to the item's README

        # Write the file
        content = "\n".join(md_lines)
        await file_io.write_text_atomic_async(readme_path, content)
        logger.info(f"Root README.md generated successfully at {readme_path}")

    except Exception as e:
        logger.error(f"Failed to generate root README.md: {e}", exc_info=True)
        raise IndexerError(f"Failed to generate root README: {e}", original_exception=e) from e


async def generate_indexes(state_manager: StateManager, config: Config):
     """Main function for the indexing phase."""
     # Currently only generates the root README.
     # Could be extended for GitHub Pages later.
     await generate_root_readme(state_manager, config)
     # await generate_github_pages(state_manager, config) # Placeholder

# Placeholder for GitHub Pages generation if implemented later
# async def generate_github_pages(state_manager: StateManager, config: Config):
#     logger.warning("GitHub Pages generation is not yet implemented.")
#     pass
