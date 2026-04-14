from typing import Optional

from app.agents.document_agent import DocumentArchiveAgent
from app.agents.hospital_agent import HospitalRecommendationAgent
from app.agents.instructions_agent import CareInstructionsAgent
from app.agents.navigation_agent import NavigationAgent
from app.agents.registration_agent import RegistrationAgent
from app.agents.triage_agent import LLMTriageAgent
from app.schemas.models import (
    BookingResponse,
    DocumentArchiveRequest,
    DocumentArchiveResponse,
    IntakeRequest,
    IntakeResponse,
    RegistrationRequest,
    SessionState,
)

from app.services.hospital_catalog import HospitalCatalog
from app.services.document_storage_service import DocumentStorageService
from app.services.map_service import MapService
from app.services.priority_hospital_catalog import PriorityHospitalCatalog
from app.services.session_store import SessionStore


class MedicalCompanionController:
    def __init__(
        self,
        store: Optional[SessionStore] = None,
        triage_agent: Optional[LLMTriageAgent] = None,
        hospital_catalog: Optional[HospitalCatalog] = None,
        map_service: Optional[MapService] = None,
        priority_catalog: Optional[PriorityHospitalCatalog] = None,
        document_storage: Optional[DocumentStorageService] = None,
    ) -> None:
        self.store = store or SessionStore()
        self.hospital_catalog = hospital_catalog or HospitalCatalog()
        self.map_service = map_service or MapService()
        self.priority_catalog = priority_catalog or PriorityHospitalCatalog()
        self.document_storage = document_storage or DocumentStorageService()
        self.triage_agent = triage_agent or LLMTriageAgent(logger=self.store.log_llm_call)
        self.hospital_agent = HospitalRecommendationAgent(
            self.hospital_catalog,
            self.map_service,
            self.priority_catalog,
        )
        self.registration_agent = RegistrationAgent(self.hospital_catalog)
        self.navigation_agent = NavigationAgent()
        self.document_agent = DocumentArchiveAgent(self.hospital_catalog)
        self.instructions_agent = CareInstructionsAgent()

    def handle_intake(self, request: IntakeRequest) -> IntakeResponse:
        triage = self.triage_agent.run(request.symptom_text)
        origin_context = self.map_service.resolve_location(request.current_location)
        candidates = self.hospital_agent.run(
            current_location=request.current_location,
            transport_mode=request.transport_mode,
            triage=triage,
            preferences=request.preferences,
        )
        if not candidates:
            city_label = (
                origin_context.city
                if origin_context and origin_context.city
                else request.current_location
            )
            raise ValueError(f"当前未能在 {city_label} 附近检索到适合 {triage.department} 的医院，请稍后重试或扩大搜索范围")

        session = self.store.create_session(request, triage, candidates)
        self.store.append_trace(
            session.session_id,
            self.triage_agent.trace(request.symptom_text[:80], f"{triage.department} / {triage.urgency}"),
        )
        self.store.append_trace(
            session.session_id,
            self.hospital_agent.trace(request.current_location, f"返回 {len(candidates)} 个候选医院"),
        )

        return IntakeResponse(
            session_id=session.session_id,
            triage=triage,
            recommended_hospital=candidates[0],
            candidates=candidates,
            suggested_next_action=f"建议优先预约 {candidates[0].hospital_name} 的 {triage.department} 门诊。",
        )

    def book_appointment(self, request: RegistrationRequest) -> BookingResponse:
        session = self.store.get_session(request.session_id)
        selected_candidate = next(
            (
                candidate
                for candidate in session.candidates
                if candidate.hospital_id == (request.hospital_id or session.candidates[0].hospital_id)
            ),
            session.candidates[0],
        )
        selected_hospital_id = selected_candidate.hospital_id
        preferred_time = request.preferred_time or session.intake.preferred_time

        appointment = self.registration_agent.run(
            hospital_id=selected_hospital_id,
            department=session.triage.department,
            preferred_time=preferred_time,
            route_summary=selected_candidate.route,
            selected_candidate=selected_candidate,
        )
        navigation = self.navigation_agent.run(appointment)
        self.store.save_appointment(session.session_id, appointment, navigation)
        self.store.append_trace(
            session.session_id,
            self.registration_agent.trace(selected_hospital_id, appointment.scheduled_at),
        )
        self.store.append_trace(
            session.session_id,
            self.navigation_agent.trace(appointment.location, navigation.destination),
        )

        return BookingResponse(appointment=appointment, navigation=navigation)

    def archive_document(self, request: DocumentArchiveRequest) -> DocumentArchiveResponse:
        session = self.store.get_session(request.session_id)
        archived_document = self.document_agent.run(
            request.document_title,
            request.document_text,
            issue_status=request.issue_status,
            source_filename=request.source_filename,
            source_image_url=request.source_image_url,
        )
        archived_document = self.document_storage.persist(
            request=request,
            archived_document=archived_document,
            fallback_department=session.triage.department,
        )
        care_instructions = self.instructions_agent.run(
            triage=session.triage,
            appointment=session.appointment,
            document=archived_document,
        )
        self.store.save_document(session.session_id, archived_document, care_instructions)
        self.store.append_trace(
            session.session_id,
            self.document_agent.trace(request.document_title or "无标题文档", archived_document.doc_type),
        )
        self.store.append_trace(
            session.session_id,
            self.instructions_agent.trace(archived_document.doc_type, care_instructions.follow_up_window or "复诊待定"),
        )

        return DocumentArchiveResponse(
            archived_document=archived_document,
            care_instructions=care_instructions,
        )

    def get_session(self, session_id: str) -> SessionState:
        return self.store.get_session(session_id)
