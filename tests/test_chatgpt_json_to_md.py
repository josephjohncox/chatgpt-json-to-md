import json
import unittest

from chatgpt_json_to_md import extract_messages_from_mapping, json_messages_to_markdown


class MarkdownRenderingTests(unittest.TestCase):
    def test_extracts_document_from_json_code_block(self) -> None:
        inner_document = {
            "name": "research_architecture",
            "type": "document",
            "content": "# Research Architecture\n\n## Purpose\n\nA practical architecture.",
        }
        mapping = {
            "root": {
                "parent": None,
                "children": [],
                "message": {
                    "author": {"role": "assistant"},
                    "content": {
                        "content_type": "code",
                        "language": "json",
                        "response_format_name": None,
                        "text": json.dumps(inner_document),
                    },
                },
            }
        }

        messages = extract_messages_from_mapping(mapping)
        markdown = json_messages_to_markdown(messages)

        self.assertIn("### Artifact", markdown)
        self.assertIn("```markdown", markdown)
        self.assertIn("# Research Architecture", markdown)
        self.assertNotIn('\\"name\\"', markdown)

    def test_uses_conversation_title_and_generates_toc(self) -> None:
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        markdown = json_messages_to_markdown(messages, title="My Conversation")

        self.assertTrue(markdown.startswith("# My Conversation"))
        self.assertIn("## Table of Contents", markdown)
        self.assertIn("- [1. User Prompt](#msg-1-user-prompt)", markdown)
        self.assertIn("- [2. Assistant Response](#msg-2-assistant-response)", markdown)
        self.assertIn("## 1. User Prompt", markdown)
        self.assertIn("## 2. Assistant Response", markdown)

    def test_fences_markdown_artifact_to_avoid_heading_collisions(self) -> None:
        messages = [
            {
                "role": "assistant",
                "type": "canvas",
                "canvas": {
                    "name": "architecture_notes",
                    "type": "document",
                    "content": "# Inner Heading\n\n## Nested Heading",
                },
            }
        ]

        markdown = json_messages_to_markdown(messages, title="Artifacts")

        self.assertIn("### Artifact", markdown)
        self.assertIn("```markdown\n# Inner Heading\n\n## Nested Heading\n```", markdown)

    def test_replaces_search_citation_tokens_with_links(self) -> None:
        messages = [
            {
                "role": "assistant",
                "content": "Result text citeturn0search18",
                "metadata": {
                    "content_references": [
                        {
                            "matched_text": "citeturn0search18",
                            "alt": "[1]",
                            "items": [
                                {
                                    "title": "Example Source",
                                    "url": "https://example.com/source",
                                    "snippet": "A source snippet.",
                                }
                            ],
                        }
                    ]
                },
            }
        ]

        markdown = json_messages_to_markdown(messages, title="Citations")

        self.assertNotIn("citeturn0search18", markdown)
        self.assertIn("Result text [1](#msg-1-assistant-ref-1)", markdown)
        self.assertIn('<a id="msg-1-assistant-ref-1"></a>', markdown)
        self.assertIn("### References", markdown)

    def test_reference_anchors_are_scoped_per_message(self) -> None:
        messages = [
            {
                "role": "assistant",
                "content": "First citeturn0search1",
                "metadata": {
                    "content_references": [
                        {
                            "matched_text": "citeturn0search1",
                            "alt": "[1]",
                            "items": [{"title": "First", "url": "https://example.com/1"}],
                        }
                    ]
                },
            },
            {
                "role": "assistant",
                "content": "Second citeturn0search2",
                "metadata": {
                    "content_references": [
                        {
                            "matched_text": "citeturn0search2",
                            "alt": "[1]",
                            "items": [{"title": "Second", "url": "https://example.com/2"}],
                        }
                    ]
                },
            },
        ]

        markdown = json_messages_to_markdown(messages, title="Scoped References")

        self.assertIn("First [1](#msg-1-assistant-ref-1)", markdown)
        self.assertIn("Second [1](#msg-2-assistant-ref-1)", markdown)
        self.assertIn('<a id="msg-1-assistant-ref-1"></a>', markdown)
        self.assertIn('<a id="msg-2-assistant-ref-1"></a>', markdown)

    def test_null_citation_alt_falls_back_to_generated_label(self) -> None:
        messages = [
            {
                "role": "assistant",
                "content": "Null alt citeturn0search7",
                "metadata": {
                    "content_references": [
                        {
                            "matched_text": "citeturn0search7",
                            "alt": None,
                            "items": [{"title": "Null Alt", "url": "https://example.com/null"}],
                        }
                    ]
                },
            }
        ]

        markdown = json_messages_to_markdown(messages, title="Null Alt")

        self.assertIn("Null alt [1](#msg-1-assistant-ref-1)", markdown)
        self.assertIn('<a id="msg-1-assistant-ref-1"></a>', markdown)

    def test_thinking_is_excluded_by_default(self) -> None:
        messages = [
            {"role": "assistant", "content": "Visible response"},
            {"role": "assistant", "content": "Hidden chain", "kind": "thinking"},
        ]

        markdown = json_messages_to_markdown(messages, title="Thinking")

        self.assertIn("Visible response", markdown)
        self.assertNotIn("Hidden chain", markdown)
        self.assertNotIn("Assistant Thinking", markdown)

    def test_thinking_can_be_included(self) -> None:
        messages = [
            {"role": "assistant", "content": "Visible response"},
            {"role": "assistant", "content": "Hidden chain", "kind": "thinking"},
        ]

        markdown = json_messages_to_markdown(
            messages,
            title="Thinking",
            include_thinking=True,
        )

        self.assertIn("## 2. Assistant Thinking", markdown)
        self.assertIn("Hidden chain", markdown)

    def test_tool_usage_is_excluded_by_default(self) -> None:
        messages = [
            {"role": "assistant", "content": "Normal answer"},
            {
                "role": "assistant",
                "content": '{"updates":[{"replacement":"tool output"}]}',
                "kind": "tool_usage",
            },
        ]

        markdown = json_messages_to_markdown(messages, title="Tools")

        self.assertIn("Normal answer", markdown)
        self.assertNotIn("tool output", markdown)
        self.assertNotIn("Assistant Tool Usage", markdown)

    def test_tool_usage_can_be_included(self) -> None:
        messages = [
            {"role": "assistant", "content": "Normal answer"},
            {
                "role": "assistant",
                "content": '{"updates":[{"replacement":"tool output"}]}',
                "kind": "tool_usage",
            },
        ]

        markdown = json_messages_to_markdown(
            messages,
            title="Tools",
            include_tool_calls=True,
        )

        self.assertIn("## 2. Assistant Tool Usage", markdown)

    def test_hidden_thinking_from_mapping_can_be_included(self) -> None:
        mapping = {
            "root": {
                "parent": None,
                "children": [],
                "message": {
                    "author": {"role": "assistant"},
                    "metadata": {"is_visually_hidden_from_conversation": True},
                    "content": {
                        "content_type": "thoughts",
                        "thoughts": [{"summary": "Plan", "content": "Reason privately"}],
                    },
                },
            }
        }

        messages = extract_messages_from_mapping(mapping)
        markdown = json_messages_to_markdown(messages, title="Mapped Thinking", include_thinking=True)

        self.assertIn("## 1. Assistant Thinking", markdown)
        self.assertIn("Reason privately", markdown)

    def test_tool_role_from_mapping_is_hidden_by_default(self) -> None:
        mapping = {
            "root": {
                "parent": None,
                "children": [],
                "message": {
                    "author": {"role": "tool"},
                    "content": {"content_type": "text", "parts": ["Tool trace"]},
                },
            }
        }

        messages = extract_messages_from_mapping(mapping)
        markdown = json_messages_to_markdown(messages, title="Mapped Tools")

        self.assertNotIn("Tool trace", markdown)

    def test_hidden_user_editable_context_is_excluded(self) -> None:
        mapping = {
            "root": {
                "parent": None,
                "children": [],
                "message": {
                    "author": {"role": "user"},
                    "metadata": {
                        "is_visually_hidden_from_conversation": True,
                        "is_user_system_message": True,
                        "can_save": False,
                    },
                    "content": {
                        "content_type": "user_editable_context",
                        "user_profile": "Role: Operations Research",
                        "user_instructions": "Be concise.",
                    },
                },
            }
        }

        messages = extract_messages_from_mapping(mapping)
        markdown = json_messages_to_markdown(messages, title="Context Filter")

        self.assertEqual(messages, [])
        self.assertNotIn("Operations Research", markdown)
        self.assertNotIn("Be concise.", markdown)

    def test_user_system_message_is_excluded_even_if_not_hidden(self) -> None:
        mapping = {
            "root": {
                "parent": None,
                "children": [],
                "message": {
                    "author": {"role": "user"},
                    "metadata": {
                        "is_user_system_message": True,
                    },
                    "content": {
                        "content_type": "text",
                        "parts": ["Internal context scaffold"],
                    },
                },
            }
        }

        messages = extract_messages_from_mapping(mapping)
        markdown = json_messages_to_markdown(messages, title="System Filter")

        self.assertEqual(messages, [])
        self.assertNotIn("Internal context scaffold", markdown)

    def test_model_editable_context_is_excluded(self) -> None:
        mapping = {
            "root": {
                "parent": None,
                "children": [],
                "message": {
                    "author": {"role": "assistant"},
                    "metadata": {
                        "message_type": "next",
                        "model_slug": "gpt-5-4-thinking",
                        "can_save": False,
                    },
                    "content": {
                        "content_type": "model_editable_context",
                        "model_set_context": "",
                        "repository": None,
                        "repo_summary": None,
                        "structured_context": None,
                    },
                },
            }
        }

        messages = extract_messages_from_mapping(mapping)
        markdown = json_messages_to_markdown(messages, title="Model Context Filter")

        self.assertEqual(messages, [])
        self.assertNotIn("model_editable_context", markdown)

    def test_commentary_tool_scaffold_is_hidden_by_default(self) -> None:
        mapping = {
            "root": {
                "parent": None,
                "children": [],
                "message": {
                    "author": {"role": "assistant"},
                    "recipient": "api_tool.list_resources",
                    "channel": "commentary",
                    "metadata": {
                        "tool_invoking_message": "Preparing app tools",
                        "tool_invoked_message": "Preparing app tools",
                        "can_save": False,
                    },
                    "content": {
                        "content_type": "code",
                        "language": "json",
                        "response_format_name": None,
                        "text": '{"path":"","only_tools":false,"refetch_tools":false}',
                    },
                },
            }
        }

        messages = extract_messages_from_mapping(mapping)
        markdown = json_messages_to_markdown(messages, title="Commentary Tools")

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].get("kind"), "tool_usage")
        self.assertNotIn("Preparing app tools", markdown)
        self.assertNotIn("api_tool.list_resources", markdown)

    def test_commentary_tool_scaffold_can_be_included(self) -> None:
        mapping = {
            "root": {
                "parent": None,
                "children": [],
                "message": {
                    "author": {"role": "assistant"},
                    "recipient": "api_tool.list_resources",
                    "channel": "commentary",
                    "metadata": {
                        "tool_invoking_message": "Preparing app tools",
                        "tool_invoked_message": "Preparing app tools",
                        "can_save": False,
                    },
                    "content": {
                        "content_type": "code",
                        "language": "json",
                        "response_format_name": None,
                        "text": '{"path":"","only_tools":false,"refetch_tools":false}',
                    },
                },
            }
        }

        messages = extract_messages_from_mapping(mapping)
        markdown = json_messages_to_markdown(
            messages,
            title="Commentary Tools",
            include_tool_calls=True,
        )

        self.assertIn("Assistant Tool Usage", markdown)
        self.assertIn("only_tools", markdown)

    def test_canmore_canvas_creation_is_rendered_as_artifact(self) -> None:
        mapping = {
            "root": {
                "parent": None,
                "children": [],
                "message": {
                    "author": {"role": "assistant"},
                    "recipient": "canmore.create_textdoc",
                    "channel": "commentary",
                    "metadata": {
                        "message_type": "next",
                        "can_save": False,
                    },
                    "content": {
                        "content_type": "code",
                        "language": "json",
                        "response_format_name": None,
                        "text": json.dumps(
                            {
                                "name": "research_architecture",
                                "type": "document",
                                "content": "# Research Architecture\n\n## Purpose\n\nA practical architecture.",
                            }
                        ),
                    },
                },
            }
        }

        messages = extract_messages_from_mapping(mapping)
        markdown = json_messages_to_markdown(messages, title="Canvas Creation")

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].get("type"), "canvas")
        self.assertNotEqual(messages[0].get("kind"), "tool_usage")
        self.assertIn("### Artifact", markdown)
        self.assertIn("```markdown", markdown)
        self.assertIn("# Research Architecture", markdown)


if __name__ == "__main__":
    unittest.main()
