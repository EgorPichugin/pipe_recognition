from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.config import IMAGE_PATH


class IssueSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReportParty(BaseModel):
    name: str = Field(..., min_length=1, examples=["Vienna Property Group"])
    role: str = Field(..., min_length=1, examples=["Client"])
    email: str | None = Field(default=None, examples=["client@example.com"])


class ReportMetadata(BaseModel):
    report_id: str = Field(..., min_length=1, examples=["RPT-2026-0001"])
    title: str = Field(..., min_length=1, examples=["Apartment Inspection Report"])
    report_date: date
    prepared_by: str = Field(..., min_length=1, examples=["AI Inspection Assistant"])
    status: Literal["draft", "review", "final"] = "draft"


class InspectionLocation(BaseModel):
    site_name: str = Field(..., min_length=1, examples=["Sample Apartment"])
    address: str = Field(..., min_length=1, examples=["Mariahilfer Strasse 1, 1060 Vienna"])
    room: str | None = Field(default=None, examples=["Living Room"])


class ReportIssue(BaseModel):
    issue_id: str = Field(..., min_length=1, examples=["ISS-001"])
    title: str = Field(..., min_length=1, examples=["Crack near window frame"])
    description: str = Field(..., min_length=1)
    severity: IssueSeverity
    recommendation: str = Field(..., min_length=1)
    image_path: str | None = Field(
        default=None,
        description="Path to an image file that should be embedded in the generated report.",
        examples=["src/docs/images/sample_wall_image.jpg"],
    )


class ReportSection(BaseModel):
    heading: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)


class ReportSchema(BaseModel):
    metadata: ReportMetadata
    client: ReportParty
    location: InspectionLocation
    executive_summary: str = Field(..., min_length=1)
    sections: list[ReportSection] = Field(default_factory=list)
    issues: list[ReportIssue] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ReportChangeRequest(BaseModel):
    requested_changes: str = Field(
        ...,
        min_length=3,
        max_length=4000,
        description="Natural-language changes requested by the user.",
        examples=["Make the crack near the window high severity and add repainting as a next step."],
    )


class StrictReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReportMetadataPatch(StrictReportModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    report_date: date | None = None
    prepared_by: str | None = Field(default=None, min_length=1, max_length=120)
    status: Literal["draft", "review", "final"] | None = None

    @model_validator(mode="after")
    def validate_patch_has_content(self) -> "ReportMetadataPatch":
        if not self.model_fields_set:
            raise ValueError("A metadata patch must provide at least one field.")
        return self


class ReportPartyPatch(StrictReportModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    role: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_patch_has_content(self) -> "ReportPartyPatch":
        if not self.model_fields_set:
            raise ValueError("A party patch must provide at least one field.")
        return self


class InspectionLocationPatch(StrictReportModel):
    site_name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, min_length=1, max_length=300)
    room: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validate_patch_has_content(self) -> "InspectionLocationPatch":
        if not self.model_fields_set:
            raise ValueError("A location patch must provide at least one field.")
        return self


class ReportSectionPatch(StrictReportModel):
    match_heading: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Existing section heading to update. Leave empty when adding a section.",
    )
    heading: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=3000)

    @model_validator(mode="after")
    def validate_patch_has_content(self) -> "ReportSectionPatch":
        if not self.heading and not self.body:
            raise ValueError("A section patch must provide a heading or body.")
        return self


class ReportIssuePatch(StrictReportModel):
    match_issue_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
        description="Existing issue_id to update. Prefer this when available.",
    )
    match_title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Existing issue title to update when issue_id is not available.",
    )
    issue_id: str | None = Field(default=None, min_length=1, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=3000)
    severity: IssueSeverity | None = None
    recommendation: str | None = Field(default=None, min_length=1, max_length=3000)
    image_path: str | None = Field(
        default=None,
        max_length=500,
        description="Set to null only when the user explicitly asks to remove the image.",
    )

    @model_validator(mode="after")
    def validate_patch_has_content(self) -> "ReportIssuePatch":
        editable_fields = {
            "issue_id",
            "title",
            "description",
            "severity",
            "recommendation",
            "image_path",
        }
        if not editable_fields.intersection(self.model_fields_set):
            raise ValueError("An issue patch must provide at least one editable field.")
        return self


class ReportNextStepPatch(StrictReportModel):
    match_text: str = Field(..., min_length=1, max_length=500)
    text: str = Field(..., min_length=1, max_length=500)


class ReportPatch(StrictReportModel):
    metadata: ReportMetadataPatch | None = None
    client: ReportPartyPatch | None = None
    location: InspectionLocationPatch | None = None
    executive_summary: str | None = Field(default=None, min_length=1, max_length=4000)
    sections_to_upsert: list[ReportSectionPatch] = Field(default_factory=list, max_length=8)
    section_headings_to_remove: list[str] = Field(default_factory=list, max_length=8)
    issues_to_upsert: list[ReportIssuePatch] = Field(default_factory=list, max_length=12)
    issue_ids_or_titles_to_remove: list[str] = Field(default_factory=list, max_length=12)
    next_steps_to_add: list[str] = Field(default_factory=list, max_length=12)
    next_steps_to_update: list[ReportNextStepPatch] = Field(default_factory=list, max_length=12)
    next_steps_to_remove: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_patch_has_content(self) -> "ReportPatch":
        if (
            self.metadata is None
            and self.client is None
            and self.location is None
            and self.executive_summary is None
            and not self.sections_to_upsert
            and not self.section_headings_to_remove
            and not self.issues_to_upsert
            and not self.issue_ids_or_titles_to_remove
            and not self.next_steps_to_add
            and not self.next_steps_to_update
            and not self.next_steps_to_remove
        ):
            raise ValueError("A report patch must include at least one change.")
        return self


class ReportEditPlan(StrictReportModel):
    intent: Literal["update_report", "clarification_needed", "unsupported"]
    summary: str = Field(..., min_length=1, max_length=700)
    allowed_instructions: list[str] = Field(default_factory=list, max_length=12)
    rejected_instructions: list[str] = Field(default_factory=list, max_length=12)
    patch: ReportPatch | None = None

    @model_validator(mode="after")
    def validate_intent_matches_patch(self) -> "ReportEditPlan":
        if self.intent == "update_report" and self.patch is None:
            raise ValueError("update_report intent requires a patch.")
        if self.intent != "update_report" and self.patch is not None:
            raise ValueError("Only update_report intent may include a patch.")
        return self


class FilteredReportChange(BaseModel):
    intent: Literal["update_report", "clarification_needed", "unsupported"]
    summary: str = Field(..., min_length=1)
    allowed_instructions: list[str] = Field(default_factory=list)
    rejected_instructions: list[str] = Field(default_factory=list)
    applied_changes: list[str] = Field(default_factory=list)


class ReportPreviewResponse(BaseModel):
    report: ReportSchema
    download_url: str
    change_filter: FilteredReportChange | None = None


def build_dummy_report() -> ReportSchema:
    return ReportSchema(
        metadata=ReportMetadata(
            report_id="RPT-2026-0001",
            title="Apartment Inspection Report",
            report_date=date(2026, 5, 11),
            prepared_by="AI Inspection Assistant",
        ),
        client=ReportParty(
            name="Vienna Property Group",
            role="Client",
            email="inspections@example.com",
        ),
        location=InspectionLocation(
            site_name="Sample Apartment",
            address="Mariahilfer Strasse 1, 1060 Vienna",
            room="Living Room",
        ),
        executive_summary=(
            "The inspection identified several finish and sealing defects in the living room. "
            "The observed issues are repairable, but water ingress and surface deterioration "
            "should be addressed before the next handover milestone."
        ),
        sections=[
            ReportSection(
                heading="Scope of Inspection",
                body=(
                    "Visual inspection of wall finishes, door sealing, window frame condition, "
                    "and visible installation quality."
                ),
            ),
            ReportSection(
                heading="Overall Assessment",
                body=(
                    "The apartment is suitable for continued works with targeted remediation. "
                    "No immediate structural concern is confirmed from the current visual evidence."
                ),
            ),
        ],
        issues=[
            ReportIssue(
                issue_id="ISS-001",
                title="Crack near window frame",
                description="A visible diagonal crack is present near the upper corner of the window frame.",
                severity=IssueSeverity.MEDIUM,
                recommendation="Inspect substrate movement, seal the crack, and repaint the affected surface.",
                image_path=IMAGE_PATH,
            ),
            ReportIssue(
                issue_id="ISS-002",
                title="Missing sealant around door",
                description="Sealant is incomplete along the lower section of the internal door frame.",
                severity=IssueSeverity.LOW,
                recommendation="Apply continuous sealant bead and verify adhesion after curing.",
                image_path=IMAGE_PATH,
            ),
        ],
        next_steps=[
            "Confirm repair ownership with the site manager.",
            "Schedule remediation before final acceptance review.",
            "Capture follow-up photographs after completion.",
        ],
    )
