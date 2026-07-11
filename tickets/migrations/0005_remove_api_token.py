from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0004_encrypt_api_tokens"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="ticketsource",
            name="api_token",
        ),
    ]
