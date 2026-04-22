"""知识库异步任务"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='knowledge.process_document')
def process_document_task(self, document_id):
    """异步处理文档：加载、分块、向量化"""
    from .models import Document
    from .services import KnowledgeBaseService

    try:
        document = Document.objects.select_related('knowledge_base').get(id=document_id)
        service = KnowledgeBaseService(document.knowledge_base)
        service.process_document(document)
        logger.info(f"文档 {document_id} 处理完成")
    except Document.DoesNotExist:
        logger.error(f"文档 {document_id} 不存在")
    except Exception as e:
        logger.error(f"文档 {document_id} 处理失败: {e}", exc_info=True)
        try:
            Document.objects.filter(id=document_id).update(
                status='failed', error_message=str(e)[:500]
            )
        except Exception:
            pass
        raise


@shared_task(name='knowledge.cleanup_summaries')
def cleanup_summaries_task(
    max_per_kb: int = 500,
    min_quality: float = 0.5,
    max_age_days: int = 90,
):
    """
    定期清理知识沉淀，避免数据库无限增长。
    策略：
    1. 删除质量分低于 min_quality 的记录
    2. 删除超过 max_age_days 天的旧记录
    3. 每个知识库保留不超过 max_per_kb 条（按质量降序保留）
    """
    from django.utils import timezone
    from datetime import timedelta
    from .models import KnowledgeSummary, KnowledgeBase
    from .services import VectorStoreManager

    total_deleted = 0

    try:
        cutoff_date = timezone.now() - timedelta(days=max_age_days)

        # 1. 删除低质量记录
        low_quality = KnowledgeSummary.objects.filter(quality_score__lt=min_quality)
        count = low_quality.count()
        if count:
            _delete_summaries_with_vectors(low_quality)
            total_deleted += count
            logger.info(f"清理低质量沉淀: {count} 条")

        # 2. 删除过期记录
        expired = KnowledgeSummary.objects.filter(created_at__lt=cutoff_date)
        count = expired.count()
        if count:
            _delete_summaries_with_vectors(expired)
            total_deleted += count
            logger.info(f"清理过期沉淀: {count} 条")

        # 3. 每个知识库限量
        for kb in KnowledgeBase.objects.all():
            kb_summaries = KnowledgeSummary.objects.filter(
                knowledge_base=kb
            ).order_by("-quality_score", "-created_at")
            total = kb_summaries.count()
            if total > max_per_kb:
                # 保留前 max_per_kb 条，删除其余
                keep_ids = list(
                    kb_summaries.values_list("id", flat=True)[:max_per_kb]
                )
                overflow = KnowledgeSummary.objects.filter(
                    knowledge_base=kb
                ).exclude(id__in=keep_ids)
                count = overflow.count()
                _delete_summaries_with_vectors(overflow)
                total_deleted += count
                logger.info(f"知识库 {kb.name} 限量清理: {count} 条")

        logger.info(f"✅ 知识沉淀清理完成，共删除 {total_deleted} 条")
        return total_deleted

    except Exception as e:
        logger.error(f"知识沉淀清理失败: {e}", exc_info=True)
        return 0


def _delete_summaries_with_vectors(queryset):
    """删除沉淀记录，同时清理 Qdrant 向量"""
    from .models import KnowledgeSummary
    from .services import VectorStoreManager

    # 按知识库分组删除向量
    kb_vector_map = {}
    for summary in queryset.filter(is_vectorized=True).select_related("knowledge_base"):
        kb_id = str(summary.knowledge_base.id)
        if kb_id not in kb_vector_map:
            kb_vector_map[kb_id] = {"kb": summary.knowledge_base, "vector_ids": []}
        if summary.vector_id:
            kb_vector_map[kb_id]["vector_ids"].append(summary.vector_id)

    for kb_id, data in kb_vector_map.items():
        if data["vector_ids"]:
            try:
                manager = VectorStoreManager(data["kb"])
                manager.qdrant_client.delete(
                    collection_name=manager._get_collection_name(),
                    points_selector=data["vector_ids"],
                )
            except Exception as e:
                logger.warning(f"删除知识库 {kb_id} 向量失败: {e}")

    queryset.delete()
