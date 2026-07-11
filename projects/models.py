from django.conf import settings
from django.db import models


class Project(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "進行中"
        ON_HOLD = "on_hold", "保留中"
        COMPLETED = "completed", "完了"

    name = models.CharField("プロジェクト名", max_length=200)
    description = models.CharField("概要", max_length=300, blank=True)
    status = models.CharField(
        "ステータス", max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    progress = models.PositiveSmallIntegerField("進捗率(%)", default=0)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="projects", blank=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="owned_projects",
        on_delete=models.CASCADE,
    )
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name

    @property
    def member_count(self) -> int:
        return self.members.count()


class Task(models.Model):
    class Priority(models.TextChoices):
        HIGH = "high", "高"
        MEDIUM = "medium", "中"
        LOW = "low", "低"

    class Status(models.TextChoices):
        TODO = "todo", "未着手"
        IN_PROGRESS = "in_progress", "進行中"
        DONE = "done", "完了"
        OVERDUE = "overdue", "期限超過"

    project = models.ForeignKey(
        Project, related_name="tasks", on_delete=models.CASCADE
    )
    title = models.CharField("タスク名", max_length=200)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="assigned_tasks",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    priority = models.CharField(
        "優先度", max_length=10, choices=Priority.choices, default=Priority.MEDIUM
    )
    status = models.CharField(
        "状態", max_length=20, choices=Status.choices, default=Status.TODO
    )
    due_date = models.DateField("期限", null=True, blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        ordering = ["due_date", "-priority"]

    def __str__(self) -> str:
        return self.title


class ActivityLog(models.Model):
    project = models.ForeignKey(
        Project, related_name="activities", on_delete=models.CASCADE
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    message = models.CharField("内容", max_length=300)
    created_at = models.DateTimeField("発生日時", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.message
