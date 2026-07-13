"""サンプル案件「レジシステム消費税0%対応」を投入する(適度に遅延)。

デモ/検証用。冪等(既存なら更新)。基準日は投入時点の当日。
"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from engagements.models import Engagement
from pmo_agent.models import PmoTaskStore

ENGAGEMENT_NAME = "POS-TAX0 レジシステム 消費税0%対応"


def _iso(d: date) -> str:
    return d.isoformat()


def _build_tasks(today: date) -> list[dict]:
    """消費税0%対応プロジェクトのWBS。適度に遅延(遅延2/ブロック1、全体約52%)。"""

    def days(n: int) -> date:
        return today + timedelta(days=n)

    return [
        {
            "id": "WBS-01", "name": "要件定義（税率0%対応範囲の確定）", "owner": "PMO/業務",
            "phase": "要件定義", "status": "done", "progress": 100, "priority": "P1",
            "start": _iso(days(-40)), "due": _iso(days(-28)), "delay": 0, "rag": "g",
            "next": "確定要件を設計・テスト計画へ引き継ぎ済み。",
        },
        {
            "id": "WBS-02", "name": "税計算ロジック改修（0%区分の追加）", "owner": "開発リード",
            "phase": "開発", "status": "in_progress", "progress": 70, "priority": "P0",
            "start": _iso(days(-26)), "due": _iso(days(-2)), "delay": 3, "rag": "a",
            "next": "端数処理の仕様差異を会計チームと確定し、残実装を完了する。",
            "ball_holder": "開発リード", "ball_status": "dev_action",
            "ball_reason": "会計IFの端数丸め仕様の回答待ちで一部保留。",
            "related_task_ids": ["WBS-05"], "handoff_due": _iso(days(1)),
        },
        {
            "id": "WBS-03", "name": "レシート・帳票の税表示改修", "owner": "開発A",
            "phase": "開発", "status": "delayed", "progress": 45, "priority": "P1",
            "start": _iso(days(-20)), "due": _iso(days(-4)), "delay": 4, "rag": "r",
            "next": "軽減税率併記レイアウトの確認遅れ。デザイン確定を本日中に依頼。",
        },
        {
            "id": "WBS-04", "name": "商品マスタ税区分の一括更新", "owner": "業務B",
            "phase": "開発", "status": "in_progress", "progress": 55, "priority": "P1",
            "start": _iso(days(-18)), "due": _iso(days(5)), "delay": 0, "rag": "a",
            "next": "対象商品の抽出条件をレビューし、更新バッチのドライランを実施。",
        },
        {
            "id": "WBS-05", "name": "会計システム連携IF改修", "owner": "開発リード",
            "phase": "開発", "status": "blocked", "progress": 20, "priority": "P0",
            "start": _iso(days(-15)), "due": _iso(days(-1)), "delay": 5, "rag": "r",
            "next": "会計側の受入仕様未確定でブロック。CCBで意思決定を上げる。",
            "ball_holder": "会計チーム", "ball_status": "customer_reply",
            "ball_reason": "会計システム側の税区分マッピング回答待ち。",
            "related_task_ids": ["WBS-02"], "handoff_due": _iso(days(2)),
        },
        {
            "id": "WBS-06", "name": "結合テスト（税計算・帳票・連携）", "owner": "テストリード",
            "phase": "テスト", "status": "delayed", "progress": 30, "priority": "P0",
            "start": _iso(days(-8)), "due": _iso(days(6)), "delay": 2, "rag": "r",
            "next": "WBS-02/05の遅延で開始が後ろ倒し。ケース優先度を再整理し日次消化。",
        },
        {
            "id": "WBS-07", "name": "店舗受入テスト（UAT）", "owner": "店舗運用",
            "phase": "UAT", "status": "not_started", "progress": 0, "priority": "P1",
            "start": _iso(days(7)), "due": _iso(days(18)), "delay": 0, "rag": "a",
            "next": "UAT開始条件（結合テスト完了）を満たすか、開始日を再判定。",
        },
        {
            "id": "WBS-08", "name": "全店ロールアウト計画・切替", "owner": "PMO",
            "phase": "リリース", "status": "not_started", "progress": 0, "priority": "P1",
            "start": _iso(days(20)), "due": _iso(days(30)), "delay": 0, "rag": "b",
            "next": "施行日から逆算した切替計画のドラフトを作成。",
        },
    ]


class Command(BaseCommand):
    help = "サンプル案件『レジシステム消費税0%対応』(適度に遅延)を冪等投入する"

    def handle(self, *args, **options):
        User = get_user_model()
        owner = (
            User.objects.filter(is_superuser=True).order_by("pk").first()
            or User.objects.order_by("pk").first()
        )
        if owner is None:
            self.stderr.write("ユーザーが存在しません。先に seed_demo を実行してください。")
            return

        engagement, _ = Engagement.objects.get_or_create(
            name=ENGAGEMENT_NAME,
            defaults=dict(
                description="消費税0%施策に伴うPOSレジの税計算・帳票・会計連携の改修。開発の一部遅延と会計連携のブロックにより回復計画を検討中。",
                status="active",
                progress=52,
                owner=owner,
                llm_provider="ollama",
                llm_model="qwen2.5:3b",
            ),
        )
        engagement.members.add(owner)

        today = timezone.localdate()
        tasks = _build_tasks(today)
        store, _ = PmoTaskStore.objects.get_or_create(engagement=engagement)
        store.tasks = tasks
        store.saved_at = timezone.now().isoformat()
        store.updated_by = owner
        store.save()

        remaining = sum(1 for t in tasks if t["status"] != "done")
        delayed = sum(1 for t in tasks if t["status"] in ("delayed", "blocked") or t["delay"] > 0)
        self.stdout.write(
            self.style.SUCCESS(
                f"サンプル案件を投入しました: {engagement.name} "
                f"(WBS {len(tasks)}件 / 残 {remaining} / 遅延・ブロック {delayed})"
            )
        )
