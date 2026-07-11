from django.db import migrations


def encrypt_forward(apps, schema_editor):
    from config.crypto import encrypt

    TicketSource = apps.get_model("tickets", "TicketSource")
    for obj in TicketSource.objects.all():
        if obj.api_token:
            obj._api_token_encrypted = encrypt(obj.api_token)
            obj.save(update_fields=["_api_token_encrypted"])


def decrypt_backward(apps, schema_editor):
    from config.crypto import decrypt

    TicketSource = apps.get_model("tickets", "TicketSource")
    for obj in TicketSource.objects.all():
        if obj._api_token_encrypted:
            obj.api_token = decrypt(obj._api_token_encrypted)
            obj.save(update_fields=["api_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0003_add_api_token_encrypted"),
    ]

    operations = [
        migrations.RunPython(encrypt_forward, decrypt_backward),
    ]
