import json

from llm.services import LlmError, run_completion

from .models import RiskItem

SUGGEST_SYSTEM = (
    "あなたは第三者検証会社の品質リスク分析の専門家です。"
    "与えられたデータのみを根拠に品質リスク候補を最大5件、"
    'JSON配列 [{"title":"...","description":"...","probability":1-5,"impact":1-5,"measurement":"..."}] '
    "の形式のみで出力してください。数値の捏造禁止。"
)


def _extract_json_array(text: str) -> list:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def suggest_risks(engagement, user=None) -> list[dict]:
    from analytics.services import odc_distribution, summarize_defects
    from tickets.models import Notification

    summary = summarize_defects(engagement)
    odc = odc_distribution(engagement)
    unread = list(
        Notification.objects.filter(engagement=engagement, is_read=False).values_list(
            "message", flat=True
        )[:10]
    )

    prompt = (
        f"案件名: {engagement.name}\n\n"
        f"欠陥サマリー: {summary}\n\n"
        f"ODC分布(確定済み): {odc}\n\n"
        f"未読通知: {unread}\n"
    )

    try:
        raw = run_completion(engagement, "risk_suggest", prompt, system=SUGGEST_SYSTEM, user=user)
    except LlmError:
        return []

    candidates = _extract_json_array(raw)
    results = []
    for item in candidates:
        if not isinstance(item, dict) or "title" not in item:
            continue
        results.append(
            {
                "title": str(item.get("title", ""))[:200],
                "description": str(item.get("description", "")),
                "probability": _clamp_1_5(item.get("probability", 3)),
                "impact": _clamp_1_5(item.get("impact", 3)),
                "measurement": str(item.get("measurement", ""))[:300],
            }
        )
    return results[:5]


def _clamp_1_5(value) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 3
    return max(1, min(5, value))


def risk_matrix(engagement) -> dict:
    """5(影響度)x5(発生確率)のセルごとのRiskItem集計(status!=closed)。"""
    risks = RiskItem.objects.filter(engagement=engagement).exclude(status=RiskItem.Status.CLOSED)
    grid = {(p, i): [] for p in range(1, 6) for i in range(1, 6)}
    for risk in risks:
        grid[(risk.probability, risk.impact)].append(risk)
    return grid
