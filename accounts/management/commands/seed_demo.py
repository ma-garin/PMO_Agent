import os

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from engagements.models import ActivityLog, Engagement


class Command(BaseCommand):
    help = "デモ用のユーザー・案件を冪等に投入する"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="本番(DEBUG=False)でも実行する。既定は開発環境でのみ実行可。",
        )

    def handle(self, *args, **options):
        # F-10(CWE-798): 本番で誤実行すると admin/password の弱い管理者が生まれるため、
        # DEBUG=False では明示の --force がない限り実行を拒否する。
        if not settings.DEBUG and not options.get("force"):
            self.stderr.write(
                "本番環境(DEBUG=False)ではseed_demoを実行できません。"
                "意図的に実行する場合は --force を付け、投入後に必ずパスワードを変更してください。"
            )
            return

        admin_password = os.environ.get("SEED_ADMIN_PASSWORD", "password")
        yuki_password = os.environ.get("SEED_YUKI_PASSWORD", "pmoagent-demo1")

        admin, admin_created = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@example.com", "is_staff": True, "is_superuser": True},
        )
        # 新規作成時は空パスワード(has_usable_passwordがTrueを返す罠)のため、createdで判定する
        if admin_created or not admin.has_usable_password():
            admin.set_password(admin_password)
            admin.save()

        yuki, yuki_created = User.objects.get_or_create(
            username="yuki",
            defaults={"email": "yuki.fujimagari@example.com", "first_name": "藤曲"},
        )
        if yuki_created or not yuki.has_usable_password():
            yuki.set_password(yuki_password)
            yuki.save()

        e1, _ = Engagement.objects.get_or_create(
            name="基幹システム刷新",
            defaults=dict(
                description="老朽化した基幹システムのリプレイス",
                status="active",
                progress=62,
                owner=yuki,
            ),
        )
        e1.members.add(yuki, admin)
        e2, _ = Engagement.objects.get_or_create(
            name="採用管理ツール導入",
            defaults=dict(
                description="新規採用管理SaaSの導入プロジェクト",
                status="on_hold",
                progress=18,
                owner=yuki,
            ),
        )
        e2.members.add(yuki)
        e3, _ = Engagement.objects.get_or_create(
            name="全社セキュリティ監査",
            defaults=dict(description="", status="completed", progress=100, owner=yuki),
        )
        e3.members.add(yuki)

        for message in [
            "「PR #3」をマージしました",
            "田中さんがUX監査にコメントしました",
            "タスク3件を完了しました",
        ]:
            ActivityLog.objects.get_or_create(engagement=e1, actor=yuki, message=message)

        self.stdout.write(self.style.SUCCESS("デモデータを投入しました(冪等)。"))
