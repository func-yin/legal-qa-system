# -*- coding: utf-8 -*-
"""
Flask 后端入口
================
接口：
    GET  /api/health     健康检查（Neo4j 连通性 + 模型状态）
    POST /api/chat       对话接口  {message, session_id?} -> {answer, intent, confidence, session_id}
    GET  /api/stats      图谱统计（演示用）
    GET  /               前端聊天页面

启动：python -m app.main
"""
import traceback

from flask import Flask, jsonify, request, send_from_directory

from .config import FLASK_HOST, FLASK_PORT, ROOT
from .dialogue_manager import DialogueManager
from .kg_repository import get_repo

app = Flask(__name__, static_folder=None)
_manager = None


def get_manager():
    global _manager
    if _manager is None:
        _manager = DialogueManager()
    return _manager


@app.route("/api/health")
def health():
    status = {"model": "ok", "neo4j": "ok"}
    code = 200
    try:
        get_repo().stats()
    except Exception as e:
        status["neo4j"] = f"error: {e}"
        code = 503
    try:
        get_manager()
    except Exception as e:
        status["model"] = f"error: {e}"
        code = 503
    return jsonify(status), code


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message 不能为空"}), 400
    try:
        result = get_manager().reply(message, data.get("session_id"))
        return jsonify(result)
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "服务内部错误，请稍后重试"}), 500


@app.route("/api/stats")
def stats():
    try:
        return jsonify({"graph": get_repo().stats()})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@app.route("/")
def index():
    return send_from_directory(ROOT / "frontend", "index.html")


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
