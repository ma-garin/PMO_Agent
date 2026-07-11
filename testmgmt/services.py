import csv
import io

from llm.services import run_completion

from .models import QualityGate, TestProgressEntry

PLAN_SECTIONS = (
    "## 1. 目的とスコープ\n"
    "## 2. テストレベルとテストタイプ\n"
    "## 3. 開始基準・終了基準\n"
    "## 4. スケジュールと体制\n"
    "## 5. 品質リスクと対策方針\n"
    "## 6. 成果物と報告\n"
)

DRAFT_SYSTEM = (
    "あなたは第三者検証会社のテスト計画を作成するアシスタントです。"
    "与えられたデータのみを根拠に、次のMarkdown章立てで出力してください。"
    "数値は与えられたものだけを使い、捏造しないでください。\n\n"
    f"# テスト計画\n{PLAN_SECTIONS}"
)


def generate_plan_draft(engagement, kind: str, test_level: str = "", user=None) -> str:
    from analytics.services import summarize_defects
    from risks.models import RiskItem

    summary = summarize_defects(engagement)
    risks = list(
        RiskItem.objects.filter(engagement=engagement)
        .exclude(status=RiskItem.Status.CLOSED)
        .order_by("-probability", "-impact")[:10]
    )
    risk_lines = [f"- {r.title}(確率{r.probability}×影響{r.impact})" for r in risks]

    rag_section = ""
    try:
        from copilot.context_builder import build_rag_context

        rag_context = build_rag_context(engagement, "テスト計画 標準")
        if rag_context:
            rag_section = f"\n参考資料:\n{rag_context}\n"
    except ImportError:
        pass

    prompt = (
        f"案件名: {engagement.name}\n"
        f"計画種別: {kind}\n"
        f"対象テストレベル: {test_level or '(マスター計画のため全体)'}\n\n"
        f"欠陥サマリー: {summary}\n\n"
        f"品質リスク(上位):\n" + "\n".join(risk_lines) + "\n"
        f"{rag_section}"
    )
    return run_completion(engagement, "test_plan_draft", prompt, system=DRAFT_SYSTEM, max_tokens=3000, user=user)


def progress_series(engagement, test_level: str) -> list[dict]:
    entries = TestProgressEntry.objects.filter(
        engagement=engagement, test_level=test_level
    ).order_by("date")
    return [
        {
            "date": e.date,
            "planned": e.planned_cases,
            "executed": e.executed_cases,
            "passed": e.passed_cases,
        }
        for e in entries
    ]


def progress_summary(engagement) -> list[dict]:
    levels = (
        TestProgressEntry.objects.filter(engagement=engagement)
        .order_by("test_level")
        .values_list("test_level", flat=True)
        .distinct()
    )
    results = []
    for level in levels:
        latest = (
            TestProgressEntry.objects.filter(engagement=engagement, test_level=level)
            .order_by("-date")
            .first()
        )
        if latest is None:
            continue
        execution_rate = (
            round(latest.executed_cases / latest.planned_cases * 100, 1)
            if latest.planned_cases
            else 0
        )
        pass_rate = (
            round(latest.passed_cases / latest.executed_cases * 100, 1)
            if latest.executed_cases
            else 0
        )
        results.append(
            {
                "test_level": level,
                "execution_rate": execution_rate,
                "pass_rate": pass_rate,
                "last_date": latest.date,
                "planned": latest.planned_cases,
                "executed": latest.executed_cases,
                "passed": latest.passed_cases,
            }
        )
    return results


def evaluate_gate(gate: QualityGate) -> dict:
    from analytics.services import summarize_defects
    from risks.models import RiskItem

    criteria = gate.criteria or {}
    summary_rows = progress_summary(gate.engagement)
    total_planned = sum(r["planned"] for r in summary_rows)
    total_executed = sum(r["executed"] for r in summary_rows)
    total_passed = sum(r["passed"] for r in summary_rows)
    execution_rate = round(total_executed / total_planned * 100, 1) if total_planned else 0
    pass_rate = round(total_passed / total_executed * 100, 1) if total_executed else 0

    defect_summary = summarize_defects(gate.engagement)
    high_risks = RiskItem.objects.filter(
        engagement=gate.engagement, probability__gte=1
    ).exclude(status=RiskItem.Status.CLOSED)
    high_risk_count = sum(1 for r in high_risks if r.severity == "high")

    results = []
    if "min_execution_rate" in criteria:
        expected = criteria["min_execution_rate"]
        results.append(
            {
                "label": "テスト消化率",
                "expected": f"{expected}%以上",
                "actual": f"{execution_rate}%",
                "ok": execution_rate >= expected,
            }
        )
    if "min_pass_rate" in criteria:
        expected = criteria["min_pass_rate"]
        results.append(
            {
                "label": "合格率",
                "expected": f"{expected}%以上",
                "actual": f"{pass_rate}%",
                "ok": pass_rate >= expected,
            }
        )
    if "max_open_defects" in criteria:
        expected = criteria["max_open_defects"]
        results.append(
            {
                "label": "未クローズ欠陥数",
                "expected": f"{expected}件以下",
                "actual": f"{defect_summary['open']}件",
                "ok": defect_summary["open"] <= expected,
            }
        )
    if "max_high_risks" in criteria:
        expected = criteria["max_high_risks"]
        results.append(
            {
                "label": "高リスク残数",
                "expected": f"{expected}件以下",
                "actual": f"{high_risk_count}件",
                "ok": high_risk_count <= expected,
            }
        )

    all_ok = all(r["ok"] for r in results) if results else False
    return {"results": results, "all_ok": all_ok}


def import_progress_csv(engagement, file) -> tuple[int, list[str]]:
    text = file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    imported = 0
    errors: list[str] = []
    for row_number, row in enumerate(reader, start=2):
        try:
            TestProgressEntry.objects.update_or_create(
                engagement=engagement,
                test_level=row["test_level"].strip(),
                date=row["date"].strip(),
                defaults={
                    "planned_cases": int(row.get("planned_cases") or 0),
                    "executed_cases": int(row.get("executed_cases") or 0),
                    "passed_cases": int(row.get("passed_cases") or 0),
                    "note": row.get("note", "").strip(),
                },
            )
            imported += 1
        except (KeyError, ValueError) as exc:
            errors.append(f"{row_number}行目: {exc}")
    return imported, errors
