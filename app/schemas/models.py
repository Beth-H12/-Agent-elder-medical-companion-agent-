from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TransportMode(str, Enum):
    walking = "walking"
    bus = "bus"
    metro = "metro"
    taxi = "taxi"


class Preferences(BaseModel):
    prefer_low_crowd: bool = True
    prefer_direct_route: bool = True
    mobility_support_needed: bool = True


class IntakeRequest(BaseModel):
    user_name: str = "长者用户"
    age: Optional[int] = 68
    current_location: str
    transport_mode: TransportMode = TransportMode.metro
    symptom_text: str
    preferred_time: str = "明天上午"
    preferences: Preferences = Field(default_factory=Preferences)


class TriageResult(BaseModel):
    symptoms: List[str]
    department: str
    advice: str
    risk_flag: bool
    urgency: Literal["routine", "soon", "urgent"]
    warnings: List[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    travel_minutes: int
    transfer_count: int
    crowd_level: float
    department_match: int
    availability_bonus: int
    elder_friendly_bonus: int
    final_score: float


class HospitalCandidate(BaseModel):
    hospital_id: str
    hospital_name: str
    address: str
    hospital_level: Optional[str] = None
    booking_url: Optional[str] = None
    route: str
    route_steps: List[str] = Field(default_factory=list)
    reasons: List[str]
    score_breakdown: ScoreBreakdown


class IntakeResponse(BaseModel):
    session_id: str
    triage: TriageResult
    recommended_hospital: HospitalCandidate
    candidates: List[HospitalCandidate]
    suggested_next_action: str


class RegistrationRequest(BaseModel):
    session_id: str
    hospital_id: Optional[str] = None
    preferred_time: Optional[str] = None


class AppointmentResult(BaseModel):
    status: str
    hospital_id: str
    hospital_name: str
    booking_url: Optional[str] = None
    department: str
    doctor_type: str
    scheduled_at: str
    location: str
    route: str
    route_steps: List[str] = Field(default_factory=list)
    queue_tip: str
    check_in_before: str


class NavigationPlan(BaseModel):
    hospital_name: str
    appointment_time: str
    destination: str
    steps: List[str]
    arrive_before: str
    carry_items: List[str]


class BookingResponse(BaseModel):
    appointment: AppointmentResult
    navigation: NavigationPlan


class DocumentArchiveRequest(BaseModel):
    session_id: str
    document_title: Optional[str] = None
    document_text: Optional[str] = None
    uploaded_from: str = "camera"
    issue_status: Literal["有问题", "无问题"] = "有问题"
    source_filename: Optional[str] = None
    source_image_url: Optional[str] = None
    source_image_temp_path: Optional[str] = None


class ArchivedDocument(BaseModel):
    document_id: str = Field(default_factory=lambda: f"doc-{uuid4().hex[:8]}")
    doc_type: str
    hospital: Optional[str] = None
    department: Optional[str] = None
    date: Optional[str] = None
    summary: str
    key_points: List[str] = Field(default_factory=list)
    issue_status: Literal["有问题", "无问题"] = "有问题"
    source_filename: Optional[str] = None
    source_image_url: Optional[str] = None
    storage_directory: Optional[str] = None
    note_file_url: Optional[str] = None


class CareInstructions(BaseModel):
    simple_summary: str
    instructions: List[str]
    follow_up_needed: bool
    follow_up_window: Optional[str] = None


class DocumentArchiveResponse(BaseModel):
    archived_document: ArchivedDocument
    care_instructions: CareInstructions


class AgentTrace(BaseModel):
    agent_name: str
    input_summary: str
    output_summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SessionState(BaseModel):
    session_id: str = Field(default_factory=lambda: f"session-{uuid4().hex[:10]}")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    intake: IntakeRequest
    triage: TriageResult
    candidates: List[HospitalCandidate]
    appointment: Optional[AppointmentResult] = None
    navigation: Optional[NavigationPlan] = None
    documents: List[ArchivedDocument] = Field(default_factory=list)
    latest_care_instructions: Optional[CareInstructions] = None
    agent_trace: List[AgentTrace] = Field(default_factory=list)
