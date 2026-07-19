# -*- coding: utf-8 -*-
"""
知识图谱检索层（Cypher 查询封装）
==================================
把「问答语义」翻译成 Cypher，上层不需要懂图查询语言。
"""
import re

from neo4j import GraphDatabase

from .config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# 法条引用归一化：兼容「刑法264条」「刑法第264条」「民法典1079」等写法
_ARTICLE_RE = re.compile(
    r"(刑法|民法典|劳动合同法|道路交通安全法|消费者权益保护法|刑事诉讼法)"
    r"第?\s*(\d+)\s*条(之[一二三四五六七八九十])?")


class KGRepository:
    def __init__(self, uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    # ---------------- 罪名 ----------------
    def get_crime(self, name: str):
        """返回罪名节点 + 四要件 + 关联法条"""
        with self.driver.session() as s:
            rec = s.run(
                "MATCH (c:Crime {name: $name}) "
                "OPTIONAL MATCH (c)-[:HAS_ELEMENT]->(e:Element) "
                "OPTIONAL MATCH (c)-[:DEFINED_IN]->(a:Article) "
                "RETURN c.name AS name, c.definition AS definition, "
                "       c.sentencing AS sentencing, "
                "       collect(DISTINCT {aspect: e.aspect, text: e.text}) AS elements, "
                "       collect(DISTINCT a.ref) AS articles",
                name=name).single()
            if not rec:
                return None
            elements = {e["aspect"]: e["text"] for e in rec["elements"] if e["aspect"]}
            return {"name": rec["name"], "definition": rec["definition"],
                    "sentencing": rec["sentencing"], "elements": elements,
                    "articles": rec["articles"]}

    def list_crimes(self):
        with self.driver.session() as s:
            return [r["name"] for r in s.run("MATCH (c:Crime) RETURN c.name AS name")]

    # ---------------- 法条 ----------------
    def get_article(self, ref: str):
        with self.driver.session() as s:
            rec = s.run(
                "MATCH (a:Article {ref: $ref})-[:BELONGS_TO]->(l:Law) "
                "RETURN a.ref AS ref, a.content AS content, l.name AS law",
                ref=ref).single()
            return dict(rec) if rec else None

    @staticmethod
    def normalize_article_ref(text: str):
        """从用户输入中解析法条引用并归一化为图谱中的 ref 形式"""
        m = _ARTICLE_RE.search(text)
        if not m:
            return None
        law, num, suffix = m.group(1), m.group(2), m.group(3) or ""
        return f"{law}第{num}条{suffix}"

    # ---------------- FAQ ----------------
    def search_faq(self, topic: str, text: str, limit: int = 1):
        """按主题 + 关键词命中数检索 FAQ（简单的关键词重叠打分）"""
        with self.driver.session() as s:
            rows = s.run(
                "MATCH (f:FAQ)-[:ABOUT_TOPIC]->(t:Topic {name: $topic}) "
                "RETURN f.question AS question, f.answer AS answer, "
                "       f.keywords AS keywords", topic=topic).data()
        scored = []
        for r in rows:
            score = sum(1 for kw in r["keywords"] if kw in text)
            scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:limit]] if scored and scored[0][0] > 0 else []

    # ---------------- 统计 ----------------
    def stats(self):
        with self.driver.session() as s:
            return s.run(
                "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS cnt "
                "ORDER BY cnt DESC").data()


_repo = None


def get_repo() -> KGRepository:
    global _repo
    if _repo is None:
        _repo = KGRepository()
    return _repo
