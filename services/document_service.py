import json
import uuid
import mimetypes
import socket
import ipaddress
from urllib.parse import urlparse, unquote
from pathlib import Path
from typing import List, Dict, Tuple

import requests
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


def _is_public_ip(hostname: str) -> bool:
    if not hostname:
        return False
    if hostname.lower() in {"localhost", "localhost.localdomain"}:
        return False
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError:
        return False

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def _pick_filename_from_url(url: str, content_type) -> str:
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).name
    name = secure_filename(name) if name else ""

    if name and Path(name).suffix:
        return name

    guessed_suffix = ""
    if content_type:
        content_type = content_type.split(";")[0].strip().lower()
        guessed_suffix = mimetypes.guess_extension(content_type) or ""

    if guessed_suffix and guessed_suffix in {".pdf", ".txt", ".md", ".json", ".csv", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".docx"}:
        return f"{uuid.uuid4().hex}{guessed_suffix}"

    return f"{uuid.uuid4().hex}.bin"


def download_file_from_url(url: str, upload_dir: Path, *, max_bytes: int = 64 * 1024 * 1024) -> Tuple[Path, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("仅支持 http/https 链接")
    if not parsed.netloc:
        raise ValueError("链接格式不正确")
    if parsed.username or parsed.password:
        raise ValueError("不支持带账号密码的链接")
    if not _is_public_ip(parsed.hostname or ""):
        raise ValueError("出于安全考虑，禁止访问内网/本机地址")

    upload_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    current_url = url
    response = None

    for _ in range(3):
        response = session.get(current_url, stream=True, timeout=(6, 20), allow_redirects=False)
        if response.is_redirect or response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location", "").strip()
            if not location:
                raise ValueError("链接跳转异常")
            next_url = requests.compat.urljoin(current_url, location)
            parsed_next = urlparse(next_url)
            if parsed_next.scheme not in {"http", "https"} or not parsed_next.netloc:
                raise ValueError("链接跳转异常")
            if not _is_public_ip(parsed_next.hostname or ""):
                raise ValueError("跳转到不安全地址，已拦截")
            current_url = next_url
            continue
        break

    if response is None:
        raise ValueError("无法获取该链接内容")

    if response.status_code >= 400:
        raise ValueError(f"下载失败（HTTP {response.status_code}）")

    length_header = response.headers.get("Content-Length", "")
    if length_header.isdigit() and int(length_header) > max_bytes:
        raise ValueError("文件太大，超过限制")

    content_type = response.headers.get("Content-Type", "")
    filename = _pick_filename_from_url(current_url, content_type)
    allowed_suffixes = {
        ".pdf",
        ".docx",
        ".pptx",
        ".txt",
        ".md",
        ".csv",
        ".json",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
    }
    if Path(filename).suffix.lower() not in allowed_suffixes:
        raise ValueError("暂不支持该链接文件类型，请提供 PDF/DOCX/PPTX/图片/TXT 等格式")
    target = upload_dir / filename
    counter = 1
    while target.exists():
        stem = target.stem.split("__")[0]
        target = upload_dir / f"{stem}__{counter}{target.suffix}"
        counter += 1

    total = 0
    try:
        with target.open("wb") as fp:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("文件太大，超过限制")
                fp.write(chunk)
    except Exception:
        if target.exists():
            try:
                target.unlink()
            except OSError:
                pass
        raise

    original_name = Path(unquote(urlparse(current_url).path)).name or filename
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
