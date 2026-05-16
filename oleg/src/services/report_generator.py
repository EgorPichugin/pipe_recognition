from datetime import date

from pydantic import ValidationError

from src.core.config import PHOTOS_IMAGE_DIR
from src.models.photos import PhotoRecord
from src.models.report import (
    InspectionLocation,
    IssueSeverity,
    ReportIssue,
    ReportMetadata,
    ReportParty,
    ReportSchema,
    ReportSection,
)
from src.services.gemini_client import GeminiClient, GeminiError


REPORT_GENERATION_INSTRUCTIONS = """
You are an inspection report writer. Generate a structured inspection report from a list of
analyzed site photos.

You will receive:
- "photos": a list of photo records with id, latitude, longitude, image_name, category, status.
- "context": optional notes from the inspector.

Return a JSON object with EXACTLY this shape (no extra fields):
{
  "metadata": {
    "report_id": "RPT-YYYY-NNNN",
    "title": "...",
    "report_date": "YYYY-MM-DD",
    "prepared_by": "AI Inspection Assistant",
    "status": "draft"
  },
  "client": { "name": "...", "role": "Client", "email": null },
  "location": { "site_name": "...", "address": "...", "room": null },
  "executive_summary": "...",
  "sections": [ { "heading": "...", "body": "..." } ],
  "issues": [
    {
      "issue_id": "ISS-001",
      "title": "...",
      "description": "...",
      "severity": "low|medium|high|critical",
      "recommendation": "...",
      "image_path": "src/docs/images/photos/<image_name>"
    }
  ],
  "next_steps": [ "..." ]
}

Rules:
- Each photo with status "detected" or "flagged" must produce one issue.
- Photos with status "ok" should be summarized in the executive summary, not as issues.
- Map category -> severity using common sense (e.g. smoke_detector_missing -> high,
  water_damage -> high, wall_crack -> medium, missing_sealant -> low, uneven_finish -> low).
- Use distinct issue_ids ISS-001, ISS-002, ...
- Use the average of the photo coordinates as the inspection site (best guess address from coords).
- Output STRICT JSON only.
""".strip()


class ReportGenerator:
    def __init__(self, gemini_client: GeminiClient | None = None) -> None:
        self._gemini = gemini_client or GeminiClient()

    def generate(self, photos: list[PhotoRecord], context: str | None = None) -> ReportSchema:
        payload = {
            "photos": [photo.model_dump() for photo in photos],
            "context": context or "",
        }
        raw = self._gemini.generate_json(REPORT_GENERATION_INSTRUCTIONS, payload)
        raw = self._sanitize(raw, photos)
        try:
            return ReportSchema.model_validate(raw)
        except ValidationError as exc:
            raise GeminiError(f"Generated report failed validation: {exc.errors()[0]}") from exc

    @staticmethod
    def _sanitize(raw: dict, photos: list[PhotoRecord]) -> dict:
        if not isinstance(raw, dict):
            raise GeminiError("Gemini returned a non-object response.")

        metadata = raw.setdefault("metadata", {})
        metadata.setdefault("report_id", "RPT-2026-0001")
        metadata.setdefault("title", "AI Inspection Report")
        metadata.setdefault("prepared_by", "AI Inspection Assistant")
        metadata.setdefault("status", "draft")
        metadata.setdefault("report_date", date.today().isoformat())

        client = raw.setdefault("client", {})
        client.setdefault("name", "Vienna Property Group")
        client.setdefault("role", "Client")
        client.setdefault("email", None)

        location = raw.setdefault("location", {})
        location.setdefault("site_name", "Inspection Site")
        location.setdefault("address", "Vienna, Austria")
        location.setdefault("room", None)

        raw.setdefault("executive_summary", "Automated inspection report generated from photo data.")
        raw.setdefault("sections", [])
        raw.setdefault("next_steps", [])

        issues = raw.get("issues") or []
        valid_image_names = {p.image_name for p in photos}
        sanitized_issues = []
        for index, issue in enumerate(issues, start=1):
            if not isinstance(issue, dict):
                continue
            issue.setdefault("issue_id", f"ISS-{index:03d}")
            issue.setdefault("title", "Inspection finding")
            issue.setdefault("description", "Issue detected during inspection.")
            issue.setdefault("severity", IssueSeverity.LOW.value)
            issue.setdefault("recommendation", "Review on site.")

            image_path = issue.get("image_path")
            if image_path:
                tail = image_path.rsplit("/", 1)[-1]
                if tail in valid_image_names:
                    issue["image_path"] = f"src/docs/images/photos/{tail}"
                else:
                    issue["image_path"] = None
            sanitized_issues.append(issue)

        raw["issues"] = sanitized_issues

        if not sanitized_issues and not raw["sections"]:
            raw["sections"].append(
                ReportSection(
                    heading="Overall Assessment",
                    body="No issues were generated from the provided photos.",
                ).model_dump()
            )

        return raw

    @staticmethod
    def fallback_report(photos: list[PhotoRecord]) -> ReportSchema:
        """Deterministic fallback used when Gemini is unavailable — keeps the UI demoable."""
        severity_by_category = {
            "wall_crack": IssueSeverity.MEDIUM,
            "missing_sealant": IssueSeverity.LOW,
            "uneven_finish": IssueSeverity.LOW,
            "smoke_detector_missing": IssueSeverity.HIGH,
            "water_damage": IssueSeverity.HIGH,
            "loose_tile": IssueSeverity.LOW,
        }
        issues: list[ReportIssue] = []
        for index, photo in enumerate((p for p in photos if p.status != "ok"), start=1):
            image_path = None
            candidate = PHOTOS_IMAGE_DIR / photo.image_name
            if candidate.exists():
                image_path = f"src/docs/images/photos/{photo.image_name}"
            issues.append(
                ReportIssue(
                    issue_id=f"ISS-{index:03d}",
                    title=photo.category.replace("_", " ").title(),
                    description=(
                        f"Photo {photo.id} captured at ({photo.latitude}, {photo.longitude}) "
                        f"shows {photo.category.replace('_', ' ')}."
                    ),
                    severity=severity_by_category.get(photo.category, IssueSeverity.LOW),
                    recommendation="Inspect on site and schedule remediation.",
                    image_path=image_path,
                )
            )

        return ReportSchema(
            metadata=ReportMetadata(
                report_id="RPT-2026-AUTO",
                title="AI Inspection Report (fallback)",
                report_date=date.today(),
                prepared_by="AI Inspection Assistant",
            ),
            client=ReportParty(name="Vienna Property Group", role="Client", email=None),
            location=InspectionLocation(
                site_name="Inspection Site",
                address="Vienna, Austria",
                room=None,
            ),
            executive_summary=(
                f"Auto-generated from {len(photos)} site photos. "
                f"{len(issues)} issues require follow-up."
            ),
            sections=[
                ReportSection(
                    heading="Scope of Inspection",
                    body=f"Review of {len(photos)} photos covering the surveyed site.",
                ),
            ],
            issues=issues,
            next_steps=[
                "Confirm repair ownership with the site manager.",
                "Schedule remediation before final acceptance review.",
            ],
        )
