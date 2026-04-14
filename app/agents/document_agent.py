from typing import List, Optional

from app.agents.base import BaseAgent
from app.schemas.models import ArchivedDocument
from app.services.hospital_catalog import HospitalCatalog
from app.utils.text import extract_date, extract_first_match, normalize_lines


class DocumentArchiveAgent(BaseAgent):
    name = "DocumentArchiveAgent"

    DOC_TYPE_RULES = {
        "血常规报告": ["白细胞", "红细胞", "血红蛋白", "中性粒细胞"],
        "CT影像报告": ["CT", "影像所见", "印象"],
        "心电图报告": ["心电图", "窦性心律", "ST-T"],
        "处方单": ["处方", "用法用量", "每日", "片"],
        "门诊病历": ["主诉", "现病史", "查体", "门诊病历"],
    }

    def __init__(self, catalog: HospitalCatalog) -> None:
        self.catalog = catalog

    def run(
        self,
        document_title: Optional[str],
        document_text: Optional[str],
        issue_status: str = "有问题",
        source_filename: Optional[str] = None,
        source_image_url: Optional[str] = None,
    ) -> ArchivedDocument:
        safe_text = (document_text or "").strip()
        combined_text = "\n".join(filter(None, [document_title, source_filename, safe_text]))
        doc_type = self._classify_doc_type(combined_text)
        hospital_names = [item["name"] for item in self.catalog.list_hospitals()]
        hospital = extract_first_match(combined_text, hospital_names)
        department = extract_first_match(combined_text, self.catalog.all_departments())
        report_date = extract_date(combined_text)
        key_points = normalize_lines(safe_text)
        if not key_points and source_filename:
            key_points = [
                f"已上传图片：{source_filename}",
                "暂未提供文字识别内容，可稍后补充文字说明以获得更准确摘要。",
            ]
        summary = self._build_summary(doc_type, hospital, department, key_points, bool(source_filename))

        return ArchivedDocument(
            doc_type=doc_type,
            hospital=hospital,
            department=department,
            date=report_date,
            summary=summary,
            key_points=key_points[:4],
            issue_status=issue_status if issue_status in {"有问题", "无问题"} else "有问题",
            source_filename=source_filename,
            source_image_url=source_image_url,
        )

    def _classify_doc_type(self, text: str) -> str:
        for doc_type, keywords in self.DOC_TYPE_RULES.items():
            if any(keyword in text for keyword in keywords):
                return doc_type
        return "检查资料"

    @staticmethod
    def _build_summary(
        doc_type: str,
        hospital: Optional[str],
        department: Optional[str],
        key_points: List[str],
        has_image_source: bool,
    ) -> str:
        source = "本次上传资料"
        if hospital or department:
            source = f"{hospital or '本次'}{department or ''}资料"

        if key_points:
            return f"已归档为{doc_type}，来源为{source}，重点内容包含：{key_points[0][:40]}"
        if has_image_source:
            return f"已收到{doc_type}图片，来源为{source}，可继续补充文字说明帮助系统整理重点。"
        return f"已归档为{doc_type}，来源为{source}。"
