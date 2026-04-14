from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


class DocumentUploadService:
    def __init__(self) -> None:
        self.upload_dir = Path(__file__).resolve().parents[2] / "static" / "uploads" / "tmp"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_image(self, upload: UploadFile) -> dict:
        content_type = (upload.content_type or "").lower()
        if not content_type.startswith("image/"):
            raise ValueError("请上传图片文件，例如检查单照片或报告截图。")

        suffix = Path(upload.filename or "").suffix.lower() or ".jpg"
        stored_name = f"doc-{uuid4().hex[:10]}{suffix}"
        destination = self.upload_dir / stored_name
        content = await upload.read()
        if not content:
            raise ValueError("上传的图片内容为空，请重新选择图片。")

        destination.write_bytes(content)
        return {
            "stored_name": stored_name,
            "original_name": upload.filename or stored_name,
            "content_type": content_type,
            "size": len(content),
            "temp_path": str(destination),
            "url": f"/static/uploads/tmp/{stored_name}",
        }
