from pathlib import Path
from tempfile import NamedTemporaryFile

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.core.config import _PROJECT_ROOT
from src.models.report import ReportSchema


_SEVERITY_COLORS = {
    "critical": colors.HexColor("#d92d20"),
    "high": colors.HexColor("#e26a3c"),
    "medium": colors.HexColor("#d4a017"),
    "low": colors.HexColor("#1d8a4a"),
}


def _resolve_image_path(image_path: str) -> Path:
    path = Path(image_path)
    if path.is_absolute():
        return path
    return _PROJECT_ROOT / path


def render_report_pdf(report: ReportSchema) -> Path:
    temp = NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_path = Path(temp.name)
    temp.close()

    doc = SimpleDocTemplate(
        str(temp_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=report.metadata.title,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=20,
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=14, spaceBefore=12, spaceAfter=6)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=4)
    body = styles["BodyText"]

    story = [Paragraph(report.metadata.title, title_style)]

    meta_rows = [
        ("Report ID", report.metadata.report_id),
        ("Date", report.metadata.report_date.isoformat()),
        ("Status", report.metadata.status.title()),
        ("Prepared by", report.metadata.prepared_by),
        ("Client", f"{report.client.name} ({report.client.role})"),
        ("Location", report.location.address),
    ]
    if report.location.room:
        meta_rows.append(("Room", report.location.room))

    table = Table(meta_rows, colWidths=[4 * cm, 12 * cm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f4f4f6")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Executive Summary", h1))
    story.append(Paragraph(report.executive_summary, body))

    for section in report.sections:
        story.append(Paragraph(section.heading, h1))
        story.append(Paragraph(section.body, body))

    story.append(Paragraph("Inspection Issues", h1))
    for issue in report.issues:
        severity = issue.severity.value
        color = _SEVERITY_COLORS.get(severity, colors.black)
        story.append(Paragraph(f"{issue.issue_id}: {issue.title}", h2))
        hex_color = "#" + color.hexval()[2:] if hasattr(color, "hexval") else "#000000"
        story.append(
            Paragraph(
                f'<font color="{hex_color}"><b>Severity:</b> {severity.title()}</font>',
                body,
            )
        )
        story.append(Paragraph(issue.description, body))
        story.append(Paragraph(f"<b>Recommendation:</b> {issue.recommendation}", body))
        if issue.image_path:
            resolved = _resolve_image_path(issue.image_path)
            if resolved.exists():
                try:
                    image = Image(str(resolved), width=10 * cm, height=6.5 * cm, kind="proportional")
                    story.append(Spacer(1, 0.2 * cm))
                    story.append(image)
                except Exception:
                    story.append(Paragraph(f"<i>Image unavailable: {resolved.name}</i>", body))
            else:
                story.append(Paragraph(f"<i>Image not found: {issue.image_path}</i>", body))
        story.append(Spacer(1, 0.3 * cm))

    if report.next_steps:
        story.append(Paragraph("Next Steps", h1))
        for index, step in enumerate(report.next_steps, start=1):
            story.append(Paragraph(f"{index}. {step}", body))

    doc.build(story)
    return temp_path
