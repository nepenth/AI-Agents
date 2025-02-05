import shutil
import logging
from pathlib import Path
from .markdown_writer import generate_root_readme
from .ai_categorization import re_categorize_offline

def reprocess_existing_items(knowledge_base_dir: Path, category_manager) -> None:
    all_items = []
    for main_cat_dir in knowledge_base_dir.iterdir():
        if not main_cat_dir.is_dir() or main_cat_dir.name.startswith('.'):
            continue
        main_cat_name = main_cat_dir.name

        for sub_cat_dir in main_cat_dir.iterdir():
            if not sub_cat_dir.is_dir() or sub_cat_dir.name.startswith('.'):
                continue
            sub_cat_name = sub_cat_dir.name

            for item_dir in sub_cat_dir.iterdir():
                if not item_dir.is_dir() or item_dir.name.startswith('.'):
                    continue
                content_file = item_dir / "content.md"
                if content_file.exists():
                    all_items.append((main_cat_name, sub_cat_name, item_dir.name, content_file))

    for (main_cat_name, sub_cat_name, item_name, content_file) in all_items:
        print(f"\nItem: {main_cat_name}/{sub_cat_name}/{item_name}")
        user_input = input("Reprocess this entry for better categorization/title? (y/n): ").strip().lower()
        if user_input == 'y':
            content_text = content_file.read_text(encoding='utf-8')
            new_main_cat, new_sub_cat, new_item_name = re_categorize_offline(content_text, ollama_url="", text_model="", category_manager=category_manager)
            print(f"\nNew Suggestion => Category: {new_main_cat}/{new_sub_cat}, Title: {new_item_name}")
            confirm = input("Apply this re-categorization? (y/n): ").strip().lower()
            if confirm == 'y':
                old_path = knowledge_base_dir / main_cat_name / sub_cat_name / item_name
                new_path = knowledge_base_dir / new_main_cat / new_sub_cat / new_item_name
                if not new_path.exists():
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_path), str(new_path))
                print(f"Moved item from {old_path} => {new_path}")
                cm_path = new_path / "content.md"
                if cm_path.exists():
                    old_lines = cm_path.read_text(encoding='utf-8').splitlines(True)
                    new_content_lines = []
                    for line in old_lines:
                        if line.startswith("# "):
                            new_content_lines.append(f"# {new_item_name}\n")
                        else:
                            new_content_lines.append(line)
                    cm_path.write_text("".join(new_content_lines), encoding='utf-8')
                    print("Updated content.md title to new item name.")
            else:
                print("Skipped changes for this item.")
