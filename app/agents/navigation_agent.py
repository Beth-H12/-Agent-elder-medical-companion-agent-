from app.agents.base import BaseAgent
from app.schemas.models import AppointmentResult, NavigationPlan


class NavigationAgent(BaseAgent):
    name = "NavigationAgent"

    def run(self, appointment: AppointmentResult) -> NavigationPlan:
        steps = [
            f"请在 {appointment.check_in_before} 前到达 {appointment.hospital_name}。",
            "先在门诊大厅自助机或人工窗口签到。",
            f"随后前往 {appointment.location} 候诊。",
            "听到叫号后进入诊室，并主动向医生说明主要不适和既往病史。",
        ]
        return NavigationPlan(
            hospital_name=appointment.hospital_name,
            appointment_time=appointment.scheduled_at,
            destination=appointment.location,
            steps=steps,
            arrive_before=appointment.check_in_before,
            carry_items=["身份证", "医保卡", "既往检查单", "日常用药清单"],
        )
