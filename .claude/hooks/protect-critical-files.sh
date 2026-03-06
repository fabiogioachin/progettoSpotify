#!/bin/bash
# PreToolUse hook: blocks writes to .env and database files.
# Receives tool input JSON on stdin.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)

# Normalize Windows backslashes
FILE_PATH=$(echo "$FILE_PATH" | tr '\\' '/')

# Block .env files (credentials must be managed manually)
if echo "$FILE_PATH" | grep -qE '/\.env(\..*)?$'; then
  echo "BLOCKED: .env files contain credentials and must be edited manually." >&2
  exit 2
fi

# Block database files
if echo "$FILE_PATH" | grep -qE '\.(db|sqlite|sqlite3)$'; then
  echo "BLOCKED: database files must not be edited directly." >&2
  exit 2
fi

# Block settings.local.json (personal, non-shared config)
if echo "$FILE_PATH" | grep -qE '/\.claude/settings\.local\.json$'; then
  echo "BLOCKED: settings.local.json is personal configuration — edit it manually if needed." >&2
  exit 2
fi

exit 0
