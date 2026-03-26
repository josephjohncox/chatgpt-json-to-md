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
import re

Message = Dict[str, Any]


def _extract_canvas_payload(payload: Any) -> Dict[str, str] | None:
    """Return a canvas-like payload when the object matches {name,type,content}."""
    if not isinstance(payload, dict):
        return None

    name = payload.get("name")
    canvas_type = payload.get("type")
    content = payload.get("content")
    if not isinstance(name, str) or not isinstance(canvas_type, str) or not isinstance(content, str):
        return None

    return {
        "name": name,
        "type": canvas_type,
        "content": content,
    }


def _extract_canvas_from_json_text(text: str) -> Dict[str, str] | None:
    """Parse a serialized JSON string and return a canvas-like payload if present."""
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

    return _extract_canvas_payload(payload)


def _make_reference_link(label: str, anchor_id: str) -> str:
    """Render a markdown link for an inline citation label."""
    normalized = label.strip() or "[1]"
    if normalized.startswith("[") and normalized.endswith("]"):
        return f"{normalized}(#{anchor_id})"
    return f"[{normalized}](#{anchor_id})"


# ---------------------------------------------------------------------------
# Citation processing helpers
# ---------------------------------------------------------------------------


def extract_bracket_citations(
    content: str, metadata: Dict[str, Any], anchor_prefix: str = "ref-"
) -> tuple[str, List[Dict[str, Any]]]:
    """Extract bracket-style citations like 【12†L123-L131】 and build references from metadata."""
    citations = metadata.get("citations", [])
    references = []
    processed_content = content
    
    # Find all bracket citations in the content
    bracket_pattern = r'【(\d+)†L\d+-L\d+】'
    bracket_matches = re.finditer(bracket_pattern, content)
    
    # Extract references from citations metadata and create citation links
    citation_map = {}
    for i, citation in enumerate(citations):
        if isinstance(citation, dict) and "metadata" in citation:
            cite_meta = citation["metadata"]
            if isinstance(cite_meta, dict):
                title = cite_meta.get("title", "Untitled")
                ref_entry = {
                    "title": title,
                    "url": cite_meta.get("url", ""),
                    "type": cite_meta.get("type", ""),
                    "text": cite_meta.get("text", ""),
                    "pub_date": cite_meta.get("pub_date", "")
                }
                # Avoid duplicates
                if ref_entry not in references:
                    references.append(ref_entry)
                    ref_num = len(references)
                    ref_entry["anchor_id"] = f"{anchor_prefix}{ref_num}"
                    citation_map[i + 1] = ref_num  # Map citation index to reference number
    
    # Replace bracket citations with links to references
    for match in reversed(list(bracket_matches)):  # Reverse to maintain positions
        full_citation = match.group(0)
        citation_num = match.group(1)
        
        # Create link to reference (using HTML anchor)
        if int(citation_num) in citation_map:
            ref_num = citation_map[int(citation_num)]
            link_text = f"[{full_citation}](#{anchor_prefix}{ref_num})"
            processed_content = processed_content[:match.start()] + link_text + processed_content[match.end():]
    
    return processed_content, references


def process_citations(
    content: str, metadata: Dict[str, Any], anchor_prefix: str = "ref-"
) -> tuple[str, List[Dict[str, Any]]]:
    """Process citations in content and return updated content with references list."""
    content_references = metadata.get("content_references", [])
    search_result_groups = metadata.get("search_result_groups", [])
    
    references = []
    processed_content = content
    
    # Process content references (inline citations)
    for ref in content_references:
        matched_text = ref.get("matched_text", "")
        raw_alt_text = ref.get("alt", "")
        alt_text = raw_alt_text if isinstance(raw_alt_text, str) else ""
        invalid = ref.get("invalid", False)
        if invalid:
            alt_text = " "
        
        # Skip empty matches or sources footnotes
        if not matched_text or ref.get("type") == "sources_footnote":
            continue
            
        # Collect reference items for the references section
        replacement_text = alt_text
        items = ref.get("items", [])
        for item in items:
            if isinstance(item, dict) and "title" in item and "url" in item:
                ref_num = len(references) + 1
                anchor_id = f"{anchor_prefix}{ref_num}"
                ref_entry = {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "attribution": item.get("attribution", ""),
                    "snippet": item.get("snippet", ""),
                    "anchor_id": anchor_id,
                }
                # Avoid duplicates
                if ref_entry not in references:
                    references.append(ref_entry)
                    if not replacement_text.strip():
                        replacement_text = f"[{ref_num}]"
                    replacement_text = _make_reference_link(replacement_text, anchor_id)
        
        # Replace the cite tag with a link or fallback text directly
        if matched_text and matched_text in processed_content:
            if replacement_text.strip():
                if replacement_text.startswith("[") and "](" in replacement_text:
                    processed_content = processed_content.replace(matched_text, replacement_text)
                else:
                    processed_content = processed_content.replace(matched_text, replacement_text)
            else:
                processed_content = processed_content.replace(matched_text, "")

    
    # Process search result groups (additional search results)
    for group in search_result_groups:
        if isinstance(group, dict) and "entries" in group:
            entries = group.get("entries", [])
            for entry in entries:
                if isinstance(entry, dict) and "title" in entry and "url" in entry:
                    ref_num = len(references) + 1
                    ref_entry = {
                        "title": entry.get("title", ""),
                        "url": entry.get("url", ""),
                        "attribution": entry.get("attribution", ""),
                        "snippet": entry.get("snippet", ""),
                        "anchor_id": f"{anchor_prefix}{ref_num}",
                    }
                    # Avoid duplicates
                    if ref_entry not in references:
                        references.append(ref_entry)
    
    return processed_content, references


def format_references_section(references: List[Dict[str, Any]]) -> str:
    """Format references into a markdown section."""
    if not references:
        return ""

    lines: List[str] = []
    
    for i, ref in enumerate(references, 1):
        title = ref.get("title", "Untitled")
        url = ref.get("url", "")
        attribution = ref.get("attribution", "")
        snippet = ref.get("snippet", "")
        text = ref.get("text", "")
        ref_type = ref.get("type", "")
        pub_date = ref.get("pub_date", "")
        
        # Format reference entry with HTML anchor
        anchor_id = ref.get("anchor_id", f"ref-{i}")
        ref_line = f'<a id="{anchor_id}"></a>\n#### {i}. {title}'
        if ref_type:
            ref_line += f" ({ref_type})"
        if attribution:
            ref_line += f" - {attribution}"
        if pub_date:
            ref_line += f" - {pub_date}"
        if url:
            ref_line += f"  \n   [{url}]({url})"
        
        # Use text if available, otherwise snippet
        content = text if text else snippet
        if content:
            # Truncate content if too long
            if len(content) > 200:
                content = content[:200] + "..."
            ref_line += f"  \n   _{content}_"
        
        lines.append(ref_line)
        lines.append("")
    
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown rendering helpers
# ---------------------------------------------------------------------------

def _slugify_heading(text: str) -> str:
    """Create a stable anchor slug from text."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def _fence_block(content: str, language: str = "") -> str:
    """Render content inside a fenced code block."""
    opening = f"```{language}" if language else "```"
    return f"{opening}\n{content}\n```"


def _render_canvas_body(canvas: Dict[str, Any]) -> str:
    """Render a canvas/document artifact as metadata plus a fenced block."""
    name = str(canvas.get("name", "untitled"))
    canvas_type = str(canvas.get("type", "document"))
    content = str(canvas.get("content", ""))

    language = ""
    if canvas_type.startswith("code/"):
        language = canvas_type.split("/", 1)[1]
    elif canvas_type == "document":
        language = "markdown"
    else:
        language = "text"

    return "\n".join([
        f"**Name:** `{name}`",
        f"**Type:** `{canvas_type}`",
        "",
        _fence_block(content, language),
    ])


def _render_replacement_payload(replacement: Any, referenced_type: str | None) -> str:
    """Render update/replacement payloads in a readable fenced format."""
    if isinstance(replacement, dict) and "code" in replacement and "language" in replacement:
        return _fence_block(str(replacement["code"]), str(replacement["language"]))

    if isinstance(replacement, dict) and "type" in replacement:
        replacement_type = replacement["type"]
        if isinstance(replacement_type, str) and replacement_type.startswith("code/"):
            return _fence_block(str(replacement.get("content", "")), replacement_type.split("/", 1)[1])
        return _fence_block(json.dumps(replacement, indent=2), "json")

    if referenced_type and referenced_type.startswith("code/"):
        language = referenced_type.split("/", 1)[1]
        if isinstance(replacement, str):
            return _fence_block(replacement, language)
        return _fence_block(json.dumps(replacement, indent=2), language)

    if isinstance(replacement, dict):
        return _fence_block(json.dumps(replacement, indent=2), "json")
    if isinstance(replacement, str):
        return _fence_block(replacement)
    return _fence_block(str(replacement))


def _render_tool_usage_payload(content_json: Dict[str, Any]) -> str | None:
    """Render known tool/update payloads under a dedicated section."""
    updates = content_json.get("updates")
    if not isinstance(updates, list) or not updates:
        return None

    first_update = updates[0]
    if not isinstance(first_update, dict) or "replacement" not in first_update:
        return None

    replacement = first_update["replacement"]
    referenced_type = None
    content_references = content_json.get("content_references", [])
    if isinstance(content_references, list):
        for ref in content_references:
            if isinstance(ref, dict) and isinstance(ref.get("type"), str):
                referenced_type = ref["type"]
                break

    return _render_replacement_payload(replacement, referenced_type)


def _render_text_section(
    content: str, metadata: Dict[str, Any], anchor_prefix: str
) -> tuple[str, List[Dict[str, Any]]]:
    """Render plain text content and collect any references."""
    references: List[Dict[str, Any]] = []
    processed_content = content

    if metadata:
        if "citations" in metadata:
            processed_content, bracket_refs = extract_bracket_citations(
                processed_content, metadata, anchor_prefix
            )
            references.extend(bracket_refs)

        processed_content, other_refs = process_citations(processed_content, metadata, anchor_prefix)
        references.extend(other_refs)

    return processed_content, references


def _render_structured_content(
    content: Any, role: str, metadata: Dict[str, Any], anchor_prefix: str
) -> tuple[List[tuple[str, str]], List[Dict[str, Any]]]:
    """Render message content into labeled sections."""
    sections: List[tuple[str, str]] = []
    references: List[Dict[str, Any]] = []

    if isinstance(content, dict) and "type" in content and "content" in content:
        canvas_payload = _extract_canvas_payload(content)
        if canvas_payload:
            sections.append(("Artifact", _render_canvas_body(canvas_payload)))
            return sections, references

        content_type = content["type"]
        content_text = content["content"]
        if isinstance(content_type, str) and content_type.startswith("code/"):
            sections.append(("Payload", _fence_block(str(content_text), content_type.split("/", 1)[1])))
        else:
            rendered_text, references = _render_text_section(str(content_text), metadata, anchor_prefix)
            label = "Prompt" if role == "user" else "Response"
            sections.append((label, rendered_text))
        return sections, references

    if isinstance(content, list):
        content = "".join(str(item) for item in cast(List[Any], content))

    if not isinstance(content, str):
        sections.append(("Payload", _fence_block(json.dumps(content, indent=2), "json")))
        return sections, references

    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            content_json = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            content_json = None

        if isinstance(content_json, dict):
            canvas_payload = _extract_canvas_payload(content_json)
            if canvas_payload and (
                canvas_payload["type"].startswith("code/") or canvas_payload["type"] == "document"
            ):
                sections.append(("Artifact", _render_canvas_body(canvas_payload)))
                return sections, references

            tool_usage = _render_tool_usage_payload(content_json)
            if tool_usage is not None:
                sections.append(("Tool Usage", tool_usage))
                return sections, references

            sections.append(("Payload", _fence_block(json.dumps(content_json, indent=2), "json")))
            return sections, references

    rendered_text, references = _render_text_section(content, metadata, anchor_prefix)
    label = "Prompt" if role == "user" else "Response"
    sections.append((label, rendered_text))
    return sections, references


def _primary_message_kind(msg: Message, sections: List[tuple[str, str]], role: str) -> str:
    """Determine the primary semantic kind of a rendered message."""
    explicit_kind = msg.get("kind")
    if isinstance(explicit_kind, str) and explicit_kind:
        return explicit_kind

    if msg.get("type") == "canvas":
        return "artifact"

    if sections:
        label = sections[0][0].lower().replace(" ", "_")
        if label in {"prompt", "response", "thinking", "tool_usage", "artifact", "payload"}:
            return label

    return "prompt" if role == "user" else "response"


def _message_kind_title(kind: str, role: str) -> str:
    """Return the heading suffix for a message kind."""
    kind_map = {
        "prompt": "Prompt",
        "response": "Response",
        "thinking": "Thinking",
        "tool_usage": "Tool Usage",
        "artifact": "Artifact",
        "payload": "Payload",
    }
    if kind in kind_map:
        return kind_map[kind]
    return "Prompt" if role == "user" else "Response"


def _should_include_message_kind(
    kind: str, *, include_thinking: bool, include_tool_calls: bool
) -> bool:
    """Filter optional message kinds based on user-selected visibility."""
    if kind == "thinking":
        return include_thinking
    if kind == "tool_usage":
        return include_tool_calls
    return True


def _should_skip_mapping_message(
    *,
    metadata: Dict[str, Any],
    content_type: str | None,
    role: str | None,
    kind: str | None,
) -> bool:
    """Decide whether a raw mapping message should be dropped before rendering."""
    if metadata.get("is_user_system_message", False):
        return True

    if content_type in {"user_editable_context", "model_editable_context"}:
        return True

    if role == "system":
        return True

    is_hidden = bool(metadata.get("is_visually_hidden_from_conversation", False))
    if is_hidden and kind != "thinking":
        return True

    return False


def json_messages_to_markdown(
    messages: List[Message],
    title: str | None = None,
    *,
    include_thinking: bool = False,
    include_tool_calls: bool = False,
) -> str:
    """Convert list of ChatGPT message objects to a structured Markdown document."""
    document_title = title or "ChatGPT Conversation"
    md_lines = [f"# {document_title}", ""]
    rendered_messages: List[List[str]] = []
    toc_lines = ["## Table of Contents", ""]
    header_map = {"user": "User", "assistant": "Assistant", "system": "System"}

    visible_index = 0
    for msg in messages:
        role = str(msg.get("role", "assistant"))
        header = header_map.get(role, role.capitalize())

        if msg.get("type") == "canvas":
            sections = [("Artifact", _render_canvas_body(cast(Dict[str, Any], msg.get("canvas", {}))))]
            references: List[Dict[str, Any]] = []
        else:
            content = msg.get("content", "")
            metadata = cast(Dict[str, Any], msg.get("metadata", {}))
            base_anchor = f"msg-{visible_index + 1}-{_slugify_heading(header)}"
            sections, references = _render_structured_content(content, role, metadata, f"{base_anchor}-ref-")

        kind = _primary_message_kind(msg, sections, role)
        if not _should_include_message_kind(
            kind,
            include_thinking=include_thinking,
            include_tool_calls=include_tool_calls,
        ):
            continue

        visible_index += 1
        base_anchor = f"msg-{visible_index}-{_slugify_heading(header)}"
        anchor = f"{base_anchor}-{_slugify_heading(_message_kind_title(kind, role))}"
        heading = f"{visible_index}. {header} {_message_kind_title(kind, role)}"
        toc_lines.append(f"- [{heading}](#{anchor})")

        message_lines = [f'<a id="{anchor}"></a>', f"## {heading}", ""]

        for label, body in sections:
            message_lines.extend([f"### {label}", "", body, ""])

        if references:
            references_section = format_references_section(references)
            if references_section:
                message_lines.extend(["### References", "", references_section.strip(), ""])

        rendered_messages.append(message_lines)

    md_lines.extend(toc_lines)
    md_lines.append("")
    for message_lines in rendered_messages:
        md_lines.extend(message_lines)

    return "\n".join(md_lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _extract_conversation_title(data: Any) -> str | None:
    """Extract a conversation title from known export shapes."""
    if isinstance(data, dict):
        title = data.get("title")
        if isinstance(title, str) and title.strip():
            return title
        return None

    if isinstance(data, list) and data and isinstance(data[0], dict):
        title = data[0].get("title")
        if isinstance(title, str) and title.strip():
            return title

    return None

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
    parser.add_argument(
        "--include-thinking",
        action="store_true",
        help="Include assistant thinking/reasoning blocks in the output.",
    )
    parser.add_argument(
        "--include-tool-calls",
        action="store_true",
        help="Include tool call / tool usage blocks in the output.",
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

    conversation_title = _extract_conversation_title(data)

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

    markdown = json_messages_to_markdown(
        messages,
        title=conversation_title,
        include_thinking=args.include_thinking,
        include_tool_calls=args.include_tool_calls,
    )

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

            metadata = msg.get("metadata", {})
            message_obj: Message = {}
            
            # Extract author/role
            author = msg.get("author", {})
            if isinstance(author, dict) and "role" in author:
                message_obj["role"] = author.get("role", "unknown")
            if message_obj.get("role") == "tool":
                message_obj["kind"] = "tool_usage"
            recipient = msg.get("recipient")
            channel = msg.get("channel")
            if (
                message_obj.get("role") == "assistant"
                and (
                    metadata.get("tool_invoking_message")
                    or metadata.get("tool_invoked_message")
                    or channel == "commentary"
                    or (isinstance(recipient, str) and recipient != "all")
                )
            ):
                message_obj["kind"] = "tool_usage"
            
            # Extract content based on type
            content_obj = msg.get("content", {})
            content_text = ""
            content_kind: str | None = None
            content_type: str | None = None
            
            if isinstance(content_obj, dict):
                raw_content_type = content_obj.get("content_type", "unknown")
                content_type = raw_content_type if isinstance(raw_content_type, str) else "unknown"
                
                # Handle different content types
                if content_type == "text" and "parts" in content_obj:
                    # Standard text content with parts
                    parts = content_obj.get("parts", [])
                    content_text = "".join(str(part) for part in parts if part)
                elif content_type == "canvas":
                    # Canvas content
                    message_obj["type"] = "canvas"
                    message_obj["canvas"] = content_obj
                    if message_obj.get("kind") == "tool_usage":
                        message_obj.pop("kind", None)
                    content_text = f"Canvas: {content_obj.get('name', 'unnamed')}"
                elif content_type == "thoughts":
                    # Format thoughts in a more readable way
                    content_kind = "thinking"
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
                    content_kind = "thinking"
                    recap_content = content_obj.get("content", "")
                    if recap_content:
                        content_text = recap_content
                    else:
                        content_text = json.dumps(content_obj, indent=2)
                elif content_type == "code":
                    code_text = content_obj.get("text", "")
                    if isinstance(code_text, str):
                        canvas_payload = _extract_canvas_from_json_text(code_text)
                        if canvas_payload:
                            message_obj["type"] = "canvas"
                            message_obj["canvas"] = canvas_payload
                            if message_obj.get("kind") == "tool_usage":
                                message_obj.pop("kind", None)
                            content_text = f"Canvas: {canvas_payload['name']}"
                        else:
                            language = content_obj.get("language")
                            if isinstance(language, str) and language:
                                content_text = f"```{language}\n{code_text}\n```"
                            else:
                                content_text = code_text
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
            if content_kind:
                message_obj["kind"] = content_kind
            
            # Preserve metadata for citation processing
            if metadata:
                message_obj["metadata"] = metadata

            role_value = message_obj.get("role")
            kind_value = message_obj.get("kind")
            if _should_skip_mapping_message(
                metadata=cast(Dict[str, Any], metadata),
                content_type=content_type,
                role=role_value if isinstance(role_value, str) else None,
                kind=kind_value if isinstance(kind_value, str) else None,
            ):
                for child_id in node.get("children", []):
                    traverse(child_id)
                return
            
            # Check for canvas messages via content
            if (message_obj["role"] == "assistant" and 
                isinstance(message_obj["content"], str) and
                message_obj["content"].strip().startswith('{')):
                # Try to parse as JSON to see if it's a canvas
                try:
                    content_json = json.loads(message_obj["content"])
                    canvas_payload = _extract_canvas_payload(content_json)
                    if canvas_payload and (
                        canvas_payload["type"].startswith("code/") or canvas_payload["type"] == "document"
                    ):
                        # This is a canvas code block or document payload.
                        message_obj["type"] = "canvas"
                        message_obj["canvas"] = canvas_payload
                        if message_obj.get("kind") == "tool_usage":
                            message_obj.pop("kind", None)
                    # Handle content with updates/replacements
                    elif "updates" in content_json and isinstance(content_json["updates"], list):
                        updates = content_json["updates"]
                        if updates and isinstance(updates[0], dict) and "replacement" in updates[0]:
                            # Just extract and use the replacement directly
                            message_obj["kind"] = "tool_usage"
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
