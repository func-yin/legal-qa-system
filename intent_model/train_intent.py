# -*- coding: utf-8 -*-
"""
Bert 法律意图分类模型微调脚本（支持断点续训）
==============================================
- 基座：bert-base-chinese（12层 Transformer）
- 任务：12 类法律咨询意图多分类
- 每次运行训练 EPOCHS_PER_RUN 个 epoch 并保存断点，重复运行同一命令即可续训，
  直到达到 EPOCHS_TOTAL 后自动用 dev 最优权重评估 test 并导出最终模型。

面试讲点：
- 类别不均衡：训练集中「问候/感谢」等类样本远少于「罪名/量刑」类，
  损失函数使用类别权重（weight = N / (K * n_c)）抑制多数类坍缩。
- 冻结底层参数：小数据场景下减少过拟合、降低 CPU 训练成本。
- 评估纪律：train/dev/test 严格分离，test 只在训练全部结束后碰一次。
"""
import json
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from torch.utils.data import DataLoader, Dataset
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          get_linear_schedule_with_warmup)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
OUT = ROOT / "intent_model" / "output"
CKPT = ROOT / "intent_model" / "ckpt" / "ckpt.pt"
OUT.mkdir(parents=True, exist_ok=True)
CKPT.parent.mkdir(parents=True, exist_ok=True)

MODEL_NAME = "bert-base-chinese"
MAX_LEN = 40        # 法律问句普遍 <30 字
BATCH = 32
EPOCHS_TOTAL = 8    # 总训练轮数
EPOCHS_PER_RUN = 2  # 每次运行训练轮数（防止单次运行过久，支持断点续训）
LR = 3e-5
SEED = 42
FREEZE_LAYERS = 8   # 冻结 embedding + 前 8 层 encoder


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


class IntentDataset(Dataset):
    def __init__(self, csv_path, tokenizer, label2id):
        df = pd.read_csv(csv_path)
        self.texts = df["text"].tolist()
        self.labels = [label2id[x] for x in df["label"]]
        self.tok = tokenizer

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, i):
        enc = self.tok(self.texts[i], max_length=MAX_LEN,
                       padding="max_length", truncation=True, return_tensors="pt")
        item = {k: v.squeeze(0) for k, v in enc.items()}
        item["labels"] = torch.tensor(self.labels[i], dtype=torch.long)
        return item


@torch.no_grad()
def evaluate(model, loader):
    model.eval()
    preds, golds = [], []
    for batch in loader:
        labels = batch.pop("labels")
        logits = model(**batch).logits
        preds += logits.argmax(-1).tolist()
        golds += labels.tolist()
    return accuracy_score(golds, preds), f1_score(golds, preds, average="macro"), golds, preds


def build_model(labels, num_labels):
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=num_labels,
        id2label={i: l for i, l in enumerate(labels)},
        label2id={l: i for i, l in enumerate(labels)})
    for p in model.bert.embeddings.parameters():
        p.requires_grad = False
    for layer in model.bert.encoder.layer[:FREEZE_LAYERS]:
        for p in layer.parameters():
            p.requires_grad = False
    return tok, model


def main():
    set_seed(SEED)
    labels = (DATA / "labels.txt").read_text(encoding="utf-8").split()
    label2id = {l: i for i, l in enumerate(labels)}
    n = len(labels)
    print(f"意图类别数: {n}")

    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=n,
        id2label={i: l for i, l in enumerate(labels)},
        label2id={l: i for i, l in enumerate(labels)})
    for p in model.bert.embeddings.parameters():
        p.requires_grad = False
    for layer in model.bert.encoder.layer[:FREEZE_LAYERS]:
        for p in layer.parameters():
            p.requires_grad = False
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"可训练参数: {trainable/1e6:.1f}M / {sum(p.numel() for p in model.parameters())/1e6:.1f}M")

    train_ds = IntentDataset(DATA / "intent_train.csv", tok, label2id)
    dev_ds = IntentDataset(DATA / "intent_dev.csv", tok, label2id)
    test_ds = IntentDataset(DATA / "intent_test.csv", tok, label2id)
    print(f"train={len(train_ds)} dev={len(dev_ds)} test={len(test_ds)}")

    train_loader = DataLoader(train_ds, batch_size=BATCH, shuffle=True)
    dev_loader = DataLoader(dev_ds, batch_size=32)

    # 类别权重：抑制多数类坍缩
    counts = np.bincount(train_ds.labels, minlength=n).astype(np.float32)
    class_weight = torch.tensor(counts.sum() / (n * np.maximum(counts, 1)),
                                dtype=torch.float32)
    print("类别权重:", {labels[i]: round(float(class_weight[i]), 2) for i in range(n)})

    optimizer = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()),
                                  lr=LR, weight_decay=0.01)
    total_steps = len(train_loader) * EPOCHS_TOTAL
    scheduler = get_linear_schedule_with_warmup(
        optimizer, int(0.1 * total_steps), total_steps)

    start_epoch, best_dev_acc, best_state, history = 1, 0.0, None, []
    if CKPT.exists():
        ck = torch.load(CKPT, weights_only=False)
        model.load_state_dict(ck["model"])
        optimizer.load_state_dict(ck["optimizer"])
        scheduler.load_state_dict(ck["scheduler"])
        start_epoch = ck["epoch"] + 1
        best_dev_acc, best_state, history = ck["best_dev_acc"], ck["best_state"], ck["history"]
        print(f"从断点恢复：已完成 {ck['epoch']} 轮，best_dev_acc={best_dev_acc:.4f}")

    end_epoch = min(start_epoch + EPOCHS_PER_RUN - 1, EPOCHS_TOTAL)
    loss_fn = torch.nn.CrossEntropyLoss(weight=class_weight)
    for epoch in range(start_epoch, end_epoch + 1):
        model.train()
        t0, total_loss = time.time(), 0.0
        for step, batch in enumerate(train_loader, 1):
            labels_b = batch.pop("labels")
            logits = model(**batch).logits
            loss = loss_fn(logits, labels_b)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(filter(lambda p: p.requires_grad,
                                                  model.parameters()), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            total_loss += loss.item()
        dev_acc, dev_f1, _, _ = evaluate(model, dev_loader)
        history.append({"epoch": epoch, "train_loss": round(total_loss / len(train_loader), 4),
                        "dev_acc": round(dev_acc, 4), "dev_f1": round(dev_f1, 4)})
        print(f"[epoch {epoch}/{EPOCHS_TOTAL}] loss={total_loss/len(train_loader):.4f} "
              f"dev_acc={dev_acc:.4f} dev_f1={dev_f1:.4f} ({time.time()-t0:.0f}s)")
        if dev_acc > best_dev_acc:
            best_dev_acc = dev_acc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        torch.save({"epoch": epoch, "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
                    "best_dev_acc": best_dev_acc, "best_state": best_state,
                    "history": history}, CKPT)

    if end_epoch < EPOCHS_TOTAL:
        print(f"\n>>> 已完成 {end_epoch}/{EPOCHS_TOTAL} 轮，再次运行本脚本继续训练 <<<")
        return

    # ===== 全部训练完成：加载 dev 最优权重，评估 test =====
    model.load_state_dict(best_state)
    test_loader = DataLoader(test_ds, batch_size=32)
    test_acc, test_f1, golds, preds = evaluate(model, test_loader)
    print(f"\n===== TEST  acc={test_acc:.4f}  macro-F1={test_f1:.4f} =====")

    id2label = {i: l for i, l in enumerate(labels)}
    report = classification_report(
        golds, preds, labels=list(range(n)),
        target_names=[id2label[i] for i in range(n)], digits=4, zero_division=0)
    cm = confusion_matrix(golds, preds, labels=list(range(n))).tolist()
    print(report)

    model.save_pretrained(OUT)
    tok.save_pretrained(OUT)
    (OUT / "metrics.json").write_text(json.dumps({
        "model": MODEL_NAME, "epochs": EPOCHS_TOTAL, "batch_size": BATCH, "lr": LR,
        "max_len": MAX_LEN, "seed": SEED, "freeze_layers": FREEZE_LAYERS,
        "class_weighted_loss": True,
        "best_dev_acc": round(best_dev_acc, 4),
        "test_acc": round(test_acc, 4), "test_macro_f1": round(test_f1, 4),
        "history": history, "confusion_matrix": cm,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = ROOT / "docs" / "intent_report.md"
    report_path.write_text(
        f"# 意图识别模型评估报告\n\n"
        f"- 基座模型：`{MODEL_NAME}`（冻结 embedding + 前 {FREEZE_LAYERS} 层）\n"
        f"- 训练轮数：{EPOCHS_TOTAL}，batch={BATCH}，lr={LR}，类别加权损失\n"
        f"- 数据规模：train={len(train_ds)} / dev={len(dev_ds)} / test={len(test_ds)}\n"
        f"- **dev 最优准确率：{best_dev_acc:.4f}**\n"
        f"- **test 准确率：{test_acc:.4f}，宏平均 F1：{test_f1:.4f}**\n\n"
        f"## 训练过程\n\n```json\n{json.dumps(history, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## 分类报告（test）\n\n```\n{report}\n```\n",
        encoding="utf-8")
    print(f"最终模型已保存到 {OUT}\n评估报告: {report_path}")


if __name__ == "__main__":
    main()
