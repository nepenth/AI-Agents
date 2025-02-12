import logging
from pathlib import Path
import shutil
import asyncio
import aiofiles

async def migrate_content_to_readme(knowledge_base_dir: Path) -> None:
    """
    Migrate existing content.md files to README.md in the knowledge base.
    """
    logging.info("Starting migration of content.md files to README.md")
    migrated_count = 0
    failed_count = 0

    try:
        # Walk through all directories in the knowledge base
        for content_file in knowledge_base_dir.rglob('content.md'):
            try:
                # Define the new README path in the same directory
                readme_path = content_file.parent / "README.md"
                
                # Skip if README already exists
                if readme_path.exists():
                    logging.warning(f"README.md already exists at {readme_path}, skipping migration")
                    continue

                # Copy content.md to README.md
                async with aiofiles.open(content_file, 'r', encoding='utf-8') as source:
                    content = await source.read()
                    async with aiofiles.open(readme_path, 'w', encoding='utf-8') as target:
                        await target.write(content)

                # Remove the old content.md file
                content_file.unlink()
                migrated_count += 1
                print(f"\rMigrated files: {migrated_count}", end="")

            except Exception as e:
                logging.error(f"Failed to migrate {content_file}: {e}")
                failed_count += 1

    except Exception as e:
        logging.error(f"Migration error: {e}")
        raise

    print(f"\n\nMigration complete:")
    print(f"Successfully migrated: {migrated_count} files")
    if failed_count > 0:
        print(f"Failed to migrate: {failed_count} files") 