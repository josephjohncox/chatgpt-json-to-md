#!/bin/zsh
SCRIPT="chatgpt_json_to_md.py"

for f in "$1"/*.json; do
  [ -e "$f" ] || continue   # if no *.json, skip
  python "$SCRIPT" "$f" -o "${f%.json}.md"
done