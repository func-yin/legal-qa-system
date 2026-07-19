# -*- coding: utf-8 -*-
"""
意图识别服务：加载微调后的 Bert 模型，对外提供 predict(text) -> (intent, confidence)

面试讲点：
- 推理时用 torch.no_grad() + eval 模式，关闭 dropout；
- softmax 取最大概率作为置信度，低于阈值由上层做拒识；
- 模型在模块加载时只初始化一次（单例），避免每次请求重复加载几百 MB 权重。
"""
import os

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from .config import INTENT_MODEL_PATH

MAX_LEN = 40


class IntentService:
    def __init__(self, model_path: str = INTENT_MODEL_PATH):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
        self.model.eval()
        self.id2label = self.model.config.id2label

    @torch.no_grad()
    def predict(self, text: str):
        enc = self.tokenizer(text, max_length=MAX_LEN, padding="max_length",
                             truncation=True, return_tensors="pt")
        logits = self.model(**enc).logits[0]
        probs = torch.softmax(logits, dim=-1)
        conf, idx = probs.max(dim=0)
        return self.id2label[int(idx)], float(conf)

    @torch.no_grad()
    def predict_topk(self, text: str, k: int = 3):
        """返回 top-k 意图及概率，调试/评估用"""
        enc = self.tokenizer(text, max_length=MAX_LEN, padding="max_length",
                             truncation=True, return_tensors="pt")
        probs = torch.softmax(self.model(**enc).logits[0], dim=-1)
        top = probs.topk(k)
        return [(self.id2label[int(i)], round(float(p), 4))
                for p, i in zip(top.values, top.indices)]


_service = None


def get_intent_service() -> IntentService:
    global _service
    if _service is None:
        _service = IntentService()
    return _service
