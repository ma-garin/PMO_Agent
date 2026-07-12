from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from audit.services import record
from engagements.models import Engagement
from risks.models import ImprovementAction
from risks.services import ROADMAP_ORIGIN_PREFIX, sync_roadmap_progress

PROJECT_NAME = "PMO Agent R-04〜R-10 実装"

ROADMAP_ACTIONS = (
    ("R-04", "重要処理の整合性", "承認の原子化、LLM利用枠、DB制約、監査ログを整備する。"),
    ("R-05", "同期・非同期ジョブの共通基盤", "状態遷移、再試行、冪等性、Outbox、共通ジョブ表示を整備する。"),
    ("R-06", "診断可能性と性能基準", "correlation ID、構造化ログ、クエリ予算、SLOを整備する。"),
    ("R-07", "アプリシェルとナビゲーション統一", "共通シェル、案件切替、ナビゲーション、設定hubを統一する。"),
    ("R-08", "画面パターンと操作フィードバック", "共通画面パターン、フィードバック、編集保護を整備する。"),
    ("R-09", "デザインシステムとアクセシビリティ", "デザイントークンとアクセシビリティ基盤を整備する。"),
    ("R-10", "実画面検証と回帰防止", "代表ジャーニーの実画面検証と回帰テストをCIへ追加する。"),
)


class Command(BaseCommand):
    help = "R-04〜R-10実装をPMO Agentの案件・改善アクションとして冪等登録する"

    def add_arguments(self, parser):
        parser.add_argument("--owner", default="admin", help="案件所有者のユーザー名")
        parser.add_argument("--name", default=PROJECT_NAME, help="作成する案件名")

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        try:
            owner = User.objects.get(username=options["owner"])
        except User.DoesNotExist as exc:
            raise CommandError(f"ユーザーが存在しません: {options['owner']}") from exc

        engagement, created = Engagement.objects.get_or_create(
            name=options["name"],
            defaults={
                "description": "docs/ROADMAP.md R-04〜R-10の実装・検証・レビュー進捗",
                "owner": owner,
                "status": Engagement.Status.ACTIVE,
            },
        )
        if engagement.owner_id != owner.pk:
            raise CommandError(
                f"同名案件は別の所有者です: {engagement.owner.username}"
            )
        engagement.members.add(owner)

        for roadmap_id, title, background in ROADMAP_ACTIONS:
            action, _ = ImprovementAction.objects.get_or_create(
                engagement=engagement,
                origin_note=f"{ROADMAP_ORIGIN_PREFIX}{roadmap_id}",
                defaults={
                    "title": f"{roadmap_id} {title}",
                    "background": background,
                    "owner": owner,
                },
            )
            changed_fields = []
            expected_title = f"{roadmap_id} {title}"
            for field, value in (
                ("title", expected_title),
                ("background", background),
                ("owner", owner),
            ):
                if getattr(action, field) != value:
                    setattr(action, field, value)
                    changed_fields.append(field)
            if changed_fields:
                action.save(update_fields=[*changed_fields, "updated_at"])

        progress = sync_roadmap_progress(engagement)
        record(
            owner,
            "roadmap_project_initialized",
            engagement,
            detail=f"R-04〜R-10 / progress={progress}%",
        )
        verb = "作成" if created else "更新"
        self.stdout.write(
            self.style.SUCCESS(
                f"案件を{verb}しました: id={engagement.pk} name={engagement.name} progress={progress}%"
            )
        )
