from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0002_ticket_closed_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticketsource",
            name="_api_token_encrypted",
            field=models.TextField(
                blank=True,
                db_column="api_token_encrypted",
                default="",
                verbose_name="APIトークン(暗号化)",
            ),
            preserve_default=False,
        ),
    ]
