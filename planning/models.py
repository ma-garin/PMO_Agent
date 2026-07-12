from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class Schedule(models.Model):
    engagement = models.OneToOneField(
        "engagements.Engagement", on_delete=models.CASCADE, related_name="schedule"
    )
    status_date = models.DateField("基準日")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.engagement.name} ({self.status_date})"


class WorkItem(models.Model):
    class Kind(models.TextChoices):
        SUMMARY = "summary", "サマリー"
        TASK = "task", "タスク"
        MILESTONE = "milestone", "マイルストーン"

    class Status(models.TextChoices):
        PLANNED = "planned", "計画"
        IN_PROGRESS = "in_progress", "実行中"
        DONE = "done", "完了"
        CANCELLED = "cancelled", "中止"

    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name="items")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    improvement_action = models.OneToOneField(
        "risks.ImprovementAction",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="planning_item",
    )
    wbs_code = models.CharField("WBS", max_length=40)
    title = models.CharField("作業名", max_length=200)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.TASK)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    start_date = models.DateField("開始日")
    finish_date = models.DateField("終了日")
    progress = models.PositiveSmallIntegerField(
        "進捗率(%)", default=0, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="planning_work_items",
    )
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["wbs_code", "sort_order", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["schedule", "wbs_code"], name="planning_unique_wbs"),
            models.CheckConstraint(
                condition=Q(finish_date__gte=F("start_date")), name="planning_finish_gte_start"
            ),
            models.CheckConstraint(
                condition=Q(progress__gte=0, progress__lte=100), name="planning_progress_range"
            ),
        ]

    def clean(self):
        super().clean()
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError({"parent": "自身を親にはできません。"})
            if self.parent.schedule_id != self.schedule_id:
                raise ValidationError({"parent": "親は同じ案件のWBS項目に限ります。"})
            ancestor = self.parent
            seen = {self.pk} if self.pk else set()
            while ancestor:
                if ancestor.pk in seen:
                    raise ValidationError({"parent": "WBS階層を循環させることはできません。"})
                seen.add(ancestor.pk)
                ancestor = ancestor.parent
        if self.improvement_action_id:
            if self.improvement_action.engagement_id != self.schedule.engagement_id:
                raise ValidationError(
                    {"improvement_action": "改善アクションは同じ案件のものに限ります。"}
                )
        if self.kind == self.Kind.MILESTONE and self.start_date != self.finish_date:
            raise ValidationError({"finish_date": "マイルストーンの開始日と終了日は同日です。"})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def depth(self) -> int:
        return max(0, self.wbs_code.count("."))

    def __str__(self) -> str:
        return f"{self.wbs_code} {self.title}"


class Dependency(models.Model):
    predecessor = models.ForeignKey(
        WorkItem, on_delete=models.CASCADE, related_name="successor_links"
    )
    successor = models.ForeignKey(
        WorkItem, on_delete=models.CASCADE, related_name="predecessor_links"
    )
    lag_days = models.IntegerField("ラグ(日)", default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["predecessor", "successor"], name="planning_unique_dependency"
            ),
            models.CheckConstraint(
                condition=~Q(predecessor=F("successor")), name="planning_dependency_not_self"
            ),
        ]

    def clean(self):
        super().clean()
        if not self.predecessor_id or not self.successor_id:
            return
        if self.predecessor.schedule_id != self.successor.schedule_id:
            raise ValidationError("依存関係は同じ案件のWBS項目間に限ります。")
        if self.predecessor_id == self.successor_id:
            raise ValidationError("自身への依存は作成できません。")
        # successor から先を辿って predecessor に戻るなら循環する。
        pending = [self.successor_id]
        visited = set()
        while pending:
            current = pending.pop()
            if current == self.predecessor_id:
                raise ValidationError("循環する依存関係は作成できません。")
            if current in visited:
                continue
            visited.add(current)
            pending.extend(
                Dependency.objects.filter(predecessor_id=current)
                .exclude(pk=self.pk)
                .values_list("successor_id", flat=True)
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.predecessor} → {self.successor} (FS{self.lag_days:+d})"
