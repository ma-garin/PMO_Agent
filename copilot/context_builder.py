from analytics.services import odc_distribution, summarize_defects
from tickets.models import Notification


def build_system_prompt(engagement) -> str:
    summary = summarize_defects(engagement)
    odc = odc_distribution(engagement)

    top_axes = []
    for axis_name, label in (
        ("defect_type", "欠陥タイプ"),
        ("trigger", "トリガー"),
        ("activity", "検出アクティビティ"),
    ):
        items = odc.get(axis_name, [])[:3]
        if items:
            joined = "、".join(f"{i['label']}({i['count']}件)" for i in items)
            top_axes.append(f"{label}: {joined}")

    unread = list(
        Notification.objects.filter(engagement=engagement, is_read=False)
        .order_by("-created_at")
        .values_list("message", flat=True)[:5]
    )

    lines = [
        "あなたは第三者検証会社のPMOを支援するアシスタントです。",
        f"案件名: {engagement.name}（ステータス: {engagement.get_status_display()}、進捗: {engagement.progress}%）",
        f"欠陥総数: {summary['total']}件（未クローズ: {summary['open']}件、期限超過: {summary['overdue']}件）",
    ]
    if summary["avg_open_age_days"] is not None:
        lines.append(f"未クローズ欠陥の平均滞留日数: {summary['avg_open_age_days']}日")
    if summary["density"] is not None:
        lines.append(f"欠陥密度: {summary['density']}")
    if top_axes:
        lines.append("ODC分布(確定済み上位): " + " / ".join(top_axes))
    if unread:
        lines.append("未読通知: " + " / ".join(unread))
    lines.append(
        "データに基づいて簡潔に回答してください。わからないことは推測せず、その旨を伝えてください。"
    )
    return "\n".join(lines)
