from typing import Dict, List

from sqlalchemy import select

from app.db.database import session_scope
from app.db.models import HospitalRecord


class HospitalCatalog:
    def list_hospitals(self) -> List[Dict]:
        with session_scope() as session:
            records = session.scalars(select(HospitalRecord)).all()
            return [self._to_dict(record) for record in records]

    def get_hospital(self, hospital_id: str) -> Dict:
        with session_scope() as session:
            record = session.get(HospitalRecord, hospital_id)
            if record is None:
                raise ValueError(f"Unknown hospital: {hospital_id}")
            return self._to_dict(record)

    def all_departments(self) -> List[str]:
        hospitals = self.list_hospitals()
        return sorted(
            {
                department
                for hospital in hospitals
                for department in hospital["departments"]
            }
        )

    @staticmethod
    def _to_dict(record: HospitalRecord) -> Dict:
        return {
            "id": record.hospital_id,
            "name": record.hospital_name,
            "address": record.address,
            "hospital_level": record.hospital_level,
            "booking_url": record.booking_url,
            "nearby_regions": record.nearby_regions_json,
            "departments": record.departments_json,
            "crowd_level": record.crowd_level,
            "elder_friendly_features": record.elder_friendly_features_json,
            "transport_profiles": record.transport_profiles_json,
            "availability": record.availability_json,
            "layout": record.layout_json,
        }
