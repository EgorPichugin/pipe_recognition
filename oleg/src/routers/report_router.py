from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError
from starlette.background import BackgroundTask
from fastapi.responses import FileResponse, Response

from src.models.photos import PhotoListResponse, ReportEvaluation
from src.models.report import ReportChangeRequest, ReportSchema
from src.services.gemini_client import GeminiError, GeminiUnavailableError
from src.services.photo_history_service import photo_history_service
from src.services.report_edit_planner import ReportPlannerError, ReportPlannerUnavailableError
from src.services.report_evaluator import ReportEvaluator
from src.services.report_generator import ReportGenerator
from src.services.report_pdf_renderer import render_report_pdf
from src.services.report_service import report_service

router = APIRouter(prefix="/report", tags=["Report Generation"])

_report_generator = ReportGenerator()
_report_evaluator = ReportEvaluator()


class GenerateFromPhotosRequest(BaseModel):
    context: str | None = None
    use_fallback_on_error: bool = True


@router.get("/schema", response_model=ReportSchema)
def get_dummy_report_schema() -> ReportSchema:
    return report_service.get_current_report()


@router.put("/schema", response_model=ReportSchema)
def put_report_schema(report: ReportSchema) -> ReportSchema:
    return report_service.set_report(report)


@router.post("/reset", response_model=ReportSchema)
def reset_report_schema() -> ReportSchema:
    return report_service.reset_report()


@router.get("/preview")
def get_report_preview() -> FileResponse:
    docx_path = report_service.create_preview_document()
    return _docx_response(docx_path)


@router.get("/preview.pdf")
def get_report_preview_pdf() -> FileResponse:
    pdf_path = render_report_pdf(report_service.get_current_report())
    return _pdf_response(pdf_path)


@router.post("/preview")
def update_report_preview(change_request: ReportChangeRequest) -> FileResponse:
    try:
        report, filtered_change = report_service.apply_requested_changes(change_request)
    except ReportPlannerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ReportPlannerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    docx_path = report_service.create_preview_document(report)
    return _docx_response(
        docx_path,
        headers={
            "X-Report-Change-Intent": filtered_change.intent,
            "X-Report-Change-Summary": filtered_change.summary[:500],
            "X-Report-Applied-Changes": str(len(filtered_change.applied_changes)),
            "X-Report-Rejected-Changes": str(len(filtered_change.rejected_instructions)),
        },
    )


@router.post("/generate", response_model=ReportSchema)
def generate_from_photos(request: GenerateFromPhotosRequest | None = None) -> ReportSchema:
    request = request or GenerateFromPhotosRequest()
    photos = photo_history_service.list_photos()
    if not photos:
        raise HTTPException(status_code=400, detail="No photos available to generate a report.")

    try:
        generated = _report_generator.generate(photos, context=request.context)
    except GeminiUnavailableError as exc:
        if request.use_fallback_on_error:
            generated = _report_generator.fallback_report(photos)
        else:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (GeminiError, ValidationError) as exc:
        if request.use_fallback_on_error:
            generated = _report_generator.fallback_report(photos)
        else:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return report_service.set_report(generated)


@router.post("/evaluate", response_model=ReportEvaluation)
def evaluate_current_report() -> ReportEvaluation:
    report = report_service.get_current_report()
    try:
        return _report_evaluator.evaluate(report)
    except GeminiUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GeminiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/photos", response_model=PhotoListResponse)
def list_photos() -> PhotoListResponse:
    return PhotoListResponse(photos=photo_history_service.list_photos())


@router.get("/photos/export")
def export_photos_csv() -> Response:
    csv_text = photo_history_service.export_csv()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=\"photo-history.csv\""},
    )


def _docx_response(path: Path, headers: dict[str, str] | None = None) -> FileResponse:
    return FileResponse(
        path=path,
        filename="inspection-report-preview.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
        background=BackgroundTask(path.unlink, missing_ok=True),
    )


def _pdf_response(path: Path) -> FileResponse:
    return FileResponse(
        path=path,
        filename="inspection-report.pdf",
        media_type="application/pdf",
        background=BackgroundTask(path.unlink, missing_ok=True),
    )
