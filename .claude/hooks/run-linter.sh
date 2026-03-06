#!/bin/bash
# PostToolUse hook (async): runs the appropriate linter on the modified file.
# Receives tool input JSON on stdin. Outputs JSON systemMessage for Claude.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)

# Normalize Windows backslashes
FILE_PATH=$(echo "$FILE_PATH" | tr '\\' '/')

# Python files in backend/ → ruff check
if [[ "$FILE_PATH" == *.py ]] && echo "$FILE_PATH" | grep -q '/backend/'; then
  BACKEND_DIR=$(echo "$FILE_PATH" | sed 's|/backend/.*|/backend|')
  RESULT=$(cd "$BACKEND_DIR" 2>/dev/null && ruff check --quiet "$FILE_PATH" 2>&1)
  if [ $? -ne 0 ] && [ -n "$RESULT" ]; then
    # Escape for JSON
    ESCAPED=$(echo "$RESULT" | python -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))" 2>/dev/null)
    echo "{\"systemMessage\": \"Ruff lint issues in modified file:\\n${ESCAPED}\"}"
  fi
  exit 0
fi

# JS/JSX files in frontend/ → eslint
if [[ "$FILE_PATH" == *.js ]] || [[ "$FILE_PATH" == *.jsx ]]; then
  if echo "$FILE_PATH" | grep -q '/frontend/'; then
    FRONTEND_DIR=$(echo "$FILE_PATH" | sed 's|/frontend/.*|/frontend|')
    RESULT=$(cd "$FRONTEND_DIR" 2>/dev/null && npx eslint --quiet "$FILE_PATH" 2>&1)
    if [ $? -ne 0 ] && [ -n "$RESULT" ]; then
      ESCAPED=$(echo "$RESULT" | python -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))" 2>/dev/null)
      echo "{\"systemMessage\": \"ESLint issues in modified file:\\n${ESCAPED}\"}"
    fi
    exit 0
  fi
fi

exit 0
