def validate_name(name: str, max_length: int = 100, is_directory: bool = True) -> bool:
    """Unified name validation for both categories and directories."""
    if not name or len(name) > max_length:
        return False
    
    # Directory names have stricter requirements
    forbidden_chars = r'\/:*?"<>|' if is_directory else r'*?"<>|'
    return not any(c in forbidden_chars for c in name)

# Update existing functions to use the unified validator
def validate_category_name(name: str) -> bool:
    return validate_name(name, max_length=100, is_directory=False)

def validate_directory_name(name: str) -> bool:
    return validate_name(name, max_length=50, is_directory=True) 
