# -*- coding: utf-8 -*-
"""
多轮对话管理器
================
核心机制（面试讲点）：
1. 会话状态：session_id -> {slots, history, updated_at}，内存存储 + TTL 过期清理；
2. 槽位继承：当前轮没有识别出实体（罪名）时，继承上一轮会话槽位，
   实现「什么是盗窃罪」→「会判几年」的上下文连贯问答；
3. 槽位填充：识别出意图但缺少必要实体时，反问用户补齐（pending_intent），
   下一轮用户只回答实体即可完成查询；
4. 指代消解（基础版）：「它/这个罪」等指代词直接映射到上下文槽位中的罪名。
"""
import time
import uuid

from .config import INTENT_CONFIDENCE_THRESHOLD, SESSION_TTL_SECONDS
from .intent_service import get_intent_service
from .kg_repository import get_repo

CRIMES = ["盗窃罪", "诈骗罪", "故意伤害罪", "抢劫罪", "交通肇事罪", "危险驾驶罪",
          "寻衅滋事罪", "贪污罪", "受贿罪", "故意杀人罪", "强奸罪", "非法拘禁罪",
          "敲诈勒索罪", "职务侵占罪", "非法吸收公众存款罪", "非法集资罪",
          "帮助信息网络犯罪活动罪", "掩饰、隐瞒犯罪所得罪", "掩饰隐瞒犯罪所得罪",
          "开设赌场罪", "贩卖毒品罪", "逃税罪", "偷税漏税罪"]
# 别名 -> 图谱标准名
CRIME_ALIAS = {"非法集资罪": "非法吸收公众存款罪", "偷税漏税罪": "逃税罪",
               "掩饰隐瞒犯罪所得罪": "掩饰、隐瞒犯罪所得罪"}
CRIME_INTENTS = {"crime_definition", "crime_elements", "sentencing"}
TOPIC_INTENTS = {"family_law", "labor_dispute", "contract_dispute",
                 "traffic_accident", "criminal_procedure", "civil_compensation"}
PRONOUNS = ["它", "这个罪", "该罪", "这种情况", "这个"]

FALLBACK = ("抱歉，我暂时理解不了您的问题。我目前可以："
            "① 解答 20 个常见罪名的定义、构成要件、量刑标准；"
            "② 查询 30 部常用法律条文；"
            "③ 解答婚姻家庭、劳动争议、合同纠纷、交通事故、刑事程序、民事赔偿的常见问题。"
            "您可以换个说法试试～")


def extract_crime(text: str):
    """实体识别：罪名词典匹配（按长度优先，避免「非法拘禁」先于「非法拘禁罪」截断）"""
    for name in sorted(CRIMES, key=len, reverse=True):
        if name in text:
            return CRIME_ALIAS.get(name, name)
    return None


class Session:
    def __init__(self):
        self.slots = {}          # 槽位：当前罪名等
        self.pending_intent = None  # 等待补齐实体的意图
        self.history = []
        self.updated_at = time.time()


class DialogueManager:
    def __init__(self, intent_service=None, repo=None):
        # 依赖注入：测试时可传入 fake，生产默认走全局单例
        self.sessions = {}
        self.intent_service = intent_service or get_intent_service()
        self.repo = repo or get_repo()

    # ---------------- 会话维护 ----------------
    def _get_session(self, session_id):
        self._cleanup()
        if session_id not in self.sessions:
            self.sessions[session_id] = Session()
        s = self.sessions[session_id]
        s.updated_at = time.time()
        return s

    def _cleanup(self):
        now = time.time()
        expired = [k for k, v in self.sessions.items()
                   if now - v.updated_at > SESSION_TTL_SECONDS]
        for k in expired:
            del self.sessions[k]

    # ---------------- 主入口 ----------------
    def reply(self, text: str, session_id: str = None):
        session_id = session_id or uuid.uuid4().hex
        sess = self._get_session(session_id)
        intent, conf = self.intent_service.predict(text)

        # 上一轮在等实体补齐：优先消费 pending 状态
        if sess.pending_intent:
            answer = self._fulfill_pending(sess, text)
        elif conf >= INTENT_CONFIDENCE_THRESHOLD:
            answer = self._dispatch(sess, intent, text)
        elif sess.slots.get("crime"):
            # 上下文兜底：上下文已有罪名槽位时，短输入（如「那会判几年」）
            # 模型置信度常偏低；先按模型意图，再按关键词推断续聊意图，
            # 结合上下文回答而不是机械拒识 —— 拒识与多轮体验的平衡（面试讲点）
            rescued = self._rescue_intent(intent, text)
            answer = self._dispatch(sess, rescued, text) if rescued else FALLBACK
        else:
            answer = FALLBACK

        sess.history.append({"user": text, "bot": answer, "intent": intent,
                             "confidence": round(conf, 4)})
        return {"session_id": session_id, "intent": intent,
                "confidence": round(conf, 4), "answer": answer}

    @staticmethod
    def _rescue_intent(intent, text):
        """低置信度续聊的意图纠偏：模型意图有效直接用，否则按关键词推断"""
        if intent in CRIME_INTENTS:
            return intent
        if any(k in text for k in ["要件", "构成", "认定", "立案标准"]):
            return "crime_elements"
        if any(k in text for k in ["判", "量刑", "坐牢", "刑期", "缓刑"]):
            return "sentencing"
        if any(k in text for k in ["是什么", "定义", "什么意思", "概念"]):
            return "crime_definition"
        return None

    # ---------------- 意图分发 ----------------
    def _dispatch(self, sess, intent, text):
        if intent == "greeting":
            return ("您好，我是法律智能问答助手 ⚖️ 可以问我：\n"
                    "· 罪名问题：什么是盗窃罪 / 诈骗罪判几年\n"
                    "· 法条查询：刑法第264条的内容\n"
                    "· 婚姻家事、劳动纠纷、合同、交通事故等常见问题")
        if intent == "thanks_bye":
            return "不客气，祝您生活愉快！有其他法律问题随时问我。"
        if intent in CRIME_INTENTS:
            return self._answer_crime(sess, intent, text)
        if intent == "article_query":
            return self._answer_article(text)
        if intent in TOPIC_INTENTS:
            return self._answer_faq(intent, text)
        return FALLBACK

    # ---------------- 罪名类问答 ----------------
    def _answer_crime(self, sess, intent, text):
        crime = extract_crime(text)
        if crime is None and any(p in text for p in PRONOUNS):
            crime = sess.slots.get("crime")          # 指代消解
        if crime is None:
            crime = sess.slots.get("crime")           # 槽位继承
        if crime is None:
            sess.pending_intent = intent               # 进入槽位填充
            return "您想咨询哪个罪名呢？比如：盗窃罪、诈骗罪、故意伤害罪……"
        sess.slots["crime"] = crime

        info = self.repo.get_crime(crime)
        if not info:
            return f"抱歉，我的知识库里暂时没有「{crime}」的条目。"
        if intent == "crime_definition":
            arts = "、".join(info["articles"])
            return f"【{info['name']}】{info['definition']}\n（法律依据：{arts}）"
        if intent == "crime_elements":
            lines = [f"【{info['name']}的构成要件】"]
            for aspect in ["客体", "客观方面", "主体", "主观方面"]:
                if aspect in info["elements"]:
                    lines.append(f"· {aspect}：{info['elements'][aspect]}")
            return "\n".join(lines)
        if intent == "sentencing":
            return f"【{info['name']}的量刑标准】{info['sentencing']}"
        return FALLBACK

    def _fulfill_pending(self, sess, text):
        intent = sess.pending_intent
        sess.pending_intent = None
        crime = extract_crime(text)
        if crime is None:
            return "抱歉，我没认出这个罪名，可以试试「什么是盗窃罪」这样的问法。"
        sess.slots["crime"] = crime
        return self._answer_crime(sess, intent, crime)

    # ---------------- 法条查询 ----------------
    def _answer_article(self, text):
        ref = self.repo.normalize_article_ref(text)
        if not ref:
            return ("请告诉我具体法条，例如「刑法第264条」"
                    "（支持刑法、民法典、劳动合同法、道路交通安全法、消费者权益保护法、刑事诉讼法）。")
        rec = self.repo.get_article(ref)
        if not rec:
            return f"抱歉，知识库中暂未收录《{ref}》，目前收录了 30 部常用法条。"
        return f"【{rec['law']} {rec['ref'].replace(rec['law'], '')}】\n{rec['content']}"

    # ---------------- 主题 FAQ ----------------
    def _answer_faq(self, intent, text):
        hits = self.repo.search_faq(intent, text)
        if not hits:
            return ("这个问题我需要更多信息才能准确回答。您可以描述得更具体一些，"
                    "比如「公司拖欠工资怎么办」「离婚财产怎么分割」。")
        return hits[0]["answer"]
