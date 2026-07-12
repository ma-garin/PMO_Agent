import markdown as _markdown
import nh3

from analytics.services import convergence_series, odc_distribution, summarize_defects
from llm.prompt_utils import EXTERNAL_DATA_GUARD
from llm.services import run_completion

# Markdown変換後のHTMLで許可するタグ/属性。これ以外(script等)は除去する(CWE-79対策)。
_ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "br", "hr",
    "strong", "em", "b", "i", "u", "s", "blockquote",
    "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td",
    "code", "pre", "a", "span",
}
_ALLOWED_ATTRS = {"a": {"href", "title"}}


def render_markdown_safe(text: str) -> str:
    """Markdownを安全なHTMLに変換する。生HTML/スクリプトはnh3で無害化する。

    報告書本文は案件メンバーが編集でき、保存型XSSの経路になり得るため、
    テンプレート側で |safe 出力する前に必ずこの関数を通すこと。
    """
    raw_html = _markdown.markdown(text or "", extensions=["tables"])
    return nh3.clean(raw_html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS)


DRAFT_SYSTEM = (
    "あなたは第三者検証会社の品質報告書を作成するアシスタントです。"
    "与えられたデータのみを根拠に、次のMarkdown章立てで出力してください。"
    "数値は与えられたものだけを使い、捏造しないでください。\n\n"
    "# 品質状況報告書\n"
    "## サマリー\n"
    "## 定量分析\n"
    "## テスト進捗\n"
    "## ODC分析所見\n"
    "## リスク状況\n"
    "## リスクと提言\n"
    + EXTERNAL_DATA_GUARD
)


def generate_draft(engagement, period_start, period_end, user=None, template=None) -> str:
    summary = summarize_defects(engagement)
    series = convergence_series(engagement)[-8:]
    odc = odc_distribution(engagement)

    risk_section = ""
    try:
        from risks.models import RiskItem
        from testmgmt.services import evaluate_gate, progress_summary
        from testmgmt.models import QualityGate

        risks = (
            RiskItem.objects.filter(engagement=engagement)
            .exclude(status=RiskItem.Status.CLOSED)
            .order_by("-probability", "-impact")[:10]
        )
        risk_counts = {"high": 0, "medium": 0, "low": 0}
        for r in risks:
            risk_counts[r.severity] += 1
        progress_rows = progress_summary(engagement)
        latest_gate = (
            QualityGate.objects.filter(engagement=engagement).order_by("-created_at").first()
        )
        gate_summary = None
        if latest_gate is not None:
            gate_summary = {
                "name": latest_gate.name,
                "verdict": latest_gate.get_verdict_display(),
                **evaluate_gate(latest_gate),
            }
        gate_text = (
            "なし"
            if gate_summary is None
            else f"{gate_summary['name']}（{gate_summary['verdict']}）"
        )
        progress_text = "データなし" if not progress_rows else str(progress_rows)
        risk_section = (
            f"\nリスク件数: 高{risk_counts['high']}件 / 中{risk_counts['medium']}件 / "
            f"低{risk_counts['low']}件\n"
            f"テスト進捗サマリー: {progress_text}\n"
            f"直近の品質ゲート判定: {gate_text}\n"
        )
    except ImportError:
        pass

    rag_section = ""
    try:
        from copilot.context_builder import build_rag_context

        rag_context = build_rag_context(engagement, "品質基準 テスト標準")
        if rag_context:
            rag_section = f"\n参考資料:\n{rag_context}\n"
    except ImportError:
        pass

    series_text = (
        "; ".join(
            f"{p.get('label', '')} 検出{p.get('opened', 0)}/クローズ{p.get('closed', 0)}"
            for p in series
        )
        if series
        else "データなし"
    )
    density_text = "-" if summary.get("density") is None else summary["density"]
    avg_age_text = (
        "データなし"
        if summary.get("avg_open_age_days") is None
        else f"{summary['avg_open_age_days']}日"
    )
    summary_text = (
        f"総数{summary['total']}件 / 未クローズ{summary['open']}件 / "
        f"クローズ{summary['closed']}件 / 期限超過{summary['overdue']}件 / "
        f"欠陥密度{density_text} / 平均滞留{avg_age_text}"
    )

    def _axis_text(axis):
        return "、".join(f"{a['label']}{a['count']}件" for a in axis) if axis else "なし"

    odc_text = (
        f"確定{odc['confirmed_count']}件 / 未分類{odc['unclassified_count']}件 / "
        f"欠陥種別[{_axis_text(odc['defect_type'])}] / "
        f"トリガー[{_axis_text(odc['trigger'])}] / "
        f"検出アクティビティ[{_axis_text(odc['activity'])}] / "
        f"影響度[{_axis_text(odc['impact'])}]"
    )
    prompt = (
        f"案件名: {engagement.name}\n"
        f"対象期間: {period_start} 〜 {period_end}\n\n"
        f"欠陥サマリー: {summary_text}\n\n"
        f"週次収束データ(直近8点): {series_text}\n\n"
        f"ODC分布(確定済み): {odc_text}\n"
        f"{risk_section}"
        f"{rag_section}"
    )
    system_prompt = template.system_prompt if template is not None else DRAFT_SYSTEM
    return run_completion(
        engagement,
        "report_draft",
        prompt,
        system=system_prompt,
        max_tokens=3000,
        user=user,
    )
