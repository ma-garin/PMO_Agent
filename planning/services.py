"""WBS/ガントチャート描画用のジオメトリ計算。

analytics.services の SVG 生成パターン(convergence_svg_points 等)を踏襲する。
"""

from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone

CHART_WIDTH = 900
ROW_HEIGHT = 34
BAR_HEIGHT = 20


def _date_range(items) -> tuple[date, date]:
    start = min(item.start_date for item in items)
    finish = max(item.finish_date for item in items)
    if finish <= start:
        finish = start + timedelta(days=1)
    return start, finish


def gantt_chart_data(schedule) -> dict:
    """WorkItem一覧からバー・進捗ライン(稲妻線)・本日線のSVG座標を作る。

    進捗ライン(稲妻線)は、WBS表示順に各タスクの「実績進捗が示す位置」
    (開始日 + 期間 × 進捗率)を上から下へ結んだ折れ線。本日の垂直線と
    比較することで、どのタスクが予定より進んでいる/遅れているかが
    一目で分かる(ガントチャートの一般的な「進捗ライン」表現)。
    """
    items = list(schedule.items.select_related("owner").order_by("wbs_code", "sort_order", "pk"))
    if not items:
        return {
            "bars": [],
            "progress_line": "",
            "today_x": None,
            "width": CHART_WIDTH,
            "height": 0,
            "range_start": None,
            "range_end": None,
        }

    range_start, range_end = _date_range(items)
    total_days = max((range_end - range_start).days, 1)

    def x_for(d: date) -> float:
        return round((d - range_start).days / total_days * CHART_WIDTH, 1)

    bars = []
    progress_points = []
    for index, item in enumerate(items):
        y = index * ROW_HEIGHT
        bar_x = x_for(item.start_date)
        bar_end_x = x_for(item.finish_date)
        if bar_end_x <= bar_x:
            bar_end_x = bar_x + 6  # マイルストーン等、期間0でも見える幅を確保
        bar_width = bar_end_x - bar_x
        progress_width = round(bar_width * (item.progress / 100), 1)
        progress_x = round(bar_x + progress_width, 1)
        mid_y = round(y + BAR_HEIGHT / 2, 1)

        bars.append(
            {
                "item": item,
                "x": bar_x,
                "y": y,
                "width": round(bar_width, 1),
                "height": BAR_HEIGHT,
                "progress_width": progress_width,
                "label_y": round(y + BAR_HEIGHT / 2 + 4, 1),
            }
        )
        progress_points.append(f"{progress_x},{mid_y}")

    today = timezone.localdate()
    today_x = x_for(today) if range_start <= today <= range_end else None

    return {
        "bars": bars,
        "progress_line": " ".join(progress_points),
        "today_x": today_x,
        "width": CHART_WIDTH,
        "height": len(items) * ROW_HEIGHT,
        "range_start": range_start,
        "range_end": range_end,
    }
