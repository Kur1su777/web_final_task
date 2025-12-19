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

    def explain_document(self, category: str, summary: str, ocr_text: str, filename: str) -> str:
        category_hint = category.strip() or "未分类"
        summary_hint = ""
        if summary and not any(summary.startswith(prefix) for prefix in self.ERROR_PREFIXES) and not summary.strip().startswith("总结失败"):
            summary_hint = summary

        system_prompt = (
            "你是一名知识型文档讲解员，需要向普通用户解释文档内容的意义。"
            "回答必须基于提供的分类、摘要及 OCR 文本，语言通俗易懂，避免 JSON。"
        )
        user_prompt = (
            f"文件名: {filename}\n"
            f"文档分类提示: {category_hint}\n"
            f"已识别内容(截断):\n{ocr_text[:2000]}\n"
            f"文档摘要(如有):\n{summary_hint}\n"
            "请解释这份文档的核心观点、可行行动或参考价值，控制在 3-5 句。"
        )
        return self._call_models(system_prompt, user_prompt, prefer_finance=True)

    def generate_document_insights(self, text: str, filename: str) -> Dict[str, str]:
        category = (self.categorize_document(filename, text) or "").strip()
        summary = self.summarize_document(text, filename)
        explanation = self.explain_document(category, summary, text, filename)

        if isinstance(summary, str):
            summary = summary.strip()
        if isinstance(explanation, str):
            explanation = explanation.strip()

        if isinstance(summary, str) and any(summary.startswith(prefix) for prefix in self.ERROR_PREFIXES):
            summary = f"总结失败: {summary}"
        if isinstance(explanation, str) and any(
            explanation.startswith(prefix) for prefix in self.ERROR_PREFIXES
        ):
            explanation = f"解释失败: {explanation}"

        return {
            "category": category,
            "summary": summary,
            "explanation": explanation,
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
