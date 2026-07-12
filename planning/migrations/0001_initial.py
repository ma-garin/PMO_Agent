# Generated manually for the initial planning domain.
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("engagements", "0001_initial"),
        ("risks", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="Schedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status_date", models.DateField(verbose_name="基準日")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("engagement", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="schedule", to="engagements.engagement")),
            ],
        ),
        migrations.CreateModel(
            name="WorkItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("wbs_code", models.CharField(max_length=40, verbose_name="WBS")),
                ("title", models.CharField(max_length=200, verbose_name="作業名")),
                ("kind", models.CharField(choices=[("summary", "サマリー"), ("task", "タスク"), ("milestone", "マイルストーン")], default="task", max_length=20)),
                ("status", models.CharField(choices=[("planned", "計画"), ("in_progress", "実行中"), ("done", "完了"), ("cancelled", "中止")], default="planned", max_length=20)),
                ("start_date", models.DateField(verbose_name="開始日")),
                ("finish_date", models.DateField(verbose_name="終了日")),
                ("progress", models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name="進捗率(%)")),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("improvement_action", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="planning_item", to="risks.improvementaction")),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="planning_work_items", to=settings.AUTH_USER_MODEL)),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="children", to="planning.workitem")),
                ("schedule", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="planning.schedule")),
            ],
            options={"ordering": ["wbs_code", "sort_order", "pk"]},
        ),
        migrations.AddConstraint(model_name="workitem", constraint=models.UniqueConstraint(fields=("schedule", "wbs_code"), name="planning_unique_wbs")),
        migrations.AddConstraint(model_name="workitem", constraint=models.CheckConstraint(condition=models.Q(("finish_date__gte", models.F("start_date"))), name="planning_finish_gte_start")),
        migrations.AddConstraint(model_name="workitem", constraint=models.CheckConstraint(condition=models.Q(("progress__gte", 0), ("progress__lte", 100)), name="planning_progress_range")),
        migrations.CreateModel(
            name="Dependency",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("lag_days", models.IntegerField(default=0, verbose_name="ラグ(日)")),
                ("predecessor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="successor_links", to="planning.workitem")),
                ("successor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="predecessor_links", to="planning.workitem")),
            ],
        ),
        migrations.AddConstraint(model_name="dependency", constraint=models.UniqueConstraint(fields=("predecessor", "successor"), name="planning_unique_dependency")),
        migrations.AddConstraint(model_name="dependency", constraint=models.CheckConstraint(condition=models.Q(("predecessor", models.F("successor")), _negated=True), name="planning_dependency_not_self")),
    ]
