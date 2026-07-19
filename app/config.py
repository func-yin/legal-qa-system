# -*- coding: utf-8 -*-
"""
全局配置：全部通过环境变量覆盖，本地开发有合理默认值。
敏感配置（Neo4j 密码）绝不写死在代码里 —— 开源项目的基本素养。
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---- Neo4j ----
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "legal-qa-2025")

# ---- 意图模型 ----
INTENT_MODEL_PATH = os.getenv("INTENT_MODEL_PATH",
                              str(ROOT / "intent_model" / "output"))
# 置信度低于该阈值时触发拒识（fallback），避免胡乱回答（面试讲点）
INTENT_CONFIDENCE_THRESHOLD = float(os.getenv("INTENT_CONFIDENCE_THRESHOLD", "0.5"))

# ---- Flask ----
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "1800"))  # 会话 30 分钟过期
