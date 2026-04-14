from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base ORM model."""


class HospitalRecord(Base):
    __tablename__ = "hospitals"

    hospital_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hospital_name: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    hospital_level: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    booking_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    nearby_regions_json: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    departments_json: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    crowd_level: Mapped[float] = mapped_column(Float, nullable=False)
    elder_friendly_features_json: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    transport_profiles_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    availability_json: Mapped[Dict[str, List[str]]] = mapped_column(JSON, nullable=False)
    layout_json: Mapped[Dict[str, str]] = mapped_column(JSON, nullable=False)


class PriorityHospitalRecord(Base):
    __tablename__ = "priority_hospitals"

    hospital_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    city: Mapped[str] = mapped_column(String(64), nullable=False)
    hospital_name: Mapped[str] = mapped_column(String(128), nullable=False)
    hospital_level: Mapped[str] = mapped_column(String(32), nullable=False)
    official_url: Mapped[str] = mapped_column(String(512), nullable=False)
    destination_query: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases_json: Mapped[List[str]] = mapped_column(JSON, nullable=False)


class SessionRecord(Base):
    __tablename__ = "medical_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    intake_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    triage_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    candidates_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    appointment_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    navigation_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    documents_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    latest_care_instructions_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    agent_trace_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)


class LLMCallLog(Base):
    __tablename__ = "llm_call_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    input_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    response_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
