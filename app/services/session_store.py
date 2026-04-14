from typing import List

from sqlalchemy import delete

from app.db.database import session_scope
from app.db.models import LLMCallLog, SessionRecord
from app.schemas.models import (
    AgentTrace,
    AppointmentResult,
    ArchivedDocument,
    CareInstructions,
    HospitalCandidate,
    IntakeRequest,
    NavigationPlan,
    SessionState,
    TriageResult,
)


class SessionStore:
    def create_session(
        self,
        intake: IntakeRequest,
        triage: TriageResult,
        candidates: List[HospitalCandidate],
    ) -> SessionState:
        session_state = SessionState(intake=intake, triage=triage, candidates=candidates)
        payload = self._state_to_record(session_state)
        with session_scope() as session:
            session.add(SessionRecord(**payload))
        return session_state

    def get_session(self, session_id: str) -> SessionState:
        with session_scope() as session:
            record = session.get(SessionRecord, session_id)
            if record is None:
                raise KeyError(f"Session not found: {session_id}")
            return self._record_to_state(record)

    def save_appointment(
        self, session_id: str, appointment: AppointmentResult, navigation: NavigationPlan
    ) -> SessionState:
        with session_scope() as session:
            record = self._get_record(session, session_id)
            record.appointment_json = appointment.model_dump(mode="json")
            record.navigation_json = navigation.model_dump(mode="json")
            return self._record_to_state(record)

    def save_document(
        self,
        session_id: str,
        document: ArchivedDocument,
        care_instructions: CareInstructions,
    ) -> SessionState:
        with session_scope() as session:
            record = self._get_record(session, session_id)
            documents = list(record.documents_json or [])
            documents.append(document.model_dump(mode="json"))
            record.documents_json = documents
            record.latest_care_instructions_json = care_instructions.model_dump(mode="json")
            return self._record_to_state(record)

    def append_trace(self, session_id: str, trace: AgentTrace) -> None:
        with session_scope() as session:
            record = self._get_record(session, session_id)
            trace_items = list(record.agent_trace_json or [])
            trace_items.append(trace.model_dump(mode="json"))
            record.agent_trace_json = trace_items

    def log_llm_call(
        self, model_name: str, input_excerpt: str, response_excerpt: str, status: str
    ) -> None:
        with session_scope() as session:
            session.add(
                LLMCallLog(
                    model_name=model_name,
                    input_excerpt=input_excerpt[:500],
                    response_excerpt=response_excerpt[:1000],
                    status=status,
                )
            )

    def clear(self) -> None:
        with session_scope() as session:
            session.execute(delete(SessionRecord))
            session.execute(delete(LLMCallLog))

    @staticmethod
    def _get_record(session, session_id: str) -> SessionRecord:
        record = session.get(SessionRecord, session_id)
        if record is None:
            raise KeyError(f"Session not found: {session_id}")
        return record

    @staticmethod
    def _state_to_record(session_state: SessionState) -> dict:
        return {
            "session_id": session_state.session_id,
            "created_at": session_state.created_at,
            "intake_json": session_state.intake.model_dump(mode="json"),
            "triage_json": session_state.triage.model_dump(mode="json"),
            "candidates_json": [item.model_dump(mode="json") for item in session_state.candidates],
            "appointment_json": None,
            "navigation_json": None,
            "documents_json": [],
            "latest_care_instructions_json": None,
            "agent_trace_json": [],
        }

    @staticmethod
    def _record_to_state(record: SessionRecord) -> SessionState:
        return SessionState(
            session_id=record.session_id,
            created_at=record.created_at,
            intake=IntakeRequest.model_validate(record.intake_json),
            triage=TriageResult.model_validate(record.triage_json),
            candidates=[
                HospitalCandidate.model_validate(candidate)
                for candidate in (record.candidates_json or [])
            ],
            appointment=AppointmentResult.model_validate(record.appointment_json)
            if record.appointment_json
            else None,
            navigation=NavigationPlan.model_validate(record.navigation_json)
            if record.navigation_json
            else None,
            documents=[
                ArchivedDocument.model_validate(document)
                for document in (record.documents_json or [])
            ],
            latest_care_instructions=CareInstructions.model_validate(
                record.latest_care_instructions_json
            )
            if record.latest_care_instructions_json
            else None,
            agent_trace=[
                AgentTrace.model_validate(trace)
                for trace in (record.agent_trace_json or [])
            ],
        )
