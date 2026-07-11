import csv

from django.core.management.base import BaseCommand, CommandError

from tpi.models import MaturityLevel, TpiCheckpoint, TpiKeyArea

VALID_LEVELS = {choice for choice, _ in MaturityLevel.choices}


class Command(BaseCommand):
    help = "CSVからTPIキーエリア・チェックポイントを取り込む"

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        try:
            f = open(csv_path, encoding="utf-8")
        except OSError as exc:
            raise CommandError(f"ファイルを開けません: {exc}") from exc

        key_area_count = 0
        checkpoint_count = 0
        order_by_key_area: dict[str, int] = {}

        with f:
            reader = csv.DictReader(f)
            for row_number, row in enumerate(reader, start=2):
                level = row.get("level", "").strip()
                key_area_name = row.get("key_area", "").strip()
                text = row.get("text", "").strip()

                if level not in VALID_LEVELS:
                    self.stderr.write(
                        f"{row_number}行目: 不正なlevel '{level}' をスキップしました"
                    )
                    continue
                if not key_area_name or not text:
                    self.stderr.write(f"{row_number}行目: key_areaまたはtextが空のためスキップ")
                    continue

                key_area, created = TpiKeyArea.objects.get_or_create(
                    name=key_area_name,
                    defaults={"order": len(order_by_key_area)},
                )
                if created:
                    key_area_count += 1
                    order_by_key_area[key_area_name] = key_area.order

                order = order_by_key_area.get(key_area_name, 0)
                _, checkpoint_created = TpiCheckpoint.objects.get_or_create(
                    key_area=key_area, level=level, text=text, defaults={"order": order}
                )
                if checkpoint_created:
                    checkpoint_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"キーエリア{key_area_count}件・チェックポイント{checkpoint_count}件を取込"
            )
        )
