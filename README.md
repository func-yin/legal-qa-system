# 法律智能问答系统（Legal QA System）

基于 **NLP + 知识图谱** 的法律领域智能问答系统：Bert 微调实现用户意图识别，
Neo4j 构建法律知识图谱完成精准检索，自研多轮对话管理器实现上下文连贯交互。

> ⚖️ 本项目为学习演示项目，回答内容基于公开法律法规整理，**不构成法律意见**。

## 功能特性

- **意图识别**：bert-base-chinese 微调，12 类法律咨询意图，测试集准确率 **96.1%**、宏平均 F1 87.6%
- **知识图谱**：Neo4j 存储 20 个常见罪名（定义 / 四要件 / 量刑）、30 部常用法条、30 条高频法律 FAQ
- **多轮对话**：槽位继承 + 指代消解 + 槽位填充反问，支持上下文连贯问答
- **置信度拒识**：模型置信度低于阈值时不强行回答，提示能力边界
- **完整工程化**：Flask REST API、Web 聊天界面、pytest 测试、训练/评估报告全留痕

## 系统架构

```
浏览器 (frontend/index.html)
    │  POST /api/chat
    ▼
Flask 后端 (app/main.py)
    ├── IntentService     Bert 意图分类 (intent_model/)
    ├── DialogueManager   多轮对话管理：槽位继承 / 指代消解 / 反问补全 (app/dialogue_manager.py)
    └── KGRepository      Cypher 检索 (app/kg_repository.py)
                              │
                              ▼
                    Neo4j 法律知识图谱
        (:Crime)-[:DEFINED_IN]->(:Article)-[:BELONGS_TO]->(:Law)
        (:Crime)-[:HAS_ELEMENT]->(:Element)
        (:FAQ)-[:ABOUT_TOPIC]->(:Topic)
```

## 意图列表（12 类）

| 意图 | 说明 | 示例 |
|---|---|---|
| crime_definition | 罪名定义 | 什么是盗窃罪 |
| crime_elements | 构成要件 | 诈骗罪的构成要件有哪些 |
| sentencing | 量刑咨询 | 故意伤害罪判几年 |
| article_query | 法条查询 | 刑法第264条的内容 |
| family_law | 婚姻家庭 | 离婚财产怎么分割 |
| labor_dispute | 劳动争议 | 公司拖欠工资怎么办 |
| contract_dispute | 合同纠纷 | 定金和订金有什么区别 |
| traffic_accident | 交通事故 | 肇事逃逸有什么后果 |
| criminal_procedure | 刑事程序 | 取保候审需要什么条件 |
| civil_compensation | 民事赔偿 | 买到假货可以几倍赔偿 |
| greeting | 问候 | 你好 |
| thanks_bye | 感谢/结束 | 谢谢 |

## 快速开始

### 1. 环境准备

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 启动 Neo4j（二选一）

- **本地部署**：下载 [Neo4j Community](https://neo4j.com/download-center/)（需 JDK 17+），启动后默认地址 `bolt://localhost:7687`
- **云端免费实例**：注册 [Neo4j AuraDB](https://console.neo4j.io/) Free 实例

配置连接（默认 neo4j / legal-qa-2025）：

```bash
# Windows PowerShell
$env:NEO4J_URI="bolt://localhost:7687"; $env:NEO4J_USER="neo4j"; $env:NEO4J_PASSWORD="你的密码"
# macOS/Linux
export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=你的密码
```

### 3. 导入知识图谱

```bash
python knowledge_graph/import_neo4j.py
```

### 4. 训练意图模型（或直接跳过用规则跑通）

```bash
python data/build_intent_dataset.py     # 生成意图数据集
python intent_model/train_intent.py     # 重复运行 4 次（断点续训，共 8 个 epoch）
```

> 国内网络建议先设置镜像：`set HF_ENDPOINT=https://hf-mirror.com`（Windows）/ `export HF_ENDPOINT=https://hf-mirror.com`

### 5. 启动服务

```bash
python -m app.main
# 打开 http://127.0.0.1:5000 开始对话
```

### 6. 运行测试

```bash
pytest tests/ -v
```

## 项目结构

```
legal-qa-system/
├── app/                    # Flask 后端
│   ├── main.py             # API 入口（/api/chat /api/health /api/stats）
│   ├── dialogue_manager.py # 多轮对话管理器（槽位继承/指代消解/反问补全）
│   ├── intent_service.py   # Bert 意图识别服务
│   ├── kg_repository.py    # Neo4j Cypher 检索封装
│   └── config.py           # 环境变量配置
├── data/
│   ├── build_intent_dataset.py  # 意图数据集构造（模板×槽位，防泄漏分层切分）
│   └── processed/               # train/dev/test CSV
├── intent_model/
│   ├── train_intent.py     # Bert 微调训练（类别加权损失、断点续训）
│   └── output/             # 训练产物（gitignore，需自行训练生成）
├── knowledge_graph/
│   ├── kg_data.py          # 20 罪名 + 30 法条
│   ├── faq_data.py         # 30 条高频法律 FAQ
│   └── import_neo4j.py     # 图谱导入脚本（幂等 MERGE）
├── frontend/index.html     # Web 聊天界面
├── tests/                  # pytest（单元 + 模型冒烟测试）
└── docs/                   # 路线图、模型评估报告
```

## 对话示例（多轮）

```
用户：什么是盗窃罪
机器人：【盗窃罪】以非法占有为目的，秘密窃取公私财物数额较大……（法律依据：刑法第264条）

用户：那会判几年          ← 无实体，自动继承上下文「盗窃罪」
机器人：【盗窃罪的量刑标准】数额较大（1千至3千元以上）处3年以下有期徒刑……
```

## 模型评估

训练与评估详情见 [docs/intent_report.md](docs/intent_report.md)（分类报告、训练曲线）。
关键指标：**test 准确率 96.1%，宏平均 F1 87.6%**（102 条测试样本，模板级防泄漏切分）。

## 技术栈

Python 3.12 · Flask 3 · PyTorch 2 (CPU) · Transformers 5 · Neo4j 5 · pytest

## License

[MIT](LICENSE)
