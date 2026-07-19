# 意图识别模型评估报告

- 基座模型：`bert-base-chinese`（冻结 embedding + 前 8 层）
- 训练轮数：8，batch=32，lr=3e-05，类别加权损失
- 数据规模：train=761 / dev=99 / test=102
- **dev 最优准确率：0.9899**
- **test 准确率：0.9608，宏平均 F1：0.8759**

## 训练过程

```json
[
  {
    "epoch": 1,
    "train_loss": 2.4738,
    "dev_acc": 0.596,
    "dev_f1": 0.3418
  },
  {
    "epoch": 2,
    "train_loss": 1.8409,
    "dev_acc": 0.7778,
    "dev_f1": 0.463
  },
  {
    "epoch": 3,
    "train_loss": 1.2282,
    "dev_acc": 0.9192,
    "dev_f1": 0.8234
  },
  {
    "epoch": 4,
    "train_loss": 0.7723,
    "dev_acc": 0.9293,
    "dev_f1": 0.7866
  },
  {
    "epoch": 5,
    "train_loss": 0.5095,
    "dev_acc": 0.9697,
    "dev_f1": 0.896
  },
  {
    "epoch": 6,
    "train_loss": 0.3484,
    "dev_acc": 0.9697,
    "dev_f1": 0.8831
  },
  {
    "epoch": 7,
    "train_loss": 0.2684,
    "dev_acc": 0.9899,
    "dev_f1": 0.9702
  },
  {
    "epoch": 8,
    "train_loss": 0.2173,
    "dev_acc": 0.9899,
    "dev_f1": 0.9702
  }
]
```

## 分类报告（test）

```
                    precision    recall  f1-score   support

     article_query     1.0000    1.0000    1.0000        22
civil_compensation     0.6667    1.0000    0.8000         2
  contract_dispute     0.6667    1.0000    0.8000         2
  crime_definition     1.0000    0.9091    0.9524        22
    crime_elements     0.9200    1.0000    0.9583        23
criminal_procedure     1.0000    1.0000    1.0000         2
        family_law     1.0000    1.0000    1.0000         2
          greeting     1.0000    1.0000    1.0000         2
     labor_dispute     1.0000    1.0000    1.0000         2
        sentencing     1.0000    1.0000    1.0000        19
        thanks_bye     1.0000    1.0000    1.0000         2
  traffic_accident     0.0000    0.0000    0.0000         2

          accuracy                         0.9608       102
         macro avg     0.8544    0.9091    0.8759       102
      weighted avg     0.9493    0.9608    0.9529       102

```
