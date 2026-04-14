from typing import Optional

from app.agents.base import BaseAgent
from app.schemas.models import ArchivedDocument, AppointmentResult, CareInstructions, TriageResult


class CareInstructionsAgent(BaseAgent):
    name = "CareInstructionsAgent"

    def run(
        self,
        triage: TriageResult,
        appointment: Optional[AppointmentResult],
        document: ArchivedDocument,
    ) -> CareInstructions:
        instructions = [
            "把本次报告和既往检查单一起保存，下次复诊时带给医生查看。",
            "按医生已开具的药物和服药时间执行，不要自行停药或加量。",
        ]
        follow_up_window = None

        if triage.department == "心内科":
            instructions.append("近期避免剧烈运动，若再次出现明显胸闷或胸痛，请及时就医。")
            follow_up_window = "1周内复诊"
        elif triage.department == "呼吸内科":
            instructions.append("注意保暖和休息，如气短或咳嗽加重请尽快复诊。")
            follow_up_window = "3至7天内复诊"
        else:
            instructions.append("若症状持续或加重，请尽快复诊，由医生进一步评估。")
            follow_up_window = "按医生建议复诊"

        if document.doc_type == "血常规报告":
            instructions.append("血常规报告建议和门诊问诊结果一起解读，不要自行判断异常指标。")
        elif document.doc_type == "CT影像报告":
            instructions.append("影像报告请结合医生面诊解读，必要时携带胶片或电子影像。")
        elif document.doc_type == "处方单":
            instructions.append("请核对药名与服用频次，家属可帮助设置每日提醒。")

        if triage.risk_flag:
            instructions.append("若症状短时间内明显加重，请不要等待预约时间，直接寻求急诊帮助。")

        summary = "已为您生成老年友好的检查后提示，方便后续复诊和家庭照护。"
        if appointment:
            summary = f"结合 {appointment.hospital_name}{appointment.department} 就诊记录，已生成后续注意事项。"

        return CareInstructions(
            simple_summary=summary,
            instructions=instructions,
            follow_up_needed=True,
            follow_up_window=follow_up_window,
        )
