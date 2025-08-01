#!/bin/bash

# Define paths (update if needed)
CODEBASE_ROOT="/home/nepenthe/git_repos/agents/knowledge-base"
JS_FOLDER="$CODEBASE_ROOT/knowledge_base_agent/static/v2/js"

# Get list of JS file basenames
JS_FILES=$(find "$JS_FOLDER" -type f -name "*.js" -exec basename {} \;)

# Array to collect truly unused files
declare -a unused_files=()

# Loop through each JS file basename
for js_file in $JS_FILES; do
    # Define enhanced search patterns for external references
    patterns=(
        "$js_file"                # Bare basename, e.g., script.js
        "js/$js_file"             # Partial path, e.g., js/script.js
        "v2/js/$js_file"          # Deeper path, e.g., v2/js/script.js
        "static/v2/js/$js_file"   # Full static path, e.g., static/v2/js/script.js
        "/js/$js_file"            # Absolute-like, e.g., /js/script.js
    )
    
    # Build grep command with multiple -e flags for patterns (external search)
    grep_cmd="grep -r --exclude-dir=$(basename "$JS_FOLDER")"
    for pattern in "${patterns[@]}"; do
        grep_cmd+=" -e '$pattern'"
    done
    grep_cmd+=" '$CODEBASE_ROOT'"
    
    # Execute the external search and count matches
    external_match_count=$(eval "$grep_cmd" | wc -l)
    
    # Separate search for intra-JS references (within JS folder only, excluding the file itself)
    intra_patterns=(
        "$js_file"
        "\./$js_file"             # e.g., ./script.js in imports
        "'$js_file'"              # Single-quoted
        "\"$js_file\""            # Double-quoted
    )
    intra_grep_cmd="grep -r --exclude='$js_file'"
    for pattern in "${intra_patterns[@]}"; do
        intra_grep_cmd+=" -e '$pattern'"
    done
    intra_grep_cmd+=" '$JS_FOLDER'"
    
    intra_match_count=$(eval "$intra_grep_cmd" | wc -l)
    
    # Check if both external and internal counts are zero
    if [ "$external_match_count" -eq 0 ] && [ "$intra_match_count" -eq 0 ]; then
        unused_files+=("$js_file")
    fi
done

# Output the list of truly unused files
echo "Truly unused JS files (no references anywhere):"
if [ ${#unused_files[@]} -eq 0 ]; then
    echo "None found."
else
    for file in "${unused_files[@]}"; do
        echo "- $file"
    done
fi
