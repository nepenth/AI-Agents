import os
import ast
import sys
from pathlib import Path

def find_imports_in_file(file_path):
    """Extract all imported modules from a Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        imports = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])  # Get base module name
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])  # Get base module name
        
        return imports
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return set()

def audit_modules(directory_path):
    """Audit all Python modules in the directory for unused imports"""
    # Get all Python files
    python_files = list(Path(directory_path).rglob("*.py"))
    
    # Collect all imports from all files
    all_imports = set()
    file_imports = {}
    
    for file_path in python_files:
        if 'venv' in str(file_path) or '__pycache__' in str(file_path):
            continue
            
        imports = find_imports_in_file(file_path)
        all_imports.update(imports)
        file_imports[str(file_path)] = imports
    
    # Get all Python files in directory (including subdirectories)
    all_py_files = [f for f in Path(directory_path).rglob("*.py") 
                   if 'venv' not in str(f) and '__pycache__' not in str(f)]
    
    # Get all modules that exist as files
    existing_modules = set()
    for file_path in all_py_files:
        module_name = file_path.stem
        if module_name != '__init__':
            existing_modules.add(module_name)
    
    # Find unused modules (modules that exist but aren't imported anywhere)
    unused_modules = existing_modules - all_imports
    
    print("=== UNUSED MODULES IN KNOWLEDGE_BASE_AGENT ===")
    
    if unused_modules:
        print(f"Found {len(unused_modules)} potentially unused modules:")
        for module in sorted(unused_modules):
            print(f"  - {module}")
    else:
        print("No unused modules found.")
    
    return unused_modules

if __name__ == "__main__":
    # Get directory path from command line or default to current directory
    directory = sys.argv[1] if len(sys.argv) > 1 else "knowledge_base_agent"
    audit_modules(directory)