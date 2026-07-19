# -*- coding: utf-8 -*-
"""意图识别模型冒烟测试（需要已训练的模型权重，加载较慢单独标记）"""
import pytest

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def service():
    from app.intent_service import IntentService
    return IntentService()


@pytest.mark.parametrize("text,expect", [
    ("什么是盗窃罪", "crime_definition"),
    ("抢劫罪的构成要件有哪些", "crime_elements"),
    ("诈骗罪一般判几年", "sentencing"),
    ("刑法第266条的内容是什么", "article_query"),
    ("公司拖欠工资怎么办", "labor_dispute"),
    ("我想离婚需要走什么程序", "family_law"),
    ("合同违约怎么要求赔偿", "contract_dispute"),
    ("酒驾怎么处罚", "traffic_accident"),
    ("取保候审需要满足什么条件", "criminal_procedure"),
    ("买到假货可以要求几倍赔偿", "civil_compensation"),
    ("你好", "greeting"),
    ("非常感谢", "thanks_bye"),
])
def test_canonical_intents(service, text, expect):
    intent, conf = service.predict(text)
    assert intent == expect, f"{text}: 预测 {intent}({conf:.2f})，期望 {expect}"
    assert conf > 0.5
