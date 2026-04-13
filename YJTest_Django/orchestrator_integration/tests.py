import os
import tempfile
from unittest.mock import patch

from django.test import SimpleTestCase
from django.test.utils import override_settings
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain.agents.middleware.types import ModelRequest, ModelResponse

from . import agent_loop_view
from .agent_loop_view import (
    _build_sanitized_messages,
    _extract_linked_image_urls,
    _is_linked_image_url_allowed,
    _normalize_uploaded_image_base64_list,
    _normalize_tool_result_for_model,
)
from .builtin_tools.skill_tools import (
    _build_skill_artifacts_dir,
    _collect_skill_artifacts,
    _build_skill_screenshots_dir,
    _finalize_skill_result,
    _prepare_skill_screenshots_dir,
    _sanitize_runtime_path_segment,
)
from .builtin_tools.output_sanitizer import strip_terminal_control_sequences
from .middleware_config import (
    ToolCallNameNormalizationMiddleware,
    get_user_friendly_llm_error,
    normalize_tool_call_names,
    _model_retry_should_retry,
)


class LLMFriendlyErrorTests(SimpleTestCase):
    def test_model_cooldown_error_returns_friendly_payload(self):
        exc = Exception(
            "Error code: 429 - {'error': {'code': 'model_cooldown', 'message': 'All credentials for model coder-model are cooling down', 'model': 'coder-model', 'reset_seconds': 27211, 'reset_time': '7h33m31s'}}"
        )

        result = get_user_friendly_llm_error(exc)

        if result is None:
            raise AssertionError("expected friendly error payload")
        self.assertEqual(result["status_code"], 429)
        self.assertEqual(result["error_code"], "model_cooldown")
        self.assertEqual(result["model"], "coder-model")
        self.assertEqual(result["reset_seconds"], 27211)
        self.assertEqual(result["reset_time"], "7h33m31s")
        self.assertIn("coder-model", result["message"])
        self.assertIn("7h33m31s", result["message"])

    def test_generic_rate_limit_error_returns_friendly_payload(self):
        exc = Exception("HTTP 429 Too Many Requests")

        result = get_user_friendly_llm_error(exc)

        if result is None:
            raise AssertionError("expected friendly error payload")
        self.assertEqual(result["status_code"], 429)
        self.assertEqual(result["error_code"], "rate_limit")
        self.assertEqual(result["message"], "当前模型服务请求过于频繁，请稍后重试。")

    def test_model_cooldown_error_will_not_retry(self):
        exc = Exception(
            "Error code: 429 - {'error': {'code': 'model_cooldown', 'message': 'All credentials for model coder-model are cooling down', 'model': 'coder-model', 'reset_seconds': 27211, 'reset_time': '7h33m31s'}}"
        )

        self.assertFalse(_model_retry_should_retry(exc))

    def test_cooling_down_text_without_code_still_maps_to_model_cooldown(self):
        exc = Exception(
            "RateLimitError: provider says model service is cooling down, retry-after: 6m0s"
        )

        result = get_user_friendly_llm_error(exc)

        if result is None:
            raise AssertionError("expected friendly cooldown payload")
        self.assertEqual(result["status_code"], 429)
        self.assertEqual(result["error_code"], "model_cooldown")
        self.assertIn("冷却中", result["message"])


class LinkedImageUrlExtractionTests(SimpleTestCase):
    def test_extract_plain_http_url_stops_before_chinese_description(self):
        text = "请访问 https://localhost:8080，准备注册信息：用户名testuser010、密码abcdef123"

        self.assertEqual(_extract_linked_image_urls(text), ["https://localhost:8080"])

    def test_extract_markdown_image_url_trims_wrapping_punctuation(self):
        text = "参考截图 ![image](https://example.com/demo.png)，然后继续分析"

        self.assertEqual(
            _extract_linked_image_urls(text),
            ["https://example.com/demo.png"],
        )

    def test_extract_invalid_unicode_netloc_does_not_raise(self):
        text = "异常链接 https://localhost:8080：准备注册信息：用户名testuser014"

        self.assertEqual(_extract_linked_image_urls(text), ["https://localhost:8080"])

    def test_extract_plain_http_url_stops_before_ascii_comma_description(self):
        text = "Open http://localhost:8080,then fill the registration form"

        self.assertEqual(_extract_linked_image_urls(text), ["http://localhost:8080"])

    def test_extract_plain_http_url_stops_before_closing_parenthesis_text(self):
        text = "查看截图 https://example.com/demo.png)后继续分析"

        self.assertEqual(
            _extract_linked_image_urls(text),
            ["https://example.com/demo.png"],
        )

    def test_allowlist_check_rejects_invalid_url_without_raising(self):
        with patch.object(
            agent_loop_view, "_LINKED_IMAGE_URL_ALLOWLIST", {"example.com"}
        ):
            self.assertFalse(
                _is_linked_image_url_allowed(
                    "https://localhost:8080：准备注册信息：用户名testuser014"
                )
            )


class UploadedImageNormalizationTests(SimpleTestCase):
    def test_normalize_uploaded_images_merges_legacy_and_array_fields(self):
        result = _normalize_uploaded_image_base64_list(
            ["img-a", " img-b ", "", "img-a"],
            "img-c",
        )

        self.assertEqual(result, ["img-a", "img-b", "img-c"])

    def test_normalize_uploaded_images_accepts_legacy_single_image_only(self):
        result = _normalize_uploaded_image_base64_list(None, " legacy-img ")

        self.assertEqual(result, ["legacy-img"])


class MessageSanitizationTests(SimpleTestCase):
    def test_normalize_tool_call_names_collapses_repeated_tool_name(self):
        repeated_name = "knowledge_search" * 4
        tool_calls = [
            {
                "name": repeated_name,
                "args": {"query": "AgentOne APP"},
                "id": "call-1",
                "type": "tool_call",
            }
        ]

        normalized_tool_calls, changed_count = normalize_tool_call_names(
            tool_calls,
            ["knowledge_search", "read_skill_content"],
        )

        self.assertEqual(changed_count, 1)
        self.assertEqual(normalized_tool_calls[0]["name"], "knowledge_search")

    def test_sanitized_messages_convert_multimodal_human_for_text_only_model(self):
        messages = [
            HumanMessage(
                content=[
                    {"type": "text", "text": "请分析这个页面"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,abc"},
                    },
                ]
            )
        ]

        clean_messages, fix_count = _build_sanitized_messages(messages)

        self.assertEqual(fix_count, 1)
        self.assertEqual(clean_messages[0].content, "请分析这个页面\n[1 image input(s) omitted for text-only model]")

    def test_sanitized_messages_keep_multimodal_human_for_vision_model(self):
        content = [
            {"type": "text", "text": "请分析这个页面"},
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,abc"},
            },
        ]
        messages = [HumanMessage(content=content)]

        clean_messages, fix_count = _build_sanitized_messages(
            messages, allow_multimodal_human=True
        )

        self.assertEqual(fix_count, 0)
        self.assertEqual(clean_messages[0].content, content)

    def test_sanitized_messages_convert_non_string_ai_content_even_for_vision_model(self):
        messages = [AIMessage(content=[{"type": "text", "text": "中间结果"}])]

        clean_messages, fix_count = _build_sanitized_messages(
            messages, allow_multimodal_human=True
        )

        self.assertEqual(fix_count, 1)
        self.assertEqual(clean_messages[0].content, "中间结果")

    def test_sanitized_messages_replace_non_string_tool_message_content(self):
        messages = [
            AIMessage(
                content="调用工具",
                tool_calls=[
                    {
                        "name": "get_project_list",
                        "args": {},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content=[{"type": "text", "text": '[{"project_id": 1}]'}],
                tool_call_id="call-1",
                name="get_project_list",
            )
        ]

        clean_messages, fix_count = _build_sanitized_messages(messages)

        self.assertEqual(fix_count, 1)
        self.assertEqual(
            clean_messages[1].content,
            "[Tool output removed: content was invalid or too large]",
        )

    def test_sanitized_messages_normalize_repeated_tool_call_names(self):
        repeated_name = "knowledge_search" * 4
        messages = [
            AIMessage(
                content="调用知识库",
                tool_calls=[
                    {
                        "name": repeated_name,
                        "args": {"query": "AgentOne APP"},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="检索成功",
                tool_call_id="call-1",
                name=repeated_name,
            ),
        ]

        clean_messages, fix_count = _build_sanitized_messages(
            messages,
            available_tool_names=["knowledge_search", "read_skill_content"],
        )

        self.assertEqual(fix_count, 2)
        self.assertEqual(clean_messages[0].tool_calls[0]["name"], "knowledge_search")
        self.assertEqual(clean_messages[1].name, "knowledge_search")

    def test_normalize_tool_result_preserves_artifact_for_content_and_artifact_tools(self):
        tool = type(
            "DummyTool",
            (),
            {"response_format": "content_and_artifact"},
        )()
        raw_content = [{"type": "text", "text": '[{"project_id": 1}]'}]

        normalized = _normalize_tool_result_for_model(tool, raw_content)

        self.assertEqual(normalized[0], '[{"project_id": 1}]')
        self.assertEqual(normalized[1], raw_content)


class ToolCallNameNormalizationMiddlewareTests(SimpleTestCase):
    def test_wrap_model_call_normalizes_repeated_tool_name_in_ai_message(self):
        middleware = ToolCallNameNormalizationMiddleware()
        repeated_name = "add_functional_case" * 3
        request = ModelRequest(
            model=object(),
            messages=[],
            tools=[
                {"name": "knowledge_search"},
                {"name": "add_functional_case"},
            ],
        )

        def handler(_request):
            return ModelResponse(
                result=[
                    AIMessage(
                        content="开始保存用例",
                        tool_calls=[
                            {
                                "name": repeated_name,
                                "args": {"title": "用例1"},
                                "id": "call-1",
                                "type": "tool_call",
                            }
                        ],
                    )
                ]
            )

        response = middleware.wrap_model_call(request, handler)

        self.assertIsInstance(response, ModelResponse)
        self.assertEqual(response.result[0].tool_calls[0]["name"], "add_functional_case")


class SkillScreenshotDirectoryTests(SimpleTestCase):
    def test_sanitize_runtime_path_segment_blocks_path_traversal(self):
        self.assertEqual(
            _sanitize_runtime_path_segment("../case/89", "_default"),
            "__case_89",
        )

    def test_build_skill_screenshots_dir_uses_runtime_media_root(self):
        with tempfile.TemporaryDirectory() as temp_media_root:
            with override_settings(MEDIA_ROOT=temp_media_root):
                screenshots_dir = _build_skill_screenshots_dir(1, "89")

        self.assertTrue(screenshots_dir.endswith("skill_runtime/screenshots/1/89"))
        self.assertNotIn("/skills/1/11/", screenshots_dir)

    def test_build_skill_screenshots_dir_keeps_path_inside_media_root(self):
        with tempfile.TemporaryDirectory() as temp_media_root:
            with override_settings(MEDIA_ROOT=temp_media_root):
                screenshots_dir = _build_skill_screenshots_dir(1, "../case/89")

        self.assertTrue(screenshots_dir.startswith(temp_media_root))
        self.assertNotIn("..", screenshots_dir)

    def test_prepare_skill_screenshots_dir_clears_stale_chat_session(self):
        with tempfile.TemporaryDirectory() as temp_media_root:
            with override_settings(MEDIA_ROOT=temp_media_root):
                screenshots_dir = _prepare_skill_screenshots_dir(1, "89", "chat-a")
                stale_file = os.path.join(screenshots_dir, "old.png")
                with open(stale_file, "w", encoding="utf-8") as f:
                    f.write("old screenshot")

                refreshed_dir = _prepare_skill_screenshots_dir(1, "89", "chat-b")
                marker_path = os.path.join(refreshed_dir, ".chat_session")

                self.assertEqual(refreshed_dir, screenshots_dir)
                self.assertFalse(os.path.exists(stale_file))
                with open(marker_path, "r", encoding="utf-8") as f:
                    self.assertEqual(f.read().strip(), "chat-b")

    def test_build_skill_artifacts_dir_uses_runtime_media_root(self):
        with tempfile.TemporaryDirectory() as temp_media_root:
            with override_settings(MEDIA_ROOT=temp_media_root):
                artifacts_dir = _build_skill_artifacts_dir(1, "session-1")

        self.assertTrue(artifacts_dir.endswith("skill_runtime/artifacts/1/session-1"))
        self.assertNotIn("/skills/1/11/", artifacts_dir)

    def test_collect_skill_artifacts_detects_named_generated_file(self):
        with tempfile.TemporaryDirectory() as temp_media_root:
            with override_settings(MEDIA_ROOT=temp_media_root, MEDIA_URL="/media/"):
                skill_dir = os.path.join(temp_media_root, "skills", "1", "11")
                os.makedirs(skill_dir, exist_ok=True)
                generated_file = os.path.join(skill_dir, "order-payment-flow.drawio")
                with open(generated_file, "w", encoding="utf-8") as f:
                    f.write("<mxfile></mxfile>")

                artifacts = _collect_skill_artifacts(
                    "已帮你生成 draw.io 文件：order-payment-flow.drawio",
                    skill_dir=skill_dir,
                    artifacts_dir=os.path.join(temp_media_root, "skill_runtime", "artifacts", "1", "s1"),
                    artifacts_before={},
                )

        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["name"], "order-payment-flow.drawio")
        self.assertEqual(artifacts[0]["url"], "/media/skills/1/11/order-payment-flow.drawio")

    def test_finalize_skill_result_wraps_output_with_file_payload(self):
        with tempfile.TemporaryDirectory() as temp_media_root:
            with override_settings(MEDIA_ROOT=temp_media_root, MEDIA_URL="/media/"):
                skill_dir = os.path.join(temp_media_root, "skills", "1", "11")
                os.makedirs(skill_dir, exist_ok=True)
                generated_file = os.path.join(skill_dir, "demo.drawio")
                with open(generated_file, "w", encoding="utf-8") as f:
                    f.write("<mxfile></mxfile>")

                wrapped = _finalize_skill_result(
                    "已生成文件 demo.drawio",
                    skill_dir=skill_dir,
                    artifacts_dir=os.path.join(temp_media_root, "skill_runtime", "artifacts", "1", "s1"),
                    artifacts_before={},
                )

        self.assertIn('"type": "file"', wrapped)
        self.assertIn('/media/skills/1/11/demo.drawio', wrapped)


class TerminalOutputSanitizerTests(SimpleTestCase):
    def test_strip_terminal_control_sequences_removes_ansi_color_codes(self):
        raw = "\x1b[32m✓\x1b[0m Browser closed"

        self.assertEqual(strip_terminal_control_sequences(raw), "✓ Browser closed")
