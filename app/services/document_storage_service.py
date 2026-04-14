from datetime import date, datetime
from pathlib import Path
from shutil import move
from typing import Optional

from app.schemas.models import ArchivedDocument, DocumentArchiveRequest


class DocumentStorageService:
    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parents[2] / "static" / "medical_records"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def persist(
        self,
        request: DocumentArchiveRequest,
        archived_document: ArchivedDocument,
        fallback_department: str,
    ) -> ArchivedDocument:
        report_date = self._normalize_date(archived_document.date) or date.today().isoformat()
        department = self._sanitize_segment(archived_document.department or fallback_department or "未分科")
        issue_status = archived_document.issue_status if archived_document.issue_status in {"有问题", "无问题"} else "有问题"
        folder_name = f"{report_date}-{department}"
        target_dir = self.base_dir / folder_name / issue_status
        target_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%H%M%S")
        note_name = f"{timestamp}-note.txt"
        note_path = target_dir / note_name
        note_path.write_text(
            self._build_note_content(request, archived_document, report_date, department, issue_status),
            encoding="utf-8",
        )

        image_url = archived_document.source_image_url
        if request.source_image_temp_path:
            source_path = Path(request.source_image_temp_path)
            if source_path.exists():
                suffix = source_path.suffix.lower() or ".jpg"
                image_name = f"{timestamp}-image{suffix}"
                image_path = target_dir / image_name
                move(str(source_path), str(image_path))
                image_url = self._to_static_url(image_path)

        archived_document.date = report_date
        archived_document.department = archived_document.department or fallback_department or "未分科"
        archived_document.issue_status = issue_status
        archived_document.source_image_url = image_url
        archived_document.storage_directory = self._to_static_url(target_dir)
        archived_document.note_file_url = self._to_static_url(note_path)
        return archived_document

    def clear(self) -> None:
        if not self.base_dir.exists():
            return
        for child in self.base_dir.rglob("*"):
            if child.is_file():
                child.unlink()
        for child in sorted(self.base_dir.rglob("*"), reverse=True):
            if child.is_dir():
                child.rmdir()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_date(raw_date: Optional[str]) -> Optional[str]:
        if not raw_date:
            return None
        text = str(raw_date).strip().replace("/", "-")
        if len(text) == 10:
            return text
        return None

    @staticmethod
    def _sanitize_segment(value: str) -> str:
        text = str(value or "").strip()
        for token in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
            text = text.replace(token, "-")
        return text or "未分科"

    def _build_note_content(
        self,
        request: DocumentArchiveRequest,
        archived_document: ArchivedDocument,
        report_date: str,
        department: str,
        issue_status: str,
    ) -> str:
        lines = [
            f"文档标题：{request.document_title or archived_document.doc_type}",
            f"检查日期：{report_date}",
            f"科室：{department}",
            f"分类：{issue_status}",
            f"文档类型：{archived_document.doc_type}",
            f"摘要：{archived_document.summary}",
        ]
        if archived_document.source_filename:
            lines.append(f"图片文件：{archived_document.source_filename}")
        if archived_document.key_points:
            lines.append("重点内容：")
            lines.extend(f"- {item}" for item in archived_document.key_points)
        if request.document_text:
            lines.append("")
            lines.append("文字说明：")
            lines.append(request.document_text.strip())
        return "\n".join(lines).strip() + "\n"

    def _to_static_url(self, path: Path) -> str:
        relative = path.relative_to(self.base_dir.parents[0])
        return "/static/" + "/".join(relative.parts)
