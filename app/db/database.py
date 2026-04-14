from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.data.mock_hospitals import HOSPITALS
from app.data.xian_priority_hospitals import PRIORITY_HOSPITALS
from app.db.models import Base, HospitalRecord, PriorityHospitalRecord


def _create_engine():
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(settings.database_url, future=True, connect_args=connect_args)


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _apply_manual_migrations()
    seed_hospital_catalog()
    seed_priority_hospital_catalog()


def _apply_manual_migrations() -> None:
    inspector = inspect(engine)
    hospital_columns = {column["name"] for column in inspector.get_columns("hospitals")}
    with engine.begin() as connection:
        if "booking_url" not in hospital_columns:
            connection.execute(text("ALTER TABLE hospitals ADD COLUMN booking_url VARCHAR(512)"))
        if "hospital_level" not in hospital_columns:
            connection.execute(text("ALTER TABLE hospitals ADD COLUMN hospital_level VARCHAR(64)"))


def seed_hospital_catalog() -> None:
    with session_scope() as session:
        for hospital in HOSPITALS:
            record = session.get(HospitalRecord, hospital["id"])
            if record is None:
                record = HospitalRecord(hospital_id=hospital["id"])
                session.add(record)

            record.hospital_name = hospital["name"]
            record.address = hospital["address"]
            record.hospital_level = hospital.get("hospital_level")
            record.booking_url = hospital.get("booking_url")
            record.nearby_regions_json = hospital["nearby_regions"]
            record.departments_json = hospital["departments"]
            record.crowd_level = hospital["crowd_level"]
            record.elder_friendly_features_json = hospital["elder_friendly_features"]
            record.transport_profiles_json = hospital["transport_profiles"]
            record.availability_json = hospital["availability"]
            record.layout_json = hospital["layout"]


def seed_priority_hospital_catalog() -> None:
    with session_scope() as session:
        for hospital in PRIORITY_HOSPITALS:
            record = session.get(PriorityHospitalRecord, hospital["hospital_id"])
            if record is None:
                record = PriorityHospitalRecord(hospital_id=hospital["hospital_id"])
                session.add(record)

            record.city = hospital["city"]
            record.hospital_name = hospital["hospital_name"]
            record.hospital_level = hospital["hospital_level"]
            record.official_url = hospital["official_url"]
            record.destination_query = hospital["destination_query"]
            record.aliases_json = hospital["aliases"]
