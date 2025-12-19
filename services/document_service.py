import json
import uuid
from pathlib import Path
from typing import List, Dict, Tuple

from werkzeug.utils import secure_filename

from .ocr_service import extract_image_text


def load_documents(data_file: Path) -> List[Dict]:
    if not data_file.exists():
        return []
    try:
        with data_file.open("r", encoding="utf-8") as fp:
            return json.load(fp)
    except json.JSONDecodeError:
        return []


def store_documents(data_file: Path, documents: List[Dict]):
    data_file.parent.mkdir(parents=True, exist_ok=True)
    with data_file.open("w", encoding="utf-8") as fp:
        json.dump(documents, fp, ensure_ascii=False, indent=2)


def save_uploaded_file(file, upload_dir: Path) -> Tuple[Path, str]:
    upload_dir.mkdir(parents=True, exist_ok=True)
    original_name = file.filename
    filename = secure_filename(original_name)
    if not filename:
        filename = uuid.uuid4().hex
    target = upload_dir / filename
    counter = 1
    while target.exists():
        stem = target.stem.split("__")[0]
        target = upload_dir / f"{stem}__{counter}{target.suffix}"
        counter += 1
    file.save(target)
    return target, original_name


def extract_preview_text(file_path: Path) -> str:
    """提取用于 AI 分析的简短文本摘要"""
    suffix = file_path.suffix.lower()
    try:
        if suffix in {".txt", ".md", ".csv", ".json"}:
            return file_path.read_text(encoding="utf-8")[:5000]
        if suffix in {".pdf"}:
            from PyPDF2 import PdfReader  # type: ignore

            reader = PdfReader(str(file_path))
            pages_text = []
            for page in reader.pages[:5]:
                pages_text.append(page.extract_text() or "")
            return "\n".join(pages_text)
        if suffix in {".docx"}:
            from docx import Document  # type: ignore

            document = Document(str(file_path))
            paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
            return "\n".join(paragraphs[:100])
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            ocr_text = extract_image_text(file_path).strip()
            if ocr_text:
                return ocr_text
            return f"图片文件: {file_path.name}"
    except Exception:  # pylint: disable=broad-except
        return ""
    return ""


def build_page_markers(file_path: Path) -> List[Dict]:
    suffix = file_path.suffix.lower()
    markers: List[Dict] = []
    if suffix == ".pdf":
        try:
            from PyPDF2 import PdfReader  # type: ignore

            reader = PdfReader(str(file_path))
            total = len(reader.pages)
            for index in range(total):
                markers.append({"label": f"第 {index + 1} 页", "index": index + 1})
        except Exception:  # pylint: disable=broad-except
            pass
    else:
        markers.append({"label": file_path.name, "index": 1})
    return markers
