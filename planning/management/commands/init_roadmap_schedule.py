from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from engagements.models import Engagement
from planning.models import Dependency, Schedule, WorkItem
from risks.management.commands.init_roadmap_project import PROJECT_NAME
from risks.models import ImprovementAction

# R-04〜R-06は実装・検証済み(main統合済み)、R-07〜R-10は未着手のため、
# 実際の状況に合わせて基準日を挟む形で日程を割り当てる。
SCHEDULE_OFFSETS = {
    "ROADMAP:R-04": (-12, -11),
    "ROADMAP:R-05": (-10, -9),
    "ROADMAP:R-06": (-8, -7),
    "ROADMAP:R-07": (-6, -3),
    "ROADMAP:R-08": (-2, 2),
    "ROADMAP:R-09": (1, 5),
    "ROADMAP:R-10": (4, 8),
}

_STATUS_TO_PROGRESS = {
    ImprovementAction.Status.DONE: 100,
    ImprovementAction.Status.IN_PROGRESS: 50,
    ImprovementAction.Status.PLANNED: 0,
    ImprovementAction.Status.CANCELLED: 0,
}

_ACTION_STATUS_TO_ITEM_STATUS = {
    ImprovementAction.Status.DONE: WorkItem.Status.DONE,
    ImprovementAction.Status.IN_PROGRESS: WorkItem.Status.IN_PROGRESS,
    ImprovementAction.Status.PLANNED: WorkItem.Status.PLANNED,
    ImprovementAction.Status.CANCELLED: WorkItem.Status.CANCELLED,
}


class Command(BaseCommand):
    help = "「PMO Agent R-04〜R-10 実装」案件のWBS/ガント日程を、改善アクションの実績に基づき冪等登録する"

    def add_arguments(self, parser):
        parser.add_argument("--name", default=PROJECT_NAME, help="対象の案件名")

    def handle(self, *args, **options):
        try:
            engagement = Engagement.objects.get(name=options["name"])
        except Engagement.DoesNotExist as exc:
            raise CommandError(
                f"案件が存在しません: {options['name']}"
                "（先に `python manage.py init_roadmap_project` を実行してください）"
            ) from exc

        today = timezone.localdate()
        schedule, _ = Schedule.objects.get_or_create(
            engagement=engagement, defaults={"status_date": today}
        )
        if schedule.status_date != today:
            schedule.status_date = today
            schedule.save(update_fields=["status_date"])

        previous_item = None
        created_count = 0
        for index, (code, (start_offset, finish_offset)) in enumerate(
            SCHEDULE_OFFSETS.items(), start=1
        ):
            try:
                action = ImprovementAction.objects.get(engagement=engagement, origin_note=code)
            except ImprovementAction.DoesNotExist:
                self.stderr.write(f"改善アクションが見つからないためスキップ: {code}")
                continue

            progress = _STATUS_TO_PROGRESS.get(action.status, 0)
            item_status = _ACTION_STATUS_TO_ITEM_STATUS.get(action.status, WorkItem.Status.PLANNED)
            start_date = today + timedelta(days=start_offset)
            finish_date = today + timedelta(days=finish_offset)

            item, created = WorkItem.objects.update_or_create(
                schedule=schedule,
                wbs_code=str(index),
                defaults={
                    "title": action.title,
                    "kind": WorkItem.Kind.TASK,
                    "status": item_status,
                    "start_date": start_date,
                    "finish_date": finish_date,
                    "progress": progress,
                    "owner": action.owner,
                    "improvement_action": action,
                    "sort_order": index,
                },
            )
            if created:
                created_count += 1

            if previous_item is not None:
                Dependency.objects.get_or_create(predecessor=previous_item, successor=item)
            previous_item = item

        self.stdout.write(
            self.style.SUCCESS(
                f"WBSを登録しました: engagement={engagement.pk} 新規={created_count}件 "
                f"合計={schedule.items.count()}件"
            )
        )
