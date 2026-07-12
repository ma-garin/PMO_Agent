"""WBS/ガントチャート描画用のジオメトリ計算。

analytics.services の SVG 生成パターン(convergence_svg_points 等)を踏襲する。
"""

from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone

from .models import Dependency

CHART_WIDTH = 900
ROW_HEIGHT = 34
BAR_HEIGHT = 20
BASELINE_HEIGHT = 6
AXIS_HEIGHT = 26

# ズーム段階ごとの1日あたりピクセル数。"all"はNoneとし、範囲全体をCHART_WIDTHへ
# 収める(フィットさせる)ことを示す。日/週/月は固定幅にして横スクロールで見る。
ZOOM_PIXELS_PER_DAY = {
    "day": 36,
    "week": 16,
    "month": 5,
    "all": None,
}
DEFAULT_ZOOM = "day"
# タイムライン前後の余白日数。タスクが端に張り付かず、未来側の余裕も見えるようにする。
LEAD_DAYS = 4
TRAIL_DAYS = 14


def _date_range(items) -> tuple[date, date]:
    start = min(item.start_date for item in items)
    finish = max(item.finish_date for item in items)
    if finish <= start:
        finish = start + timedelta(days=1)
    return start, finish


def _axis_ticks(range_start: date, range_end: date, x_for, pixels_per_day: float) -> list[dict]:
    """ズーム倍率に応じて日/週/月いずれかの間隔で目盛りラベルを作る。"""
    ticks: list[dict] = []
    max_ticks = 120  # 異常に長い範囲でも無限ループ・過密表示にならないようにする安全弁

    if pixels_per_day >= 20:
        cursor = range_start
        step = timedelta(days=1)
        label_fmt = lambda d: f"{d.month}/{d.day}"  # noqa: E731
    elif pixels_per_day >= 6:
        # 範囲内で最初の月曜日から週単位
        offset = (7 - range_start.weekday()) % 7
        cursor = range_start + timedelta(days=offset) if offset else range_start
        step = timedelta(days=7)
        label_fmt = lambda d: f"{d.month}/{d.day}週"  # noqa: E731
    else:
        cursor = range_start.replace(day=1)
        if cursor < range_start:
            # 月初が範囲より前なら次の月初へ進める(単純に+32日して1日に丸める)
            nxt = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            cursor = nxt
        step = None  # 月は日数が不定なので下のループ内で計算する
        label_fmt = lambda d: f"{d.year}/{d.month}"  # noqa: E731

    count = 0
    while cursor <= range_end and count < max_ticks:
        ticks.append({"x": x_for(cursor), "label": label_fmt(cursor)})
        count += 1
        if step is not None:
            cursor = cursor + step
        else:
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)

    return ticks


def gantt_chart_data(schedule, zoom: str = DEFAULT_ZOOM) -> dict:
    """WorkItem一覧からバー・進捗ライン(稲妻線)・ベースライン(予実比較)・軸ラベルのSVG座標を作る。

    - タイムライン軸: zoom("day"/"week"/"month"/"all")に応じた間隔で日付ラベルを表示する。
      "all"以外は1日あたりのピクセル数を固定するため、範囲が広いほどSVG幅が広がり、
      呼び出し側(gantt-wrap)の横スクロールで閲覧する。
    - 予実比較: 各タスクの実バー(現在の予定/実績)の上に、ベースライン(当初計画)を
      細い帯で重ねて表示し、日程の乖離を視覚化する。
    - 進捗ライン(稲妻線): WBS表示順に各タスクの「実績進捗が示す位置」
      (開始日 + 期間 × 進捗率)を上から下へ結んだ折れ線。本日の垂直線と
      比較することで、どのタスクが予定より進んでいる/遅れているかが一目で分かる。
    """
    if zoom not in ZOOM_PIXELS_PER_DAY:
        zoom = DEFAULT_ZOOM

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
            "dependency_lines": [],
            "axis_ticks": [],
            "zoom": zoom,
        }

    range_start, range_end = _date_range(items)
    # ベースラインが実バーより外側にある場合も軸範囲に含める(予実の乖離が画面外に出ないように)
    baseline_starts = [i.baseline_start_date for i in items if i.baseline_start_date]
    baseline_finishes = [i.baseline_finish_date for i in items if i.baseline_finish_date]
    if baseline_starts:
        range_start = min(range_start, min(baseline_starts))
    if baseline_finishes:
        range_end = max(range_end, max(baseline_finishes))
    # タスク範囲の前後に余白を設ける(タスクが端に張り付かず、未来側の余裕を見せ、
    # 横スクロールで時間を辿れるようにする)。本日が範囲外の案件では余白は付くが
    # 本日線は従来どおり範囲内のときのみ表示する。
    range_start = range_start - timedelta(days=LEAD_DAYS)
    range_end = range_end + timedelta(days=TRAIL_DAYS)
    total_days = max((range_end - range_start).days, 1)

    fixed_pixels_per_day = ZOOM_PIXELS_PER_DAY[zoom]
    if fixed_pixels_per_day is None:
        pixels_per_day = CHART_WIDTH / total_days
        chart_width = CHART_WIDTH
    else:
        pixels_per_day = fixed_pixels_per_day
        chart_width = max(round(total_days * pixels_per_day), CHART_WIDTH)

    def x_for(d: date) -> float:
        return round((d - range_start).days * pixels_per_day, 1)

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

        baseline = None
        if item.baseline_start_date and item.baseline_finish_date:
            bl_x = x_for(item.baseline_start_date)
            bl_end_x = x_for(item.baseline_finish_date)
            if bl_end_x <= bl_x:
                bl_end_x = bl_x + 6
            slipped = item.finish_date > item.baseline_finish_date and item.status != "done"
            ahead = item.finish_date < item.baseline_finish_date and item.status == "done"
            baseline = {
                "x": bl_x,
                "width": round(bl_end_x - bl_x, 1),
                "y": y - 3,
                "height": BASELINE_HEIGHT,
                "slipped": slipped,
                "ahead": ahead,
            }

        bars.append(
            {
                "item": item,
                "x": bar_x,
                "y": y,
                "width": round(bar_width, 1),
                "height": BAR_HEIGHT,
                "progress_width": progress_width,
                "label_y": round(y + BAR_HEIGHT / 2 + 4, 1),
                "baseline": baseline,
            }
        )
        progress_points.append(f"{progress_x},{mid_y}")

    today = timezone.localdate()
    today_x = x_for(today) if range_start <= today <= range_end else None

    index_by_item_id = {item.pk: index for index, item in enumerate(items)}
    dependency_lines = []
    dependencies = Dependency.objects.filter(
        predecessor__schedule=schedule, successor__schedule=schedule
    ).select_related("predecessor", "successor")
    for dependency in dependencies:
        pred_index = index_by_item_id.get(dependency.predecessor_id)
        succ_index = index_by_item_id.get(dependency.successor_id)
        if pred_index is None or succ_index is None:
            continue
        pred_bar = bars[pred_index]
        succ_bar = bars[succ_index]
        start_point = (pred_bar["x"] + pred_bar["width"], pred_bar["y"] + BAR_HEIGHT / 2 + 6)
        end_point = (succ_bar["x"], succ_bar["y"] + BAR_HEIGHT / 2 + 6)
        mid_x = round((start_point[0] + end_point[0]) / 2, 1)
        end_x, end_y = round(end_point[0], 1), round(end_point[1], 1)
        arrow_points = f"{end_x},{end_y} {end_x - 6},{end_y - 4} {end_x - 6},{end_y + 4}"
        dependency_lines.append(
            {
                "points": (
                    f"{round(start_point[0], 1)},{round(start_point[1], 1)} "
                    f"{mid_x},{round(start_point[1], 1)} "
                    f"{mid_x},{end_y} "
                    f"{end_x},{end_y}"
                ),
                "arrow_points": arrow_points,
            }
        )

    axis_ticks = _axis_ticks(range_start, range_end, x_for, pixels_per_day)

    return {
        "bars": bars,
        "progress_line": " ".join(progress_points),
        "today_x": today_x,
        "width": chart_width,
        "height": len(items) * ROW_HEIGHT,
        "range_start": range_start,
        "range_end": range_end,
        "dependency_lines": dependency_lines,
        "axis_ticks": axis_ticks,
        "zoom": zoom,
    }
