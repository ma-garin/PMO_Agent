from llm.services import run_completion

from .models import LEVEL_ORDER, TpiAnswer, TpiCheckpoint, TpiKeyArea

SUGGEST_SYSTEM = (
    "あなたはテストプロセス改善のコンサルタントです。"
    "与えられたデータのみを根拠に、優先度順に改善アクションを3〜5件、"
    "根拠と共にMarkdownで提案してください。参考資料を使った場合は文末に[出典n]を明記してください。"
)


def _level_status_for_area(assessment, key_area) -> dict:
    levels: dict[str, dict] = {}
    for level in LEVEL_ORDER:
        checkpoints = TpiCheckpoint.objects.filter(key_area=key_area, level=level)
        total = checkpoints.count()
        if total == 0:
            levels[level] = {"total": 0, "met": 0, "na": 0, "complete": True}
            continue

        answers = TpiAnswer.objects.filter(assessment=assessment, checkpoint__in=checkpoints)
        met = answers.filter(result=TpiAnswer.Result.MET).count()
        na = answers.filter(result=TpiAnswer.Result.NA).count()
        unmet_or_unanswered = total - met - na
        levels[level] = {
            "total": total,
            "met": met,
            "na": na,
            "complete": unmet_or_unanswered == 0,
        }

    all_empty = all(levels[level]["total"] == 0 for level in LEVEL_ORDER)
    achieved_level = None
    if not all_empty:
        for level in LEVEL_ORDER:
            if levels[level]["complete"]:
                achieved_level = level
            else:
                break

    return {"achieved_level": achieved_level, "levels": levels}


def level_status(assessment, key_area) -> dict:
    return _level_status_for_area(assessment, key_area)


def assessment_matrix(assessment) -> list[dict]:
    key_areas = TpiKeyArea.objects.filter(is_active=True)
    result = []
    for key_area in key_areas:
        status = _level_status_for_area(assessment, key_area)
        result.append({"key_area": key_area, **status})
    return result


def unmet_checkpoints(assessment) -> list[TpiAnswer]:
    return list(
        TpiAnswer.objects.filter(assessment=assessment, result=TpiAnswer.Result.NOT_MET)
        .select_related("checkpoint", "checkpoint__key_area")
    )


def generate_suggestion(assessment, user=None) -> str:
    matrix = assessment_matrix(assessment)
    matrix_summary = "\n".join(
        f"{row['key_area'].name}: 到達レベル={row['achieved_level'] or 'イニシャル'}"
        for row in matrix
    )

    unmet = unmet_checkpoints(assessment)[:30]
    unmet_text = "\n".join(
        f"- [{a.checkpoint.key_area.name}/{a.checkpoint.get_level_display()}] {a.checkpoint.text}"
        for a in unmet
    )

    rag_section = ""
    try:
        from copilot.context_builder import build_rag_context

        rag_context = build_rag_context(assessment.engagement, "テストプロセス 改善")
        if rag_context:
            rag_section = f"\n参考資料:\n{rag_context}\n"
    except ImportError:
        pass

    prompt = (
        f"案件名: {assessment.engagement.name}\n"
        f"アセスメント: {assessment.title}\n\n"
        f"キーエリア別到達レベル:\n{matrix_summary}\n\n"
        f"未充足チェックポイント(最大30件):\n{unmet_text}\n"
        f"{rag_section}"
    )
    return run_completion(
        assessment.engagement,
        "tpi_suggest",
        prompt,
        system=SUGGEST_SYSTEM,
        max_tokens=2000,
        user=user,
    )
