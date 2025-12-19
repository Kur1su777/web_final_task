import base64
import os
from pathlib import Path
from typing import Optional

import requests

DEFAULT_BAIDU_OCR_KEY = (
    "bce-v3/ALTAK-xFMZoXtvAUOk6XgTe9hxr/930e05f6f6184d73cd9409c35de1756968702639"
)


def call_baidu_ocr(image_path: Path) -> Optional[str]:
    """调用百度 OCR 接口，若失败返回 None。"""
    api_key = os.getenv("BAIDU_OCR_API_KEY") or DEFAULT_BAIDU_OCR_KEY
    if not api_key:
        return None

    try:
        with image_path.open("rb") as img:
            image_base64 = base64.b64encode(img.read()).decode("utf-8")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {api_key}",
        }
        api_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
        resp = requests.post(api_url, headers=headers, data={"image": image_base64}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "words_result" in data:
            return "\n".join(item["words"] for item in data["words_result"])
    except Exception:  # pylint: disable=broad-except
        return None
    return None


def basic_pillow_extract(image_path: Path) -> str:
    try:
        from PIL import Image  # type: ignore
        import pytesseract  # type: ignore

        text = pytesseract.image_to_string(Image.open(str(image_path)), lang="chi_sim+eng")
        return text.strip()
    except Exception:
        return ""


def extract_image_text(image_path: Path) -> str:
    text = call_baidu_ocr(image_path)
    if text:
        return text
    fallback = basic_pillow_extract(image_path)
    if fallback:
        return fallback
    # 兜底信息
    return f"图片文件: {image_path.name}"
