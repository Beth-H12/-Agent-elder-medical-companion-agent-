from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.agents.controller import MedicalCompanionController
from app.core.config import settings
from app.db.database import init_db
from app.services.document_upload_service import DocumentUploadService
from app.services.ollama_service import OllamaService
from app.schemas.models import (
    BookingResponse,
    DocumentArchiveRequest,
    DocumentArchiveResponse,
    IntakeRequest,
    IntakeResponse,
    RegistrationRequest,
    SessionState,
)

router = APIRouter(prefix="/api")
document_upload_service = DocumentUploadService()


@lru_cache
def get_controller() -> MedicalCompanionController:
    init_db()
    return MedicalCompanionController()


@router.get("/health")
def health() -> dict:
    ollama_health = OllamaService().health()
    return {
        "status": "ok",
        "database_url": settings.database_url,
        "llm_triage_enabled": settings.llm_provider == "ollama" and ollama_health["ready"],
        "map_service_enabled": bool(settings.amap_api_key and settings.map_provider == "amap"),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.ollama_model,
        "map_provider": settings.map_provider,
        "ollama_ready": ollama_health["ready"],
        "ollama_executable": ollama_health["executable"],
        "ollama_base_url": ollama_health["base_url"],
    }


@router.post("/intake", response_model=IntakeResponse)
def intake(request: IntakeRequest) -> IntakeResponse:
    try:
        return get_controller().handle_intake(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/appointments/book", response_model=BookingResponse)
def book_appointment(request: RegistrationRequest) -> BookingResponse:
    try:
        return get_controller().book_appointment(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents/archive", response_model=DocumentArchiveResponse)
def archive_document(request: DocumentArchiveRequest) -> DocumentArchiveResponse:
    try:
        return get_controller().archive_document(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/documents/archive-image", response_model=DocumentArchiveResponse)
async def archive_document_image(
    session_id: str = Form(...),
    document_title: Optional[str] = Form(default=None),
    document_text: Optional[str] = Form(default=None),
    uploaded_from: str = Form(default="camera"),
    issue_status: str = Form(default="有问题"),
    document_image: UploadFile = File(...),
) -> DocumentArchiveResponse:
    upload_info = None
    try:
        upload_info = await document_upload_service.save_image(document_image)
        request = DocumentArchiveRequest(
            session_id=session_id,
            document_title=document_title,
            document_text=document_text,
            uploaded_from=uploaded_from,
            issue_status=issue_status if issue_status in {"有问题", "无问题"} else "有问题",
            source_filename=upload_info["original_name"],
            source_image_url=upload_info["url"],
            source_image_temp_path=upload_info["temp_path"],
        )
        return get_controller().archive_document(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if upload_info and upload_info.get("temp_path"):
            temp_path = Path(upload_info["temp_path"])
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)


@router.get("/sessions/{session_id}", response_model=SessionState)
def get_session(session_id: str) -> SessionState:
    try:
        return get_controller().get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
