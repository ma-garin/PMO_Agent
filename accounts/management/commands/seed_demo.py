import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from analytics.models import OdcClassification
from engagements.models import ActivityLog, Engagement
from tickets.models import Notification, Ticket, TicketSource


class Command(BaseCommand):
    help = "デモ用のユーザー・案件・チケットを冪等に投入する"

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

        now = timezone.now()
        today = timezone.localdate()

        admin_password = os.environ.get("SEED_ADMIN_PASSWORD", "password")
        yuki_password = os.environ.get("SEED_YUKI_PASSWORD", "pmoagent-demo1")

        admin, admin_created = User.objects.get_or_create(
            username="admin", defaults={"email": "admin@example.com", "is_staff": True, "is_superuser": True}
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
            defaults=dict(description="老朽化した基幹システムのリプレイス", status="active", progress=62, owner=yuki),
        )
        e1.members.add(yuki, admin)
        e2, _ = Engagement.objects.get_or_create(
            name="採用管理ツール導入",
            defaults=dict(description="新規採用管理SaaSの導入プロジェクト", status="on_hold", progress=18, owner=yuki),
        )
        e2.members.add(yuki)
        e3, _ = Engagement.objects.get_or_create(
            name="全社セキュリティ監査",
            defaults=dict(description="", status="completed", progress=100, owner=yuki),
        )
        e3.members.add(yuki)

        src, _ = TicketSource.objects.get_or_create(
            engagement=e1,
            kind="jira",
            name="顧客JIRA(デモ)",
            defaults=dict(
                base_url="https://example.atlassian.net",
                project_key="PROJ",
                username="demo@example.com",
            ),
        )
        if not src.api_token:
            src.api_token = "dummy-token-not-real"
            src.save()

        tickets_data = [
            ("PROJ-241", "リリースノート v5.0 のレビュー", "高", "In Progress", "バグ", False, today, now - timedelta(hours=2)),
            ("PROJ-238", "監査指摘 A-01 の修正確認", "高", "In Progress", "バグ", False, today, now - timedelta(hours=5)),
            ("PROJ-244", "デザインシステムのダーク対応 方針決め", "中", "To Do", "Task", False, today, now - timedelta(days=1)),
            ("PROJ-236", "議事レビュの下書き", "低", "Done", "バグ", True, today - timedelta(days=1), now - timedelta(days=1)),
            ("PROJ-245", "export-project.sh の実案件検証", "低", "To Do", "Task", False, today + timedelta(days=2), now - timedelta(days=8)),
            ("PROJ-230", "旧システムのデータ移行検証", "中", "To Do", "バグ", False, today - timedelta(days=3), now - timedelta(days=9)),
            ("PROJ-101", "ログイン画面で全角入力時に落ちる", "中", "Open", "バグ", False, today - timedelta(days=12), now - timedelta(days=24)),
            ("PROJ-105", "帳票出力の日付が1日ずれる", "中", "Closed", "バグ", True, today - timedelta(days=18), now - timedelta(days=18)),
            ("PROJ-112", "検索結果の並び順が不安定", "低", "Open", "バグ", False, today - timedelta(days=20), now - timedelta(days=10)),
            ("PROJ-118", "CSV取込でメモリリーク", "高", "Closed", "バグ", True, today - timedelta(days=15), now - timedelta(days=6)),
            ("PROJ-125", "権限チェック漏れで403にならない", "高", "Open", "バグ", False, today - timedelta(days=12), now - timedelta(days=1)),
        ]
        for ext_id, summary, priority, status, ttype, is_done, due, updated in tickets_data:
            Ticket.objects.update_or_create(
                source=src,
                external_id=ext_id,
                defaults=dict(
                    external_url=f"https://example.atlassian.net/browse/{ext_id}",
                    summary=summary,
                    status=status,
                    is_done=is_done,
                    priority=priority,
                    ticket_type=ttype,
                    assignee_name="藤曲",
                    reporter_name="田中",
                    due_date=due,
                    source_created_at=now - timedelta(days=20),
                    source_updated_at=updated,
                    closed_at=updated if is_done else None,
                ),
            )

        first_defect = Ticket.objects.filter(source=src, ticket_type="バグ").order_by("external_id").first()
        if first_defect is not None:
            OdcClassification.objects.get_or_create(
                ticket=first_defect,
                defaults=dict(
                    defect_type="function",
                    trigger="coverage",
                    activity="system_test",
                    impact="major",
                    source="manual",
                    status="confirmed",
                    classified_by=yuki,
                ),
            )

        for message in ["「PR #3」をマージしました", "田中さんがUX監査にコメントしました", "タスク3件を完了しました"]:
            ActivityLog.objects.get_or_create(engagement=e1, actor=yuki, message=message)

        for ticket, kind, message in [
            (Ticket.objects.filter(source=src, external_id="PROJ-101").first(), Notification.Kind.STAGNANT, "「ログイン画面で全角入力時に落ちる」が5日以上更新されていません"),
            (Ticket.objects.filter(source=src, external_id="PROJ-230").first(), Notification.Kind.OVERDUE, "「旧システムのデータ移行検証」が期限を超過しています"),
            (Ticket.objects.filter(source=src, external_id="PROJ-112").first(), Notification.Kind.STAGNANT, "「検索結果の並び順が不安定」が5日以上更新されていません"),
        ]:
            if ticket is not None:
                Notification.objects.get_or_create(engagement=e1, ticket=ticket, kind=kind, defaults={"message": message})

        self.stdout.write(self.style.SUCCESS("デモデータを投入しました(冪等)。"))
