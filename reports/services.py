from analytics.services import convergence_series, odc_distribution, summarize_defects
from llm.services import run_completion

DRAFT_SYSTEM = (
    "あなたは第三者検証会社の品質報告書を作成するアシスタントです。"
    "与えられたデータのみを根拠に、次のMarkdown章立てで出力してください。"
    "数値は与えられたものだけを使い、捏造しないでください。\n\n"
    "# 品質状況報告書\n"
    "## サマリー\n"
    "## 定量分析\n"
    "## ODC分析所見\n"
    "## リスクと提言\n"
)


def generate_draft(engagement, period_start, period_end, user=None) -> str:
    summary = summarize_defects(engagement)
    series = convergence_series(engagement)[-8:]
    odc = odc_distribution(engagement)

    prompt = (
        f"案件名: {engagement.name}\n"
        f"対象期間: {period_start} 〜 {period_end}\n\n"
        f"欠陥サマリー: {summary}\n\n"
        f"週次収束データ(直近8点): {series}\n\n"
        f"ODC分布(確定済み): {odc}\n"
    )
    return run_completion(
        engagement,
        "report_draft",
        prompt,
        system=DRAFT_SYSTEM,
        max_tokens=3000,
        user=user,
    )
