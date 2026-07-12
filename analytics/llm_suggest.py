import json

from llm.prompt_utils import EXTERNAL_DATA_GUARD, wrap_external
from llm.services import LlmError, run_completion

from .models import OdcClassification

SUGGEST_SYSTEM = (
    "あなたはソフトウェア品質保証の専門家です。欠陥チケットをODC分類します。"
    "必ずJSONのみで回答してください。" + EXTERNAL_DATA_GUARD
)

_AXIS_CHOICES = {
    "defect_type": OdcClassification.DefectType.choices,
    "trigger": OdcClassification.Trigger.choices,
    "activity": OdcClassification.Activity.choices,
    "impact": OdcClassification.Impact.choices,
}


def build_prompt(ticket) -> str:
    choices_text = "\n".join(
        f"{axis}: " + ", ".join(f"{value}({label})" for value, label in choices)
        for axis, choices in _AXIS_CHOICES.items()
    )
    # チケット由来のテキスト(外部起票者が書ける)は外部データとして区切る
    ticket_data = wrap_external(
        f"タイトル: {ticket.summary}\n"
        f"本文: {ticket.description[:1000]}\n"
        f"状態: {ticket.status}\n"
        f"優先度: {ticket.priority}"
    )
    return (
        f"以下の欠陥チケットをODC分類してください。\n\n"
        f"{ticket_data}\n\n"
        f"選択肢(value(label)の形式):\n{choices_text}\n\n"
        '出力は {"defect_type": "...", "trigger": "...", "activity": "...", "impact": "..."} '
        "の形式のJSONのみとし、各値は上記選択肢のvalueから選んでください。"
        "該当なしの軸は空文字にしてください。"
    )


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


def suggest_classification(ticket, user=None) -> OdcClassification:
    existing = OdcClassification.objects.filter(ticket=ticket).first()
    if existing and existing.status == OdcClassification.Status.CONFIRMED:
        return existing

    engagement = ticket.source.engagement
    prompt = build_prompt(ticket)

    try:
        raw = run_completion(
            engagement, "odc_suggest", prompt, system=SUGGEST_SYSTEM, user=user
        )
        parsed = _extract_json(raw)
    except LlmError:
        parsed = {}

    values = {}
    for axis, choices in _AXIS_CHOICES.items():
        candidate = parsed.get(axis, "")
        valid_values = {value for value, _ in choices}
        values[axis] = candidate if candidate in valid_values else ""

    classification, _ = OdcClassification.objects.update_or_create(
        ticket=ticket,
        defaults={
            **values,
            "source": OdcClassification.Source.LLM,
            "status": OdcClassification.Status.PENDING,
            "classified_by": user,
        },
    )
    return classification
