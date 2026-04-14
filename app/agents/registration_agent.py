from app.agents.base import BaseAgent
from app.core.config import settings
from app.schemas.models import AppointmentResult, HospitalCandidate
from app.services.hospital_catalog import HospitalCatalog
from app.utils.time_parser import choose_best_slot, minus_minutes, parse_preferred_window


class RegistrationAgent(BaseAgent):
    name = "RegistrationAgent"

    def __init__(self, catalog: HospitalCatalog) -> None:
        self.catalog = catalog

    def run(
        self,
        hospital_id: str,
        department: str,
        preferred_time: str,
        route_summary: str = "",
        selected_candidate: HospitalCandidate = None,
    ) -> AppointmentResult:
        try:
            hospital = self.catalog.get_hospital(hospital_id)
        except ValueError:
            return self._build_live_registration(selected_candidate, department, preferred_time, route_summary)

        slots = hospital["availability"].get(department, [])
        selected_slot = choose_best_slot(slots, preferred_time, settings.demo_reference_date)
        if not selected_slot:
            raise ValueError(f"{hospital['name']} 暂无 {department} 可用号源")

        return AppointmentResult(
            status="success",
            hospital_id=hospital["id"],
            hospital_name=hospital["name"],
            booking_url=hospital.get("booking_url"),
            department=department,
            doctor_type="普通门诊",
            scheduled_at=selected_slot,
            location=hospital["layout"][department],
            route=route_summary or hospital["transport_profiles"]["metro"]["route"],
            route_steps=selected_candidate.route_steps if selected_candidate else [],
            queue_tip="建议您提前到院完成签到，避免错过叫号。",
            check_in_before=minus_minutes(selected_slot, settings.default_check_in_buffer_minutes),
        )

    @staticmethod
    def _build_live_registration(
        selected_candidate: HospitalCandidate,
        department: str,
        preferred_time: str,
        route_summary: str,
    ) -> AppointmentResult:
        if selected_candidate is None:
            raise ValueError("未找到可用于挂号的医院候选信息")

        target_date, window = parse_preferred_window(preferred_time, settings.demo_reference_date)
        if window:
            hour = window[0].hour + 1
            minute = 30
        else:
            hour = 10
            minute = 0
        scheduled_at = target_date.strftime("%Y-%m-%d") + f" {hour:02d}:{minute:02d}"

        return AppointmentResult(
            status="pending_official_booking",
            hospital_id=selected_candidate.hospital_id,
            hospital_name=selected_candidate.hospital_name,
            booking_url=selected_candidate.booking_url,
            department=department,
            doctor_type="官网预约",
            scheduled_at=scheduled_at,
            location="请先前往门诊大厅导医台确认分诊与候诊区域",
            route=route_summary or selected_candidate.route,
            route_steps=selected_candidate.route_steps,
            queue_tip="当前为官网预约引导，请打开医院官网或搜索官网完成最终挂号。",
            check_in_before=minus_minutes(scheduled_at, settings.default_check_in_buffer_minutes),
        )
