#!/bin/bash
# Post-write hook to format files after creating
# Auto-formats files when Claude Code writes them

# Read JSON from stdin and extract file path
FILE=$(jq -r '.tool_input.file_path' 2>/dev/null)

if [ -z "$FILE" ] || [ "$FILE" = "null" ]; then
  exit 0
fi

# Check if file exists
if [ ! -f "$FILE" ]; then
  exit 0
fi

# Format based on file type
case "$FILE" in
  */package.json)
    npx sort-package-json "$FILE" 2>/dev/null
    ;;
  *.yml|*.yaml|*.json)
    npx prettier --write "$FILE" 2>/dev/null
    ;;
  *.md|*.mdx)
    npx prettier --write "$FILE" 2>/dev/null
    ;;
  *.js|*.jsx|*.ts|*.tsx)
    npx prettier --write "$FILE" 2>/dev/null
    npx eslint --cache --fix "$FILE" 2>/dev/null
    ;;
esac

exit 0
