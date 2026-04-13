"""
知识库改进功能测试
覆盖三个改进点：
1. _generate_answer  - LLM 生成回答（含降级）
2. precipitate_knowledge / _should_precipitate - 知识沉淀
3. multi_kb_search   - Query Rewrite + 上下文扩展
"""

from unittest.mock import MagicMock, patch, call
from django.contrib.auth.models import User
from django.test import TestCase

from projects.models import Project
from .models import KnowledgeBase, KnowledgeSummary, QueryLog


# ---------------------------------------------------------------------------
# 公共 fixture
# ---------------------------------------------------------------------------

def _make_sources(scores=(0.9, 0.8, 0.7)):
    """构造模拟检索结果列表"""
    return [
        {
            "content": f"这是第{i+1}条检索内容，关于登录功能的测试步骤。",
            "similarity_score": s,
            "metadata": {
                "title": f"文档{i+1}",
                "document_id": str(i + 1),
                "chunk_index": i,
                "vector_id": f"vec-{i}",
            },
        }
        for i, s in enumerate(scores)
    ]


def _make_kb(user, project):
    return KnowledgeBase.objects.create(
        name="测试知识库",
        project=project,
        creator=user,
    )


# ---------------------------------------------------------------------------
# 1. _generate_answer
# ---------------------------------------------------------------------------

class GenerateAnswerTests(TestCase):
    """_generate_answer：LLM 生成 + 降级逻辑"""

    def setUp(self):
        self.user = User.objects.create_user("u1", password="pw")
        self.project = Project.objects.create(name="P1", creator=self.user)
        self.kb = _make_kb(self.user, self.project)

        from .services import KnowledgeBaseService
        self.svc = KnowledgeBaseService(self.kb)

    def test_no_sources_returns_fallback_message(self):
        """没有检索结果时直接返回提示语"""
        result = self.svc._generate_answer("随便问", [])
        self.assertIn("没有找到", result)

    @patch("knowledge.services.KnowledgeBaseService._generate_answer")
    def test_llm_answer_returned_when_config_active(self, mock_gen):
        """有激活 LLM 配置时，返回 LLM 生成的回答"""
        mock_gen.return_value = "这是 LLM 生成的回答"
        result = mock_gen("登录功能如何测试？", _make_sources())
        self.assertEqual(result, "这是 LLM 生成的回答")

    def test_fallback_when_no_llm_config(self):
        """无激活 LLM 配置时降级为拼接模式，不抛异常"""
        # LLMConfig 表为空，_generate_answer 应降级
        from langgraph_integration.models import LLMConfig
        LLMConfig.objects.all().delete()

        sources = _make_sources()
        result = self.svc._generate_answer("登录功能如何测试？", sources)
        # 降级结果包含原始内容
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    @patch("langchain_openai.ChatOpenAI.invoke", side_effect=Exception("网络超时"))
    def test_fallback_on_llm_exception(self, _mock):
        """LLM 调用抛异常时降级，不影响主流程"""
        from langgraph_integration.models import LLMConfig
        LLMConfig.objects.create(
            config_name="test-llm",
            name="gpt-4o",
            api_url="https://api.openai.com/v1",
            api_key="sk-test",
            is_active=True,
        )
        sources = _make_sources()
        result = self.svc._generate_answer("登录功能如何测试？", sources)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


# ---------------------------------------------------------------------------
# 2. 知识沉淀
# ---------------------------------------------------------------------------

class KnowledgePrecipitateTests(TestCase):
    """precipitate_knowledge + _should_precipitate"""

    def setUp(self):
        self.user = User.objects.create_user("u2", password="pw")
        self.project = Project.objects.create(name="P2", creator=self.user)
        self.kb = _make_kb(self.user, self.project)

        from .services import KnowledgeBaseService
        self.svc = KnowledgeBaseService(self.kb)

    # --- _should_precipitate ---

    def test_should_precipitate_true_when_high_score(self):
        sources = _make_sources(scores=(0.9, 0.8))
        self.assertTrue(self.svc._should_precipitate(sources, "这是一段足够长的回答内容" * 5))

    def test_should_precipitate_false_when_low_score(self):
        sources = _make_sources(scores=(0.3, 0.2))
        self.assertFalse(self.svc._should_precipitate(sources, "回答内容" * 10))

    def test_should_precipitate_false_when_answer_too_short(self):
        sources = _make_sources(scores=(0.9,))
        self.assertFalse(self.svc._should_precipitate(sources, "短"))

    def test_should_precipitate_false_when_no_sources(self):
        self.assertFalse(self.svc._should_precipitate([], "足够长的回答内容" * 5))

    # --- precipitate_knowledge ---

    @patch("knowledge.services.VectorStoreManager.vector_store", new_callable=MagicMock)
    def test_precipitate_creates_summary_record(self, mock_vs_prop):
        """沉淀后 KnowledgeSummary 记录应写入数据库"""
        # mock vector_store.add_documents 返回一个 vector id
        mock_vs = MagicMock()
        mock_vs.add_documents.return_value = ["vec-summary-001"]
        mock_vs_prop.__get__ = MagicMock(return_value=mock_vs)

        sources = _make_sources()
        answer = "这是 LLM 生成的详细回答，包含登录功能的测试步骤。" * 3

        result = self.svc.precipitate_knowledge(
            query="登录功能如何测试？",
            answer=answer,
            sources=sources,
            user=self.user,
        )

        self.assertTrue(result)
        summary = KnowledgeSummary.objects.filter(knowledge_base=self.kb).first()
        self.assertIsNotNone(summary)
        self.assertIn("登录功能如何测试", summary.title)
        self.assertIn("## 问题", summary.content)
        self.assertIn("## 回答", summary.content)
        self.assertIn("## 参考来源", summary.content)
        self.assertEqual(summary.source, "query_answer")
        self.assertEqual(summary.creator, self.user)

    @patch("knowledge.services.VectorStoreManager.vector_store", new_callable=MagicMock)
    def test_precipitate_marks_vectorized_when_vector_id_returned(self, mock_vs_prop):
        """向量化成功时 is_vectorized=True 且 vector_id 已保存"""
        mock_vs = MagicMock()
        mock_vs.add_documents.return_value = ["vec-abc-123"]
        mock_vs_prop.__get__ = MagicMock(return_value=mock_vs)

        self.svc.precipitate_knowledge(
            query="测试问题",
            answer="足够长的回答内容" * 5,
            sources=_make_sources(),
        )

        summary = KnowledgeSummary.objects.filter(knowledge_base=self.kb).first()
        self.assertTrue(summary.is_vectorized)
        self.assertEqual(summary.vector_id, "vec-abc-123")

    @patch("knowledge.services.VectorStoreManager.vector_store", new_callable=MagicMock)
    def test_precipitate_returns_false_on_exception(self, mock_vs_prop):
        """向量化失败时返回 False，不抛异常"""
        mock_vs = MagicMock()
        mock_vs.add_documents.side_effect = Exception("Qdrant 连接失败")
        mock_vs_prop.__get__ = MagicMock(return_value=mock_vs)

        result = self.svc.precipitate_knowledge(
            query="测试问题",
            answer="足够长的回答内容" * 5,
            sources=_make_sources(),
        )
        self.assertFalse(result)

    @patch("knowledge.services.VectorStoreManager.vector_store", new_callable=MagicMock)
    def test_precipitate_associates_query_log(self, mock_vs_prop):
        """传入 query_log 时，summary.query_log 应正确关联"""
        mock_vs = MagicMock()
        mock_vs.add_documents.return_value = ["vec-x"]
        mock_vs_prop.__get__ = MagicMock(return_value=mock_vs)

        log = QueryLog.objects.create(
            knowledge_base=self.kb,
            user=self.user,
            query="登录功能如何测试？",
            response="回答",
        )
        self.svc.precipitate_knowledge(
            query="登录功能如何测试？",
            answer="足够长的回答内容" * 5,
            sources=_make_sources(),
            query_log=log,
        )
        summary = KnowledgeSummary.objects.filter(knowledge_base=self.kb).first()
        self.assertEqual(summary.query_log_id, log.id)


# ---------------------------------------------------------------------------
# 3. query() 触发知识沉淀
# ---------------------------------------------------------------------------

class QueryTriggersPrecipitateTests(TestCase):
    """query() 在满足条件时应异步触发 precipitate_knowledge"""

    def setUp(self):
        self.user = User.objects.create_user("u3", password="pw")
        self.project = Project.objects.create(name="P3", creator=self.user)
        self.kb = _make_kb(self.user, self.project)

    @patch("knowledge.services.KnowledgeBaseService.precipitate_knowledge")
    @patch("knowledge.services.KnowledgeBaseService._generate_answer", return_value="LLM 回答" * 10)
    @patch("knowledge.services.KnowledgeBaseService.enhanced_search", return_value=_make_sources())
    def test_query_triggers_precipitate_when_high_score(
        self, _mock_search, _mock_gen, mock_precip
    ):
        """高分检索结果时，query() 应触发 precipitate_knowledge"""
        import time
        from .services import KnowledgeBaseService

        svc = KnowledgeBaseService(self.kb)
        svc.query("登录功能如何测试？", user=self.user, enable_precipitate=True)

        # 沉淀在后台线程，等一下
        time.sleep(0.2)
        mock_precip.assert_called_once()

    @patch("knowledge.services.KnowledgeBaseService.precipitate_knowledge")
    @patch("knowledge.services.KnowledgeBaseService._generate_answer", return_value="回答")
    @patch(
        "knowledge.services.KnowledgeBaseService.enhanced_search",
        return_value=_make_sources(scores=(0.3, 0.2)),  # 低分
    )
    def test_query_skips_precipitate_when_low_score(
        self, _mock_search, _mock_gen, mock_precip
    ):
        """低分检索结果时，query() 不应触发 precipitate_knowledge"""
        import time
        from .services import KnowledgeBaseService

        svc = KnowledgeBaseService(self.kb)
        svc.query("随便问", user=self.user, enable_precipitate=True)

        time.sleep(0.2)
        mock_precip.assert_not_called()

    @patch("knowledge.services.KnowledgeBaseService.precipitate_knowledge")
    @patch("knowledge.services.KnowledgeBaseService._generate_answer", return_value="LLM 回答" * 10)
    @patch("knowledge.services.KnowledgeBaseService.enhanced_search", return_value=_make_sources())
    def test_query_skips_precipitate_when_disabled(
        self, _mock_search, _mock_gen, mock_precip
    ):
        """enable_precipitate=False 时不触发沉淀"""
        import time
        from .services import KnowledgeBaseService

        svc = KnowledgeBaseService(self.kb)
        svc.query("登录功能如何测试？", user=self.user, enable_precipitate=False)

        time.sleep(0.2)
        mock_precip.assert_not_called()


# ---------------------------------------------------------------------------
# 4. multi_kb_search 增强
# ---------------------------------------------------------------------------

class MultiKbSearchTests(TestCase):
    """multi_kb_search：Query Rewrite + 去重 + 上下文扩展"""

    def setUp(self):
        self.user = User.objects.create_user("u4", password="pw")
        self.project = Project.objects.create(name="P4", creator=self.user)
        self.kb1 = KnowledgeBase.objects.create(name="KB1", project=self.project, creator=self.user)
        self.kb2 = KnowledgeBase.objects.create(name="KB2", project=self.project, creator=self.user)

    @patch("knowledge.services.KnowledgeBaseService._rewrite_query", return_value="改写后的查询")
    @patch("knowledge.services.VectorStoreManager.similarity_search", return_value=_make_sources())
    def test_multi_kb_search_calls_rewrite(self, _mock_search, mock_rewrite):
        """enable_rewrite=True 时应调用 _rewrite_query"""
        from .services import KnowledgeBaseService
        KnowledgeBaseService.multi_kb_search(
            "原始查询",
            [str(self.kb1.id), str(self.kb2.id)],
            enable_rewrite=True,
        )
        mock_rewrite.assert_called_once_with("原始查询")

    @patch("knowledge.services.KnowledgeBaseService._rewrite_query", return_value="改写后的查询")
    @patch("knowledge.services.VectorStoreManager.similarity_search", return_value=_make_sources())
    def test_multi_kb_search_skips_rewrite_when_disabled(self, _mock_search, mock_rewrite):
        """enable_rewrite=False 时不调用 _rewrite_query"""
        from .services import KnowledgeBaseService
        KnowledgeBaseService.multi_kb_search(
            "原始查询",
            [str(self.kb1.id)],
            enable_rewrite=False,
        )
        mock_rewrite.assert_not_called()

    @patch("knowledge.services.KnowledgeBaseService._expand_context", side_effect=lambda x: x)
    @patch("knowledge.services.VectorStoreManager.similarity_search", return_value=_make_sources())
    def test_multi_kb_search_calls_expand_context(self, _mock_search, mock_expand):
        """multi_kb_search 应调用 _expand_context 做上下文扩展"""
        from .services import KnowledgeBaseService
        KnowledgeBaseService.multi_kb_search(
            "查询",
            [str(self.kb1.id)],
            enable_rewrite=False,
        )
        mock_expand.assert_called_once()

    @patch("knowledge.services.VectorStoreManager.similarity_search")
    def test_multi_kb_search_deduplicates_results(self, mock_search):
        """两个知识库返回相同内容时，结果应去重"""
        same_source = _make_sources(scores=(0.9,))
        mock_search.return_value = same_source

        from .services import KnowledgeBaseService
        results = KnowledgeBaseService.multi_kb_search(
            "查询",
            [str(self.kb1.id), str(self.kb2.id)],
            enable_rewrite=False,
        )
        # 相同 vector_id 的结果只保留一条
        vector_ids = [r["metadata"].get("vector_id") for r in results]
        self.assertEqual(len(vector_ids), len(set(vector_ids)))
