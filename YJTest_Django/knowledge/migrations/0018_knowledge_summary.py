from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0017_remove_document_image"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="KnowledgeSummary",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "title",
                    models.CharField(max_length=200, verbose_name="摘要标题"),
                ),
                ("content", models.TextField(verbose_name="沉淀内容")),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("query_answer", "查询问答沉淀"),
                            ("testcase_feedback", "用例反馈沉淀"),
                            ("manual", "手动添加"),
                        ],
                        default="query_answer",
                        max_length=30,
                        verbose_name="来源类型",
                    ),
                ),
                (
                    "is_vectorized",
                    models.BooleanField(default=False, verbose_name="已向量化"),
                ),
                (
                    "vector_id",
                    models.CharField(
                        blank=True, max_length=100, null=True, verbose_name="向量ID"
                    ),
                ),
                (
                    "quality_score",
                    models.FloatField(default=1.0, verbose_name="质量评分"),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="创建时间"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="更新时间"),
                ),
                (
                    "creator",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_summaries",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="创建人",
                    ),
                ),
                (
                    "knowledge_base",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="summaries",
                        to="knowledge.knowledgebase",
                        verbose_name="所属知识库",
                    ),
                ),
                (
                    "query_log",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="summaries",
                        to="knowledge.querylog",
                        verbose_name="来源查询日志",
                    ),
                ),
            ],
            options={
                "verbose_name": "知识沉淀",
                "verbose_name_plural": "知识沉淀",
                "ordering": ["-created_at"],
            },
        ),
    ]
