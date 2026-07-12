"""暗号鍵ローテーション: 全TicketSourceのトークンを現行鍵で再暗号化する(F-14)。

手順:
1. .env に FIELD_ENCRYPTION_KEYS="新鍵,旧鍵" を設定(新鍵を先頭)。
2. このコマンドを実行(旧鍵で復号→新鍵で再暗号化)。
3. 動作確認後、.env を FIELD_ENCRYPTION_KEYS="新鍵" のみに更新し旧鍵を破棄。
"""

from django.core.management.base import BaseCommand

from tickets.models import TicketSource


class Command(BaseCommand):
    help = "全TicketSourceのAPIトークンを現行(先頭)の暗号鍵で再暗号化する"

    def handle(self, *args, **options):
        rotated = 0
        skipped = 0
        for source in TicketSource.objects.all():
            token = source.api_token  # MultiFernetが旧鍵含めて復号
            if not token:
                skipped += 1
                continue
            source.api_token = token  # 先頭(新)鍵で再暗号化
            source.save(update_fields=["_api_token_encrypted"])
            rotated += 1
        self.stdout.write(
            f"再暗号化: {rotated}件、スキップ(空トークン): {skipped}件"
        )
