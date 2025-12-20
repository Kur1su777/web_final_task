# 新版智能阅读平台
import os
import json
import uuid
import datetime
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    send_from_directory,
    abort,
)

from services.ai_service import DocumentAIClient
from services.document_service import (
    save_uploaded_file,
    load_documents,
    store_documents,
    extract_preview_text,
    build_page_markers,
)


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
DATA_FILE = BASE_DIR / "data" / "metadata.json"

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64MB

UPLOAD_FOLDER.mkdir(exist_ok=True, parents=True)

ai_client = DocumentAIClient()


def get_document_or_404(doc_id: str):
    documents = load_documents(DATA_FILE)
    for doc in documents:
        if doc["id"] == doc_id:
            return doc, documents
    abort(404)


@app.route("/")
def index():
    documents = load_documents(DATA_FILE)
    recent_docs = sorted(documents, key=lambda d: d["uploaded_at"], reverse=True)[:6]
    return render_template("upload.html", documents=recent_docs)


@app.route("/reader/<doc_id>")
def reader(doc_id):
    document, _ = get_document_or_404(doc_id)
    file_path = Path(document["filepath"])
    preview_type = "pdf"
    if file_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        preview_type = "image"
    elif file_path.suffix.lower() not in {".pdf"}:
        preview_type = "text"

    page_markers = build_page_markers(file_path)
    preview_text = ""
    if preview_type == "text":
        preview_text = extract_preview_text(file_path)[:800] or "暂不支持该文件预览，请尝试下载后查看。"
    show_thumbnails = preview_type == "pdf" and len(page_markers) > 1
    return render_template(
        "reader.html",
        document=document,
        preview_type=preview_type,
        page_markers=page_markers,
        preview_text=preview_text,
        show_thumbnails=show_thumbnails,
    )


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/api/documents", methods=["GET"])
def api_list_documents():
    documents = load_documents(DATA_FILE)
    documents.sort(key=lambda d: d["uploaded_at"], reverse=True)
    return jsonify({"success": True, "documents": documents})


@app.route("/api/documents/<doc_id>", methods=["GET"])
def api_get_document(doc_id):
    document, _ = get_document_or_404(doc_id)
    return jsonify({"success": True, "document": document})


def _remove_document_entry(documents, doc_id):
    target = next((doc for doc in documents if doc["id"] == doc_id), None)
    if not target:
        return False

    filepath = Path(target["filepath"])
    if filepath.exists():
        try:
            filepath.unlink()
        except OSError:
            pass

    documents.remove(target)
    return True


@app.route("/api/documents/<doc_id>", methods=["DELETE"])
def api_delete_document(doc_id):
    documents = load_documents(DATA_FILE)
    if not _remove_document_entry(documents, doc_id):
        return jsonify({"success": False, "error": "记录不存在"}), 404
    store_documents(DATA_FILE, documents)
    return jsonify({"success": True})


@app.route("/api/documents/clear", methods=["POST"])
def api_clear_documents():
    documents = load_documents(DATA_FILE)
    for doc in list(documents):
        _remove_document_entry(documents, doc["id"])
    store_documents(DATA_FILE, [])
    return jsonify({"success": True})


@app.route("/api/documents/<doc_id>/analysis", methods=["GET"])
def api_document_analysis(doc_id):
    document, documents = get_document_or_404(doc_id)

    analysis_payload = document.get("analysis") or {}
    required_keys = {"summary", "deep_read", "translation", "mindmap"}
    needs_refresh = not analysis_payload or not required_keys.issubset(analysis_payload.keys())

    if needs_refresh:
        file_path = Path(document["filepath"])
        preview_text = extract_preview_text(file_path)
        if not preview_text:
            preview_text = f"文件名: {document['original_name']}\n文件类型: {file_path.suffix}\n请基于文件名和上下文给予大致分析。"

        analysis = ai_client.generate_document_insights(
            preview_text,
            document["original_name"],
        )
        document["analysis"] = analysis
        document["classification"] = analysis.get("category", "")
        store_documents(DATA_FILE, documents)

    return jsonify({"success": True, "analysis": document["analysis"]})


@app.route("/api/documents/<doc_id>/ask", methods=["POST"])
def api_document_ask(doc_id):
    payload = request.get_json() or {}
    question = payload.get("question", "").strip()
    if not question:
        return jsonify({"success": False, "error": "请输入有效的问题"}), 400

    document, _ = get_document_or_404(doc_id)
    file_path = Path(document["filepath"])
    preview_text = extract_preview_text(file_path)
    compare_id = (payload.get("compare_doc_id") or "").strip()
    if compare_id and compare_id != doc_id:
        compare_doc, _ = get_document_or_404(compare_id)
        compare_path = Path(compare_doc["filepath"])
        compare_text = extract_preview_text(compare_path)
        answer = ai_client.ask_about_documents(
            question=question,
            primary_filename=document["original_name"],
            primary_excerpt=preview_text,
            secondary_filename=compare_doc["original_name"],
            secondary_excerpt=compare_text,
        )
    else:
        answer = ai_client.ask_about_document(
            question=question,
            filename=document["original_name"],
            document_excerpt=preview_text,
        )
    return jsonify({"success": True, "answer": answer})


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "没有检测到文件"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "请选择文件"}), 400

    saved_file, original_name = save_uploaded_file(
        file=file,
        upload_dir=app.config["UPLOAD_FOLDER"],
    )

    doc_entry = {
        "id": uuid.uuid4().hex,
        "filename": saved_file.name,
        "original_name": original_name,
        "filepath": str(saved_file),
        "size": saved_file.stat().st_size,
        "uploaded_at": datetime.datetime.utcnow().isoformat(),
        "analysis": None,
        "classification": "",
    }

    documents = load_documents(DATA_FILE)
    documents.append(doc_entry)
    store_documents(DATA_FILE, documents)

    return jsonify(
        {
            "success": True,
            "document": doc_entry,
            "redirect": url_for("reader", doc_id=doc_entry["id"]),
        }
    )


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=5050, debug=debug_mode)
