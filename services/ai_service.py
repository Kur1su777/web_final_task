import os
from typing import Dict

try:
    import dashscope
    from dashscope import Generation
except ImportError:  # pragma: no cover
    dashscope = None
    Generation = None


class DocumentAIClient:
    """轻量封装 DashScope DeepSeek 接口，用于文档阅读助手场景"""

    ERROR_PREFIXES = ("调用 DashScope 失败", "调用 DeepSeek 失败")

    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        self.model = os.getenv("DASHSCOPE_MODEL", "deepseek-v3.2").strip()
        self.finance_model = os.getenv("DASHSCOPE_FINANCE_MODEL", "").strip()
        self.temperature = float(os.getenv("DASHSCOPE_TEMPERATURE", "0.4"))
        self.enable_thinking = os.getenv("DASHSCOPE_ENABLE_THINKING", "1") != "0"
        base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")

        if dashscope is not None:
            dashscope.base_http_api_url = base_url

    def _request(self, system_prompt: str, user_prompt: str, *, model: str = None) -> str:
        if Generation is None:
            return "调用 DashScope 失败: 未安装 dashscope SDK，请先 pip install dashscope"
        if not self.api_key:
            return "调用 DashScope 失败: 未配置 DASHSCOPE_API_KEY，无法生成内容。"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        call_kwargs = {
            "api_key": self.api_key,
            "model": model or self.model,
            "messages": messages,
            "result_format": "message",
            "temperature": self.temperature,
        }
        if self.enable_thinking:
            call_kwargs["enable_thinking"] = True

        try:
            response = Generation.call(**call_kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            return f"调用 DashScope 失败: {exc}"

        if getattr(response, "status_code", None) == 200:
            message = response.output.choices[0].message
            content = (message.content or "").strip()
            if content:
                return content
            reasoning = getattr(message, "reasoning_content", "")
            return reasoning.strip() if reasoning else ""

        error_code = getattr(response, "code", "unknown")
        error_msg = getattr(response, "message", "unknown error")
        return f"调用 DashScope 失败: {error_code} - {error_msg}"

    def _call_models(self, system_prompt: str, user_prompt: str, *, prefer_finance: bool = False) -> str:
        models: list[str] = []
        if prefer_finance and self.finance_model and self.finance_model != self.model:
            models.append(self.finance_model)
        models.append(self.model)

        last_response = ""
        for model_name in models:
            response = self._request(system_prompt, user_prompt, model=model_name)
            last_response = response
            if not any(response.startswith(prefix) for prefix in self.ERROR_PREFIXES):
                return response
        return last_response

    def categorize_document(self, filename: str, ocr_text: str) -> str:
        """
        分类模块暂未接入，返回空字符串为占位。
        未来接入模型后可在此处实现真正分类逻辑。
        """
        return ""

    def summarize_document(self, ocr_text: str, filename: str) -> str:
        system_prompt = (
            "你是一名文档阅读助手，善于迅速提炼长文档的关键信息。"
            "输出需使用流畅的中文，力求简洁明了，避免 JSON 或编号列表。"
        )
        user_prompt = (
            f"文件名: {filename}\n"
            "以下是文档的文字内容（可能包含噪声）：\n"
            f"{ocr_text[:4000]}\n"
            "请概括 2-3 个核心要点，每个要点独立成句，并使用换行分隔。"
        )
        return self._call_models(system_prompt, user_prompt, prefer_finance=True)

    def deep_read_document(self, category: str, summary: str, ocr_text: str, filename: str) -> str:
        category_hint = category.strip() or "未分类"
        summary_hint = ""
        if summary and not any(summary.startswith(prefix) for prefix in self.ERROR_PREFIXES) and not summary.strip().startswith("总结失败"):
            summary_hint = summary

        system_prompt = (
            "你是一名文章精读助手，需要输出更深入的阅读要点。"
            "回答必须基于提供的分类、摘要及 OCR 文本，语言通俗易懂，避免 JSON。"
        )
        user_prompt = (
            f"文件名: {filename}\n"
            f"文档分类提示: {category_hint}\n"
            f"已识别内容(截断):\n{ocr_text[:2000]}\n"
            f"文档摘要(如有):\n{summary_hint}\n"
            "请输出精读要点：背景/问题、核心论点、关键证据、结论或启发，各点独立成句，4-6 行。"
        )
        return self._call_models(system_prompt, user_prompt, prefer_finance=True)

    def explain_document(self, category: str, summary: str, ocr_text: str, filename: str) -> str:
        return self.deep_read_document(category, summary, ocr_text, filename)

    def translate_document(self, summary: str, ocr_text: str, filename: str) -> str:
        summary_hint = ""
        if summary and not any(summary.startswith(prefix) for prefix in self.ERROR_PREFIXES) and not summary.strip().startswith("总结失败"):
            summary_hint = summary

        system_prompt = (
            "你是一名专业翻译助手，需要将内容翻译为英文。"
            "如果原文已经是英文，请翻译为中文。"
        )
        user_prompt = (
            f"文件名: {filename}\n"
            f"文档摘要(如有):\n{summary_hint}\n"
            f"内容摘录(截断):\n{ocr_text[:2500]}\n"
            "请输出通顺的翻译结果，保留原意，避免分点编号。"
        )
        return self._call_models(system_prompt, user_prompt, prefer_finance=False)

    def mindmap_document(self, summary: str, ocr_text: str, filename: str) -> str:
        summary_hint = ""
        if summary and not any(summary.startswith(prefix) for prefix in self.ERROR_PREFIXES) and not summary.strip().startswith("总结失败"):
            summary_hint = summary

        system_prompt = (
            "你是一名思维导图整理助手，需要用文本形式输出层级结构。"
            "只输出文本导图，不要 JSON。"
        )
        user_prompt = (
            f"文件名: {filename}\n"
            f"文档摘要(如有):\n{summary_hint}\n"
            f"内容摘录(截断):\n{ocr_text[:2000]}\n"
            "请输出思维导图，使用如下格式：\n"
            "- 主题\n"
            "  - 分支一\n"
            "    - 子点\n"
            "  - 分支二"
        )
        return self._call_models(system_prompt, user_prompt, prefer_finance=False)

    def generate_document_insights(self, text: str, filename: str) -> Dict[str, str]:
        category = (self.categorize_document(filename, text) or "").strip()
        summary = self.summarize_document(text, filename)
        deep_read = self.deep_read_document(category, summary, text, filename)
        translation = self.translate_document(summary, text, filename)
        mindmap = self.mindmap_document(summary, text, filename)

        if isinstance(summary, str):
            summary = summary.strip()
        if isinstance(deep_read, str):
            deep_read = deep_read.strip()
        if isinstance(translation, str):
            translation = translation.strip()
        if isinstance(mindmap, str):
            mindmap = mindmap.strip()

        if isinstance(summary, str) and any(summary.startswith(prefix) for prefix in self.ERROR_PREFIXES):
            summary = f"总结失败: {summary}"
        if isinstance(deep_read, str) and any(deep_read.startswith(prefix) for prefix in self.ERROR_PREFIXES):
            deep_read = f"精读失败: {deep_read}"
        if isinstance(translation, str) and any(translation.startswith(prefix) for prefix in self.ERROR_PREFIXES):
            translation = f"翻译失败: {translation}"
        if isinstance(mindmap, str) and any(mindmap.startswith(prefix) for prefix in self.ERROR_PREFIXES):
            mindmap = f"导图失败: {mindmap}"

        return {
            "category": category,
            "summary": summary,
            "deep_read": deep_read,
            "translation": translation,
            "mindmap": mindmap,
        }


    def ask_about_document(self, question: str, filename: str, document_excerpt: str) -> str:
        system_prompt = (
            "你是一名专业的文件助手，将根据提供的文档内容回答用户的问题。"
            "若信息不足，请清楚说明。"
        )
        user_prompt = (
            f"文件名: {filename}\n"
            "文档摘录(截断):\n"
            f"{document_excerpt[:3500]}\n"
            f"用户问题: {question}\n"
            "请用中文回答。"
        )
        return self._request(system_prompt, user_prompt)

    def ask_about_documents(
        self,
        question: str,
        primary_filename: str,
        primary_excerpt: str,
        secondary_filename: str,
        secondary_excerpt: str,
    ) -> str:
        system_prompt = (
            "你是一名文档对比助手，需要结合两份文档回答问题。"
            "回答中如涉及差异，请明确指出对应的文档。"
        )
        user_prompt = (
            f"文档A: {primary_filename}\n"
            f"文档A摘录(截断):\n{primary_excerpt[:2500]}\n"
            f"文档B: {secondary_filename}\n"
            f"文档B摘录(截断):\n{secondary_excerpt[:2500]}\n"
            f"用户问题: {question}\n"
            "请用中文回答，必要时给出对比结论。"
        )
        return self._request(system_prompt, user_prompt)
