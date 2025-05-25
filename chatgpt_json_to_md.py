"""chatgpt_json_to_md.py

Convert ChatGPT conversation JSON (including Canvas objects) into Markdown.

USAGE
-----
python chatgpt_json_to_md.py path/to/input.json [-o path/to/output.md]

If -o/--output is omitted, the Markdown is written to STDOUT.

JSON EXPECTATIONS
-----------------
The input file should be a JSON object or list produced by ChatGPT.

* Either a top‑level list of messages OR an object with a "messages" key.
* Each message is an object with at minimum:
    - role: "user" | "assistant" | "system" | ...
    - content: string | list of strings
* Canvas messages are represented as objects with "type": "canvas" and an
  embedded "canvas" object identical to canmore.create_textdoc payloads:
    {
        "type": "canvas",
        "canvas": {
            "name": "file.py",
            "type": "code/python",  # or "document"
            "content": "..."
        }
    }

Anything outside this minimal contract is ignored but preserved as raw JSON
comment blocks so that no information is silently dropped.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, cast

Message = Dict[str, Any]


# ---------------------------------------------------------------------------
# Citation processing helpers
# ---------------------------------------------------------------------------

def process_citations(content: str, metadata: Dict[str, Any]) -> tuple[str, List[Dict[str, Any]]]:
    """Process citations in content and return updated content with references list."""
    content_references = metadata.get("content_references", [])
    search_result_groups = metadata.get("search_result_groups", [])
    
    references = []
    processed_content = content
    
    # Process content references (inline citations)
    for ref in content_references:
        matched_text = ref.get("matched_text", "")
        alt_text = ref.get("alt", "")
        
        # Skip empty matches or sources footnotes
        if not matched_text or ref.get("type") == "sources_footnote":
            continue
            
        # Replace the cite tag with the alt text (which contains markdown links)
        if matched_text in processed_content and alt_text:
            processed_content = processed_content.replace(matched_text, alt_text)
        
        # Collect reference items for the references section
        items = ref.get("items", [])
        for item in items:
            if isinstance(item, dict) and "title" in item and "url" in item:
                ref_entry = {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "attribution": item.get("attribution", ""),
                    "snippet": item.get("snippet", "")
                }
                # Avoid duplicates
                if ref_entry not in references:
                    references.append(ref_entry)
    
    # Process search result groups (additional search results)
    for group in search_result_groups:
        if isinstance(group, dict) and "entries" in group:
            entries = group.get("entries", [])
            for entry in entries:
                if isinstance(entry, dict) and "title" in entry and "url" in entry:
                    ref_entry = {
                        "title": entry.get("title", ""),
                        "url": entry.get("url", ""),
                        "attribution": entry.get("attribution", ""),
                        "snippet": entry.get("snippet", "")
                    }
                    # Avoid duplicates
                    if ref_entry not in references:
                        references.append(ref_entry)
    
    return processed_content, references


def format_references_section(references: List[Dict[str, Any]]) -> str:
    """Format references into a markdown section."""
    if not references:
        return ""
    
    lines = ["", "## References", ""]
    
    for i, ref in enumerate(references, 1):
        title = ref.get("title", "Untitled")
        url = ref.get("url", "")
        attribution = ref.get("attribution", "")
        snippet = ref.get("snippet", "")
        
        # Format reference entry
        ref_line = f"{i}. **{title}**"
        if attribution:
            ref_line += f" - {attribution}"
        if url:
            ref_line += f"  \n   [{url}]({url})"
        if snippet:
            # Truncate snippet if too long
            if len(snippet) > 200:
                snippet = snippet[:200] + "..."
            ref_line += f"  \n   _{snippet}_"
        
        lines.append(ref_line)
        lines.append("")
    
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown rendering helpers
# ---------------------------------------------------------------------------

def json_messages_to_markdown(messages: List[Message]) -> str:
    """Convert list of ChatGPT message objects to a Markdown string directly."""
    md_lines = ["# ChatGPT Conversation", ""]
    
    for msg in messages:
        if msg.get("type") == "canvas":
            canvas = msg.get("canvas", {})
            name = canvas.get("name", "untitled")
            ctype = canvas.get("type", "document")
            content = canvas.get("content", "")
            
            if ctype.startswith("code/"):
                lang = ctype.split("/", 1)[1]
                md_lines.extend([
                    f"### {name} - Code ({lang})",
                    "",
                    f"```{lang}",
                    content,
                    "```",
                    ""
                ])
            else:
                md_lines.extend([
                    f"### {name}",
                    "",
                    content,
                    ""
                ])
        else:
            role = msg.get("role", "assistant")
            content = msg.get("content", "")
            metadata = msg.get("metadata", {})
            
            # Handle direct code content
            if isinstance(content, dict) and "type" in content and "content" in content:
                content_type = content["type"]
                content_text = content["content"]
                
                if content_type.startswith("code/"):
                    # Extract language for code blocks
                    lang = content_type.split("/", 1)[1]
                    content = f"```{lang}\n{content_text}\n```"
                else:
                    # Just use the content directly
                    content = content_text
            
            # Process content if it's a string that looks like JSON
            if isinstance(content, str) and content.strip().startswith('{') and content.strip().endswith('}'):
                try:
                    content_json = json.loads(content)
                    
                    # Handle updates with replacements
                    if "updates" in content_json and isinstance(content_json["updates"], list):
                        updates = content_json["updates"]
                        if updates and isinstance(updates[0], dict) and "replacement" in updates[0]:
                            replacement = updates[0]["replacement"]
                            
                            # Check for content references to original messages
                            content_references = content_json.get("content_references", [])
                            referenced_type = None
                            
                            # Try to get type information from referenced content
                            if content_references and isinstance(content_references, list):
                                for ref in content_references:
                                    if isinstance(ref, dict) and "type" in ref:
                                        referenced_type = ref.get("type")

                            # Format as code block based on type
                            if isinstance(replacement, dict) and "code" in replacement and "language" in replacement:
                                # Use specified language and code
                                lang = replacement["language"]
                                code = replacement["code"]
                                content = f"```{lang}\n{code}\n```"
                            elif isinstance(replacement, dict) and "type" in replacement:
                                # Use type directly from the replacement
                                rtype = replacement["type"]
                                if rtype.startswith("code/"):
                                    # Extract language from code type
                                    lang = rtype.split("/", 1)[1]
                                    code_content = replacement.get("content", "")
                                    content = f"```{lang}\n{code_content}\n```"
                                else:
                                    # Use JSON formatting as fallback
                                    content = f"```json\n{json.dumps(replacement, indent=2)}\n```"
                            elif referenced_type and referenced_type.startswith("code/"):
                                # Use the referenced content type
                                lang = referenced_type.split("/", 1)[1]
                                if isinstance(replacement, str):
                                    content = f"```{lang}\n{replacement}\n```"
                                else:
                                    content = f"```{lang}\n{json.dumps(replacement, indent=2)}\n```"
                            elif isinstance(replacement, dict):
                                # JSON object - format as JSON
                                content = f"```json\n{json.dumps(replacement, indent=2)}\n```"
                            elif isinstance(replacement, str):
                                # Plain text - use simple code block
                                content = f"```\n{replacement}\n```"
                            else:
                                # Other types - use plain code block
                                content = f"```\n{str(replacement)}\n```"
                except (json.JSONDecodeError, AttributeError, TypeError):
                    pass
            
            if isinstance(content, list):
                content = "".join([str(item) for item in cast(List[Any], content)])
            elif not isinstance(content, str):
                content = f"```json\n{json.dumps(content, indent=2)}\n```"
            
            # Process citations if content is a string
            message_references = []
            if isinstance(content, str) and metadata:
                content, message_references = process_citations(content, metadata)
                
            header_map = {"user": "User", "assistant": "Assistant", "system": "System"}
            header = header_map.get(role, role.capitalize())
            
            md_lines.extend([
                f"## {header}",
                "",
                content,
                ""
            ])
            
            # Add references for this message if any exist
            if message_references:
                references_section = format_references_section(message_references)
                if references_section:
                    md_lines.append(references_section)
                    md_lines.append("")  # Extra spacing after references
    
    return "\n".join(md_lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Convert ChatGPT JSON export (including Canvas) to Markdown"
    )
    parser.add_argument("input", type=Path, help="Path to JSON file. Use '-' for STDIN.")
    parser.add_argument(
        "-o", "--output", type=Path, default=None, help="Output Markdown file path."
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Print debugging information"
    )

    args = parser.parse_args(argv)

    # ---------------------------------------------------------------------
    # Read JSON
    # ---------------------------------------------------------------------
    if str(args.input) == "-":
        raw = sys.stdin.read()
    else:
        raw = args.input.read_text()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"[ERROR] Invalid JSON: {exc}")

    # Process different formats
    messages: List[Message] = []
    
    # Detect data format
    if isinstance(data, list):
        # Could be a list of messages directly, or a list of conversations
        if len(data) > 0 and isinstance(data[0], dict):
            if "mapping" in data[0]:
                # This is a conversation with mapping - extract from first item
                mapping_data: Dict[str, Any] = data[0]["mapping"]
                messages = extract_messages_from_mapping(mapping_data)
            elif "role" in data[0] and "content" in data[0]:
                # This is a list of messages directly
                messages = data
    elif isinstance(data, dict):
        # Could be a conversation object or a single message
        if "mapping" in data:
            # Conversation with mapping
            mapping_data: Dict[str, Any] = data["mapping"]
            messages = extract_messages_from_mapping(mapping_data)
        elif "messages" in data and isinstance(data["messages"], list):
            # Object with messages array
            messages = data["messages"]
        elif "role" in data and "content" in data:
            # Single message
            messages = [data]
        elif all(isinstance(data.get(k), dict) and "role" in data.get(k, {}) for k in data):
            # Mapping of messages
            messages = list(data.values())
    
    # Print debug info if requested
    if args.debug:
        print(f"Found {len(messages)} messages:")
        for i, msg in enumerate(messages[:5]):  # Print first 5 msgs
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                short_content = content[:50] + "..." if len(content) > 50 else content
            else:
                short_content = str(content)[:50] + "..."
            print(f"{i+1}: {role} - {short_content}")
        if len(messages) > 5:
            print(f"... and {len(messages) - 5} more")

    markdown = json_messages_to_markdown(messages)

    # ---------------------------------------------------------------------
    # Write Markdown
    # ---------------------------------------------------------------------
    if args.output:
        args.output.write_text(markdown)
    else:
        sys.stdout.write(markdown)


def extract_messages_from_mapping(mapping: Dict[str, Any]) -> List[Message]:
    """Extract messages from the mapping structure in a tree/graph format."""
    messages: List[Message] = []
    
    # Find the root node (one with parent=null)
    root_ids = [node_id for node_id, node in mapping.items() 
                if node.get("parent") is None]
    
    if not root_ids:
        return messages
    
    # Keep track of visited nodes to avoid duplicate processing
    visited = set()
    
    # Traverse the tree in order
    def traverse(node_id: str) -> None:
        if node_id in visited:
            return
            
        visited.add(node_id)
        node = mapping.get(node_id, {})
        
        # Add the message if it exists
        if node.get("message"):
            msg = node["message"]
            
            # Skip visually hidden messages (typically system prompts)
            metadata = msg.get("metadata", {})
            if metadata.get("is_visually_hidden_from_conversation", False):
                # Skip this message but process children
                for child_id in node.get("children", []):
                    traverse(child_id)
                return
                
            message_obj: Message = {}
            
            # Extract author/role
            author = msg.get("author", {})
            if isinstance(author, dict) and "role" in author:
                message_obj["role"] = author.get("role", "unknown")
            
            # Extract content based on type
            content_obj = msg.get("content", {})
            content_text = ""
            
            if isinstance(content_obj, dict):
                content_type = content_obj.get("content_type", "unknown")
                
                # Handle different content types
                if content_type == "text" and "parts" in content_obj:
                    # Standard text content with parts
                    parts = content_obj.get("parts", [])
                    content_text = "".join(str(part) for part in parts if part)
                elif content_type == "canvas":
                    # Canvas content
                    message_obj["type"] = "canvas"
                    message_obj["canvas"] = content_obj
                    content_text = f"Canvas: {content_obj.get('name', 'unnamed')}"
                elif content_type == "thoughts":
                    # Format thoughts in a more readable way
                    thoughts = content_obj.get("thoughts", [])
                    formatted_thoughts = []
                    
                    for thought in thoughts:
                        summary = thought.get("summary", "")
                        content = thought.get("content", "")
                        if summary:
                            formatted_thoughts.append(f"**{summary}**\n{content}")
                        else:
                            formatted_thoughts.append(content)
                    
                    content_text = "\n\n".join(formatted_thoughts)
                    if not content_text:
                        content_text = json.dumps(content_obj, indent=2)
                elif content_type == "reasoning_recap":
                    # Extract the content directly
                    recap_content = content_obj.get("content", "")
                    if recap_content:
                        content_text = recap_content
                    else:
                        content_text = json.dumps(content_obj, indent=2)
                else:
                    # Handle other content types or raw objects as JSON
                    content_text = json.dumps(content_obj, indent=2)
            elif isinstance(content_obj, str):
                # Direct string content
                content_text = content_obj
            else:
                # Fallback
                content_text = str(content_obj)
            
            message_obj["content"] = content_text
            
            # Preserve metadata for citation processing
            if metadata:
                message_obj["metadata"] = metadata
            
            # Check for canvas messages via content
            if (message_obj["role"] == "assistant" and 
                isinstance(message_obj["content"], str) and
                message_obj["content"].strip().startswith('{')):
                # Try to parse as JSON to see if it's a canvas
                try:
                    content_json = json.loads(message_obj["content"])
                    if ("name" in content_json and "type" in content_json and
                        "content" in content_json and content_json["type"].startswith("code/")):
                        # This is a canvas code block
                        message_obj["type"] = "canvas"
                        message_obj["canvas"] = {
                            "name": content_json["name"],
                            "type": content_json["type"],
                            "content": content_json["content"]
                        }
                    # Handle content with updates/replacements
                    elif "updates" in content_json and isinstance(content_json["updates"], list):
                        updates = content_json["updates"]
                        if updates and isinstance(updates[0], dict) and "replacement" in updates[0]:
                            # Just extract and use the replacement directly
                            replacement = updates[0]["replacement"]
                            if isinstance(replacement, str):
                                message_obj["content"] = replacement
                            else:
                                message_obj["content"] = json.dumps(replacement, indent=2)
                except (json.JSONDecodeError, AttributeError, TypeError):
                    pass
            
            # Only add messages with both role and non-empty content
            if message_obj.get("role") and message_obj.get("content") and message_obj["content"].strip():
                messages.append(message_obj)
        
        # Recursively process children
        for child_id in node.get("children", []):
            traverse(child_id)
    
    # Start traversal from each root
    for root_id in root_ids:
        traverse(root_id)
    
    return messages


if __name__ == "__main__":
    _cli()
