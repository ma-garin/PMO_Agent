from django.db import migrations

DEFAULT_TEMPLATE_NAME = "標準テンプレート"
DEFAULT_SYSTEM_PROMPT = (
    "あなたは第三者検証会社の品質報告書を作成するアシスタントです。"
    "与えられたデータのみを根拠に、次のMarkdown章立てで出力してください。"
    "数値は与えられたものだけを使い、捏造しないでください。\n\n"
    "# 品質状況報告書\n"
    "## サマリー\n"
    "## 定量分析\n"
    "## テスト進捗\n"
    "## ODC分析所見\n"
    "## リスク状況\n"
    "## リスクと提言\n"
)


def seed_default_template(apps, schema_editor):
    ReportTemplate = apps.get_model("reports", "ReportTemplate")
    ReportTemplate.objects.get_or_create(
        name=DEFAULT_TEMPLATE_NAME,
        defaults={"system_prompt": DEFAULT_SYSTEM_PROMPT, "is_default": True},
    )


def remove_default_template(apps, schema_editor):
    ReportTemplate = apps.get_model("reports", "ReportTemplate")
    ReportTemplate.objects.filter(name=DEFAULT_TEMPLATE_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0002_reporttemplate"),
    ]

    operations = [
        migrations.RunPython(seed_default_template, remove_default_template),
    ]
