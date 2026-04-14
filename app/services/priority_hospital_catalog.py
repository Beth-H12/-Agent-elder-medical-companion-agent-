from typing import Dict, List, Optional

from sqlalchemy import select

from app.db.database import session_scope
from app.db.models import PriorityHospitalRecord


class PriorityHospitalCatalog:
    def list_by_city(self, city: str) -> List[Dict]:
        normalized_city = self._normalize_city(city)
        with session_scope() as session:
            records = session.scalars(
                select(PriorityHospitalRecord).where(PriorityHospitalRecord.city == normalized_city)
            ).all()
            return [self._to_dict(record) for record in records]

    def match_by_name(self, city: str, hospital_name: str) -> Optional[Dict]:
        normalized_city = self._normalize_city(city)
        normalized_name = self._normalize_name(hospital_name)
        for hospital in self.list_by_city(normalized_city):
            normalized_target = self._normalize_name(hospital["hospital_name"])
            if normalized_name == normalized_target:
                return hospital
            if normalized_target in normalized_name or normalized_name in normalized_target:
                return hospital
            for alias in hospital["aliases"]:
                normalized_alias = self._normalize_name(alias)
                if not normalized_alias:
                    continue
                if normalized_alias in normalized_name or normalized_name in normalized_alias:
                    return hospital
        return None

    @staticmethod
    def _normalize_name(name: str) -> str:
        return (
            str(name or "")
            .replace("（", "(")
            .replace("）", ")")
            .replace("总院", "")
            .replace("门诊部", "")
            .replace("门诊", "")
            .replace("医院", "医院")
            .strip()
            .split("(", 1)[0]
            .replace(" ", "")
        )

    @staticmethod
    def _normalize_city(city: str) -> str:
        text = str(city or "").strip()
        if not text:
            return ""
        if text.endswith("市"):
            return text
        return f"{text}市"

    @staticmethod
    def _to_dict(record: PriorityHospitalRecord) -> Dict:
        return {
            "hospital_id": record.hospital_id,
            "city": record.city,
            "hospital_name": record.hospital_name,
            "hospital_level": record.hospital_level,
            "official_url": record.official_url,
            "destination_query": record.destination_query,
            "aliases": record.aliases_json,
        }
