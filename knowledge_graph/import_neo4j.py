# -*- coding: utf-8 -*-
"""
Neo4j 法律知识图谱导入脚本
============================
用法：
    1. 启动本地 Neo4j（或配置 Aura 云端实例）
    2. 设置环境变量 NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD（见 app/config.py）
    3. python knowledge_graph/import_neo4j.py

图模型（Schema）：
    (:Law {name})                      法律（如 中华人民共和国刑法）
    (:Article {ref, content})          法条 -[:BELONGS_TO]-> (:Law)
    (:Crime {name, definition, sentencing})
        -[:DEFINED_IN]-> (:Article)    罪名定义出处
        -[:HAS_ELEMENT]-> (:Element {aspect, text})   四要件（客体/客观方面/主体/主观方面）
    (:Topic {name})                    法律主题（family_law 等）
    (:FAQ {qid, question, answer, keywords})
        -[:ABOUT_TOPIC]-> (:Topic)

全部使用 MERGE，重复执行幂等。
"""
import sys
from pathlib import Path

from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD  # noqa: E402
from knowledge_graph.kg_data import ARTICLES, CRIMES  # noqa: E402
from knowledge_graph.faq_data import FAQS  # noqa: E402

TOPIC_NAMES = {
    "family_law": "婚姻家庭", "labor_dispute": "劳动争议",
    "contract_dispute": "合同纠纷", "traffic_accident": "交通事故",
    "criminal_procedure": "刑事程序", "civil_compensation": "民事赔偿",
}


def import_all(session):
    # 唯一性约束（面试讲点：图谱建模要先建约束，防止重复节点）
    for stmt in [
        "CREATE CONSTRAINT crime_name IF NOT EXISTS FOR (c:Crime) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT article_ref IF NOT EXISTS FOR (a:Article) REQUIRE a.ref IS UNIQUE",
        "CREATE CONSTRAINT law_name IF NOT EXISTS FOR (l:Law) REQUIRE l.name IS UNIQUE",
        "CREATE CONSTRAINT faq_qid IF NOT EXISTS FOR (f:FAQ) REQUIRE f.qid IS UNIQUE",
        "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
    ]:
        session.run(stmt)

    for art in ARTICLES:
        session.run(
            "MERGE (l:Law {name: $law}) "
            "MERGE (a:Article {ref: $ref}) SET a.content = $content "
            "MERGE (a)-[:BELONGS_TO]->(l)",
            law=art["law"], ref=art["ref"], content=art["content"])

    for crime in CRIMES:
        session.run(
            "MERGE (c:Crime {name: $name}) "
            "SET c.definition = $definition, c.sentencing = $sentencing",
            name=crime["name"], definition=crime["definition"],
            sentencing=crime["sentencing"])
        session.run(
            "MATCH (c:Crime {name: $name}), (a:Article {ref: $ref}) "
            "MERGE (c)-[:DEFINED_IN]->(a)",
            name=crime["name"], ref=crime["article"])
        for aspect, text in crime["elements"].items():
            session.run(
                "MATCH (c:Crime {name: $name}) "
                "MERGE (e:Element {crime: $name, aspect: $aspect}) SET e.text = $text "
                "MERGE (c)-[:HAS_ELEMENT]->(e)",
                name=crime["name"], aspect=aspect, text=text)

    for i, faq in enumerate(FAQS):
        session.run(
            "MERGE (t:Topic {name: $topic}) SET t.display = $display "
            "MERGE (f:FAQ {qid: $qid}) "
            "SET f.question = $question, f.answer = $answer, f.keywords = $keywords "
            "MERGE (f)-[:ABOUT_TOPIC]->(t)",
            topic=faq["topic"], display=TOPIC_NAMES.get(faq["topic"], faq["topic"]),
            qid=f"faq_{i:03d}", question=faq["question"],
            answer=faq["answer"], keywords=faq["keywords"])


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        import_all(session)
        stats = session.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS cnt "
            "ORDER BY cnt DESC").data()
        rels = session.run("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS cnt").data()
    driver.close()
    print("导入完成，节点统计:", stats)
    print("关系统计:", rels)


if __name__ == "__main__":
    main()
