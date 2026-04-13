import os
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Initialize admin account, demo data, and default integrations."

    def _write(self, message, style_func=None):
        """Keep command output safe on Windows terminals with non-UTF-8 encodings."""
        encoding = (
            getattr(self.stdout, "encoding", None)
            or getattr(sys.stdout, "encoding", None)
            or "utf-8"
        )
        safe_message = message.encode(encoding, errors="ignore").decode(
            encoding, errors="ignore"
        )
        if style_func:
            self.stdout.write(style_func(safe_message))
        else:
            self.stdout.write(safe_message)

    def handle(self, *args, **options):
        admin_username = os.environ.get("DJANGO_ADMIN_USERNAME", "admin")
        admin_email = os.environ.get("DJANGO_ADMIN_EMAIL", "admin@example.com")
        admin_password = os.environ.get("DJANGO_ADMIN_PASSWORD", "admin123456")

        admin_user = User.objects.filter(username=admin_username).first()
        admin_created = False
        if admin_user:
            self._write(
                f'Admin user "{admin_username}" already exists, skipping creation.',
                self.style.WARNING,
            )
        else:
            admin_user = User.objects.create_superuser(
                username=admin_username,
                email=admin_email,
                password=admin_password,
            )
            admin_created = True
            self._write(
                (
                    "Created admin user:\n"
                    f"  username: {admin_username}\n"
                    f"  email: {admin_email}\n"
                    f"  password: {admin_password}"
                ),
                self.style.SUCCESS,
            )

        self._initialize_admin_prompts(admin_user, admin_created)
        default_api_key_value = self._initialize_default_api_key(admin_user)
        self._initialize_default_mcp_configs()
        demo_project = self._initialize_demo_project(admin_user)
        self._initialize_demo_user(demo_project)
        self._initialize_knowledge_global_config(admin_user)

        self._write(
            (
                "\n========================================\n"
                "System initialization completed\n"
                "========================================\n"
                f"Admin username: {admin_username}\n"
                f"Admin password: {admin_password}\n"
                f"Default API key: {default_api_key_value}\n"
                f"Demo project: {demo_project.name}\n"
                "========================================"
            ),
            self.style.SUCCESS,
        )

    def _initialize_default_api_key(self, admin_user):
        from api_keys.models import APIKey

        default_api_key_value = "yjtest-default-mcp-key-2026"
        key_name = "Default MCP Key (Auto-generated)"
        default_key = APIKey.objects.filter(user=admin_user, name=key_name).first()
        if default_key:
            self._write("Default API key already exists, skipping creation.", self.style.WARNING)
        else:
            APIKey.objects.create(
                user=admin_user,
                name=key_name,
                key=default_api_key_value,
                is_active=True,
            )
            self._write(
                (
                    "Created default API key:\n"
                    f"  name: {key_name}\n"
                    f"  key: {default_api_key_value}"
                ),
                self.style.SUCCESS,
            )
        return default_api_key_value

    def _initialize_default_mcp_configs(self):
        from mcp_tools.models import RemoteMCPConfig

        mcp_configs = [
            {
                "name": "YJTest-Tools",
                "url": "http://mcp:8006/mcp",
                "transport": "streamable-http",
            },
            {
                "name": "Playwright-MCP",
                "url": "http://playwright-mcp:8931/mcp",
                "transport": "streamable-http",
            },
        ]

        created_configs = []
        for config in mcp_configs:
            existing_config = RemoteMCPConfig.objects.filter(name=config["name"]).first()
            if existing_config:
                self._write(
                    f'MCP config "{config["name"]}" already exists, skipping creation.',
                    self.style.WARNING,
                )
                continue

            RemoteMCPConfig.objects.create(
                name=config["name"],
                url=config["url"],
                transport=config["transport"],
                is_active=True,
            )
            created_configs.append(config["name"])
            self._write(
                f'Created MCP config: {config["name"]} ({config["url"]})',
                self.style.SUCCESS,
            )

        if created_configs:
            self._write(
                f"Created {len(created_configs)} default MCP configs.",
                self.style.SUCCESS,
            )

    def _initialize_demo_project(self, admin_user):
        from projects.models import Project, ProjectMember

        demo_project_name = "演示项目 (Demo Project)"
        demo_project = Project.objects.filter(name=demo_project_name).first()
        if demo_project:
            self._write(
                f'Demo project "{demo_project_name}" already exists, skipping creation.',
                self.style.WARNING,
            )
        else:
            demo_project = Project.objects.create(
                name=demo_project_name,
                description=(
                    "Default demo workspace for YJTest.\n\n"
                    "This project is created automatically so new users can"
                    " enter the platform with a working example."
                ),
                creator=admin_user,
            )
            ProjectMember.objects.create(
                project=demo_project,
                user=admin_user,
                role="owner",
            )
            self._write(
                (
                    "Created demo project:\n"
                    f"  name: {demo_project.name}\n"
                    f"  id: {demo_project.id}"
                ),
                self.style.SUCCESS,
            )

        return demo_project

    def _initialize_admin_prompts(self, admin_user, admin_created):
        try:
            from prompts.services import initialize_user_prompts

            if admin_created:
                self._write(
                    "Admin prompts will be initialized by the user creation signal.",
                    self.style.SUCCESS,
                )
                return

            result = initialize_user_prompts(admin_user, force_update=False)
            created_count = result["summary"]["created_count"]
            skipped_count = result["summary"]["skipped_count"]
            if created_count > 0:
                self._write(
                    (
                        "Admin prompts initialized:\n"
                        f"  created: {created_count}\n"
                        f"  skipped: {skipped_count}"
                    ),
                    self.style.SUCCESS,
                )
            else:
                self._write("Admin prompts already exist, skipping.", self.style.WARNING)
        except Exception as exc:
            self._write(f"Failed to initialize admin prompts: {exc}", self.style.ERROR)

    def _initialize_demo_user(self, demo_project):
        """Ensure the default demo user can access the core product menus."""
        from django.contrib.auth.models import Permission
        from projects.models import ProjectMember

        demo_username = os.environ.get("DJANGO_DEMO_USERNAME", "EmTest")
        demo_email = os.environ.get("DJANGO_DEMO_EMAIL", "emtest@example.com")
        demo_password = os.environ.get("DJANGO_DEMO_PASSWORD", "EmTest123456")

        demo_user = User.objects.filter(username=demo_username).first()
        if demo_user is None:
            demo_user = User.objects.create_user(
                username=demo_username,
                email=demo_email,
                password=demo_password,
                first_name="Em",
                last_name="Test",
                is_active=True,
            )
            self._write(
                f"Created demo user: {demo_username} / {demo_password}",
                self.style.SUCCESS,
            )
        elif not demo_user.is_active:
            demo_user.is_active = True
            demo_user.save(update_fields=["is_active"])
            self._write(f'Demo user "{demo_username}" has been re-enabled.', self.style.SUCCESS)

        membership, membership_created = ProjectMember.objects.get_or_create(
            project=demo_project,
            user=demo_user,
            defaults={"role": "admin"},
        )
        if membership_created:
            self._write(
                f'Demo user "{demo_username}" added to demo project {demo_project.name}.',
                self.style.SUCCESS,
            )
        elif membership.role not in {"admin", "owner"}:
            membership.role = "admin"
            membership.save(update_fields=["role"])
            self._write(
                f'Demo user "{demo_username}" role upgraded to admin in demo project.',
                self.style.SUCCESS,
            )

        menu_permissions = {
            ("projects", "view_project"),
            ("requirements", "view_requirementdocument"),
            ("testcases", "view_testcase"),
            ("testcases", "view_testsuite"),
            ("testcases", "view_testexecution"),
            ("langgraph_integration", "view_llmconfig"),
            ("langgraph_integration", "view_chatsession"),
            ("langgraph_integration", "view_chatmessage"),
            ("ui_automation", "view_uimodule"),
            ("ui_automation", "view_uipage"),
            ("ui_automation", "view_uitestcase"),
            ("knowledge", "view_knowledgebase"),
            ("task_center", "view_scheduledtask"),
            ("auth", "view_user"),
            ("auth", "view_group"),
            ("auth", "view_permission"),
            ("api_keys", "view_apikey"),
            ("mcp_tools", "view_remotemcpconfig"),
            ("skills", "view_skill"),
        }

        # Grant the demo admin a complete UI automation workspace so every
        # visible tab can be opened and operated without hitting 403 errors.
        ui_automation_models = {
            "uimodule",
            "uipage",
            "uielement",
            "uipagesteps",
            "uipagestepsdetailed",
            "uitestcase",
            "uicasestepsdetailed",
            "uiexecutionrecord",
            "uipublicdata",
            "uienvironmentconfig",
            "uibatchexecutionrecord",
        }
        ui_automation_permissions = {
            ("ui_automation", f"{action}_{model_name}")
            for model_name in ui_automation_models
            for action in ("add", "change", "delete", "view")
        }
        default_permissions = menu_permissions | ui_automation_permissions

        permissions = list(
            Permission.objects.filter(
                content_type__app_label__in=[
                    app_label for app_label, _ in default_permissions
                ],
                codename__in=[codename for _, codename in default_permissions],
            ).select_related("content_type")
        )
        existing_permission_ids = set(
            demo_user.user_permissions.values_list("id", flat=True)
        )
        permissions_to_add = [
            permission
            for permission in permissions
            if (permission.content_type.app_label, permission.codename) in default_permissions
            and permission.id not in existing_permission_ids
        ]
        if permissions_to_add:
            demo_user.user_permissions.add(*permissions_to_add)
            self._write(
                f'Demo user "{demo_username}" granted {len(permissions_to_add)} menu permissions.',
                self.style.SUCCESS,
            )
        else:
            self._write(
                f'Demo user "{demo_username}" already has the default menu permissions.',
                self.style.WARNING,
            )

    def _initialize_knowledge_global_config(self, admin_user):
        try:
            from knowledge.models import KnowledgeGlobalConfig

            config = KnowledgeGlobalConfig.get_config()
            if config.updated_by is None:
                xinference_url = os.environ.get(
                    "XINFERENCE_API_BASE_URL", "http://xinference:9997"
                )
                config.embedding_service = "xinference"
                config.api_base_url = xinference_url
                config.api_key = ""
                config.model_name = os.environ.get(
                    "XINFERENCE_EMBEDDING_MODEL", "qwen3-vl-emb-2b"
                )
                config.reranker_service = "xinference"
                config.reranker_api_url = xinference_url
                config.reranker_api_key = ""
                config.reranker_model_name = os.environ.get(
                    "XINFERENCE_RERANKER_MODEL", "Qwen3-VL-Reranker-2B"
                )
                config.chunk_size = 1000
                config.chunk_overlap = 200
                config.updated_by = admin_user
                config.save()

                self._write(
                    (
                        "Initialized knowledge global config:\n"
                        f"  api_base_url: {config.api_base_url}\n"
                        f"  embedding_model: {config.model_name}\n"
                        f"  reranker_model: {config.reranker_model_name}"
                    ),
                    self.style.SUCCESS,
                )
            else:
                self._write(
                    "Knowledge global config already exists, skipping initialization.",
                    self.style.WARNING,
                )
        except Exception as exc:
            self._write(
                f"Failed to initialize knowledge global config: {exc}",
                self.style.ERROR,
            )
