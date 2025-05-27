# ChatGPT JSON to Markdown Converter

Converts ChatGPT conversation exports (JSON) to Markdown format.

## Features

- Supports multiple JSON formats from ChatGPT exports
- Converts bracket citations `【12†L123-L131】` to clickable links
- Handles Canvas code blocks and documents
- Generates reference sections from citation metadata
- Processes different content types (text, code, thoughts, reasoning)

## Installation

No dependencies required - uses Python standard library only.

## Getting ChatGPT Conversation Data

### Option 1: Bookmarklet (Recommended)

1. Setup and json export bookmarklet (https://github.com/pionxzh/chatgpt-exporter)
2. Go to a ChatGPT conversation and click the bookmarklet
3. Download or copy the JSON data

### Option 2: Manual Export
1. Go to ChatGPT Settings → Data controls → Export data
2. Download the ZIP file when ready
3. Extract and find `conversations.json`

## Usage

```bash
# Convert JSON to Markdown
python chatgpt_json_to_md.py conversation.json

# Save to file
python chatgpt_json_to_md.py conversation.json -o output.md

# Read from stdin
cat conversation.json | python chatgpt_json_to_md.py - -o output.md

# Debug mode
python chatgpt_json_to_md.py conversation.json -d
```

### Options

- `input`: JSON file path (use `-` for stdin)
- `-o, --output`: Output file (default: stdout)
- `-d, --debug`: Show processing info

## Supported JSON Formats

### Message list
```json
[
  {"role": "user", "content": "Hello"},
  {"role": "assistant", "content": "Hi there"}
]
```

### Object with messages
```json
{
  "messages": [
    {"role": "user", "content": "What is AI?"}
  ]
}
```

### Mapping structure (ChatGPT export format)
```json
{
  "mapping": {
    "node-id": {
      "message": {
        "author": {"role": "user"},
        "content": {"content_type": "text", "parts": ["Hello"]}
      },
      "children": ["next-node-id"]
    }
  }
}
```

## Citations

### Bracket citations (o1 research)
Input:
```json
{
  "role": "assistant",
  "content": "AI is a field of study【1†L15-L23】.",
  "metadata": {
    "citations": [
      {
        "metadata": {
          "title": "Introduction to AI",
          "url": "https://example.com/ai"
        }
      }
    ]
  }
}
```

Output:
```markdown
## Assistant

AI is a field of study[【1†L15-L23】](#ref1).

## References

<a id="ref1"></a>
### 1. Introduction to AI
   [https://example.com/ai](https://example.com/ai)
```

### Search result citations
Processes `content_references` and `search_result_groups` from ChatGPT search.

## Content Types

- **Text**: Standard conversation messages
- **Code**: Canvas code blocks with syntax highlighting
- **Thoughts**: o1 reasoning chains
- **Canvas**: Code and document canvases
- **JSON objects**: Formatted as code blocks

## Output Format

```markdown
# ChatGPT Conversation

## User
[message content]

## Assistant  
[response with citation links]

## References
<a id="ref1"></a>
### 1. Reference Title
   [URL](URL)
   _Description_
```

## Examples

```bash
# Convert research conversation
python chatgpt_json_to_md.py research.json -o notes.md

# Process Canvas session
python chatgpt_json_to_md.py canvas.json -o code.md

# Batch convert
for file in *.json; do
  python chatgpt_json_to_md.py "$file" -o "${file%.json}.md"
done
```

## Complete Workflow

### Using Bookmarklet (Easiest)
```bash
# 1. Set up bookmarklet (one-time setup)
# See bookmarklet_instructions.md

# 2. Extract conversation from web page
# Click bookmarklet on ChatGPT conversation page
# Choose "Download JSON file"

# 3. Convert to Markdown
python chatgpt_json_to_md.py your_conversation.json -o output.md
```

### Using Official Export
```bash
# 1. Export from ChatGPT Settings → Data controls → Export data
# 2. Extract conversations.json from ZIP file
# 3. Convert to Markdown
python chatgpt_json_to_md.py conversations.json -o output.md
```

## Requirements

- Python 3.8+
- No external dependencies

## Compatibility

Works with GitHub Markdown, and other Markdown processors that support HTML anchors.
