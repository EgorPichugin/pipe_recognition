from pydantic import ValidationError

from src.models.photos import ReportEvaluation
from src.models.report import ReportSchema
from src.services.gemini_client import GeminiClient, GeminiError


REPORT_EVALUATION_INSTRUCTIONS = """
You are a senior QA reviewer of inspection reports. Audit the provided report for:
- Internal consistency (issues match the executive summary; severities reflect descriptions).
- Missing or implausible data (empty fields, generic boilerplate, mismatched recommendations).
- Coverage gaps (next steps cover all high/critical issues).
- Tone and clarity issues.

Return a STRICT JSON object with EXACTLY this shape (no extras, no markdown fences):
{
  "overall_score": 0-100,
  "summary": "one-paragraph verdict",
  "findings": [
    { "severity": "info|low|medium|high", "target": "<field path>", "message": "..." }
  ],
  "recommendations": [ "concrete edits the author should make" ]
}

Target path examples: "executive_summary", "issues[ISS-002].severity", "next_steps".
Be concise. At most 8 findings and 6 recommendations.
""".strip()


class ReportEvaluator:
    def __init__(self, gemini_client: GeminiClient | None = None) -> None:
        self._gemini = gemini_client or GeminiClient()

    def evaluate(self, report: ReportSchema) -> ReportEvaluation:
        payload = {"report": report.model_dump(mode="json")}
        raw = self._gemini.generate_json(REPORT_EVALUATION_INSTRUCTIONS, payload)
        try:
            return ReportEvaluation.model_validate(raw)
        except ValidationError as exc:
            raise GeminiError(f"Evaluation response failed validation: {exc.errors()[0]}") from exc
