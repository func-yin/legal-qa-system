# -*- coding: utf-8 -*-
"""多轮对话管理器单元测试（fake 依赖，无需 Neo4j / 模型权重）"""
import pytest

from app.dialogue_manager import DialogueManager

CRIME_INFO = {
    "盗窃罪": {"name": "盗窃罪", "definition": "以非法占有为目的，秘密窃取公私财物……",
               "sentencing": "数额较大处3年以下有期徒刑……",
               "elements": {"客体": "公私财物所有权", "客观方面": "秘密窃取",
                            "主体": "一般主体", "主观方面": "直接故意"},
               "articles": ["刑法第264条"]},
    "诈骗罪": {"name": "诈骗罪", "definition": "以非法占有为目的，用虚构事实……",
               "sentencing": "数额较大处3年以下……",
               "elements": {"客体": "公私财物所有权", "客观方面": "虚构事实骗取财物",
                            "主体": "一般主体", "主观方面": "直接故意"},
               "articles": ["刑法第266条"]},
}


class FakeIntentService:
    """用规则模拟意图识别，专注测对话逻辑"""
    RULES = [("什么是", "crime_definition"), ("是什么意思", "crime_definition"),
             ("构成要件", "crime_elements"), ("要件", "crime_elements"),
             ("判几年", "sentencing"), ("怎么判", "sentencing"), ("量刑", "sentencing"),
             ("第", "article_query"), ("你好", "greeting"), ("谢谢", "thanks_bye")]

    def predict(self, text):
        for kw, intent in self.RULES:
            if kw in text:
                return intent, 0.95
        return "greeting", 0.3  # 低置信度 -> 拒识


class FakeRepo:
    def get_crime(self, name):
        return CRIME_INFO.get(name)

    @staticmethod
    def normalize_article_ref(text):
        from app.kg_repository import KGRepository
        return KGRepository.normalize_article_ref(text)

    def get_article(self, ref):
        return {"ref": ref, "law": "中华人民共和国刑法", "content": "条文内容……"}

    def search_faq(self, topic, text):
        return []


@pytest.fixture()
def dm():
    return DialogueManager(intent_service=FakeIntentService(), repo=FakeRepo())


def test_single_turn_definition(dm):
    r = dm.reply("什么是盗窃罪")
    assert "盗窃罪" in r["answer"] and "非法占有" in r["answer"]
    assert r["intent"] == "crime_definition"


def test_multi_turn_slot_inheritance(dm):
    """多轮槽位继承：第二轮没有罪名实体，应继承上一轮的盗窃罪"""
    sid = dm.reply("什么是盗窃罪")["session_id"]
    r2 = dm.reply("会判几年", sid)
    assert r2["intent"] == "sentencing"
    assert "盗窃罪" in r2["answer"] and "3年以下" in r2["answer"]


def test_pronoun_resolution(dm):
    """指代消解：「它」映射到上下文罪名"""
    sid = dm.reply("什么是诈骗罪")["session_id"]
    r = dm.reply("它的构成要件有哪些", sid)
    assert "诈骗罪" in r["answer"] and "客体" in r["answer"]


def test_slot_filling_flow(dm):
    """槽位填充：无意图实体 -> 反问 -> 用户补实体 -> 正常回答"""
    r1 = dm.reply("一般会判几年")
    assert "哪个罪名" in r1["answer"]
    r2 = dm.reply("诈骗罪", r1["session_id"])
    assert "诈骗罪" in r2["answer"] and "3年以下" in r2["answer"]


def test_session_isolation(dm):
    """不同 session 互不串扰"""
    dm.reply("什么是盗窃罪", "user-a")
    r = dm.reply("会判几年", "user-b")  # b 没有上下文 -> 应反问
    assert "哪个罪名" in r["answer"]


def test_fallback_on_low_confidence(dm):
    r = dm.reply("今天天气怎么样")
    assert "理解不了" in r["answer"]


@pytest.mark.parametrize("raw,expect", [
    ("刑法264条的内容", "刑法第264条"),
    ("刑法第264条", "刑法第264条"),
    ("民法典1084条是什么", "民法典第1084条"),
    ("刑法第133条之一怎么规定", "刑法第133条之一"),
    ("刑事诉讼法67条", "刑事诉讼法第67条"),
])
def test_article_ref_normalization(raw, expect):
    from app.kg_repository import KGRepository
    assert KGRepository.normalize_article_ref(raw) == expect
