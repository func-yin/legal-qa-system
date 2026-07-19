# -*- coding: utf-8 -*-
"""
端到端验证脚本：模拟真实用户多轮对话
前提：Neo4j 已启动并导入图谱，Flask 服务已启动（python -m app.main）
用法：python tests/verify_e2e.py
"""
import json
import urllib.request

BASE = "http://127.0.0.1:5000"


def post(path, payload, timeout=120):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path, timeout=120):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def show(user, resp):
    print(f"\n👤 用户: {user}")
    print(f"🤖 助手 [{resp.get('intent')}, 置信度 {resp.get('confidence')}]:")
    print(f"   {resp.get('answer', resp.get('error'))}")


def main():
    print("== /api/health ==", get("/api/health"))

    # 1. 多轮：罪名定义 -> 量刑（槽位继承）
    r1 = post("/api/chat", {"message": "什么是盗窃罪"})
    show("什么是盗窃罪", r1)
    sid = r1["session_id"]

    r2 = post("/api/chat", {"message": "那会判几年", "session_id": sid})
    show("那会判几年（应继承「盗窃罪」）", r2)

    r3 = post("/api/chat", {"message": "它的构成要件呢", "session_id": sid})
    show("它的构成要件呢（指代消解）", r3)

    # 2. 法条查询
    show("刑法第266条的内容", post("/api/chat", {"message": "刑法第266条的内容"}))

    # 3. 槽位填充（无上下文问量刑 -> 应反问）
    r5 = post("/api/chat", {"message": "一般判几年"})
    show("一般判几年（新会话，应反问）", r5)
    r6 = post("/api/chat", {"message": "诈骗罪", "session_id": r5["session_id"]})
    show("诈骗罪（补全槽位后应回答）", r6)

    # 4. 主题 FAQ
    show("公司拖欠工资怎么办", post("/api/chat", {"message": "公司拖欠工资怎么办"}))

    # 5. 拒识
    show("今天天气怎么样", post("/api/chat", {"message": "今天天气怎么样"}))

    print("\n== /api/stats ==", get("/api/stats"))
    print("\n✅ 端到端验证完成")


if __name__ == "__main__":
    main()
