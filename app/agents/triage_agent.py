from collections import Counter
from typing import Callable, Dict, Optional

import httpx

from app.agents.base import BaseAgent
from app.core.config import settings
from app.schemas.models import TriageResult
from app.services.ollama_service import OllamaService


class RuleBasedTriageAgent(BaseAgent):
    name = "RuleBasedTriageAgent"
    NEGATION_PREFIXES = ("没有", "无", "并无", "未见", "不是", "未出现", "无明显")

    SYMPTOM_RULES = {
        "胸闷": ("心内科", 4),
        "胸口闷": ("心内科", 4),
        "胸口发闷": ("心内科", 4),
        "发闷": ("心内科", 2),
        "胸痛": ("心内科", 5),
        "心慌": ("心内科", 4),
        "心悸": ("心内科", 4),
        "气短": ("呼吸内科", 3),
        "喘不上气": ("呼吸内科", 5),
        "咳嗽": ("呼吸内科", 3),
        "发热": ("呼吸内科", 2),
        "头晕": ("神经内科", 3),
        "头痛": ("神经内科", 2),
        "手麻": ("神经内科", 3),
        "恶心": ("消化内科", 2),
        "反胃": ("消化内科", 2),
        "胃痛": ("消化内科", 4),
        "胃绞痛": ("消化内科", 5),
        "腹痛": ("消化内科", 4),
        "腹泻": ("消化内科", 4),
        "拉肚子": ("消化内科", 4),
        "呕吐": ("消化内科", 4),
        "肠胃炎": ("消化内科", 5),
        "急性肠胃炎": ("消化内科", 6),
        "腹胀": ("消化内科", 3),
        "骨折": ("骨科", 6),
        "摔倒": ("骨科", 4),
        "扭伤": ("骨科", 2),
        "肿胀": ("骨科", 3),
        "肿得厉害": ("骨科", 4),
        "不能动": ("骨科", 5),
        "走不了路": ("骨科", 5),
        "剧痛": ("骨科", 5),
        "疼得厉害": ("骨科", 4),
        "畸形": ("骨科", 5),
        "关节痛": ("骨科", 4),
        "腰痛": ("骨科", 4),
        "血糖": ("内分泌科", 4),
    }

    HIGH_RISK_KEYWORDS = {
        "胸痛",
        "持续胸痛",
        "呼吸困难",
        "喘不上气",
        "晕厥",
        "意识不清",
        "一侧无力",
        "言语不清",
        "黑便",
        "便血",
        "呕血",
        "血便",
        "剧烈腹痛",
        "突发剧烈腹痛",
        "冷汗",
        "骨头露出来",
        "开放性骨折",
        "明显畸形",
    }
    ELDERLY_HOME_OBSERVATION_KEYWORDS = {"头晕", "恶心", "反胃", "乏力", "轻微头痛", "胃胀"}
    ELDERLY_SOON_KEYWORDS = {"心慌", "心悸", "胃绞痛", "腹绞痛", "急性肠胃炎", "腹泻", "拉肚子", "呕吐", "骨折", "摔倒"}
    ELDERLY_SOON_MODIFIERS = {"反复", "持续", "越来越重", "加重", "难受", "站起来就晕", "走不稳", "吃不下"}
    EXERTIONAL_KEYWORDS = {"走快", "活动后", "上楼", "劳累", "一动就", "稍微活动"}
    DEHYDRATION_KEYWORDS = {"尿少", "口干", "站起来头晕", "心跳快", "乏力明显", "没精神", "脱水"}
    FRACTURE_URGENT_KEYWORDS = {"骨折", "不能动", "走不了路", "明显畸形", "骨头露出来", "开放性骨折", "剧痛", "疼得厉害", "肿得厉害"}
    FRACTURE_SOON_KEYWORDS = {"骨折", "摔倒", "扭伤", "肿胀"}

    def run(self, symptom_text: str) -> TriageResult:
        text = symptom_text.strip()
        symptom_counter: Counter[str] = Counter()
        extracted_symptoms: list[str] = []

        for symptom, (department, weight) in self.SYMPTOM_RULES.items():
            if self._has_positive_keyword(text, symptom):
                extracted_symptoms.append(symptom)
                symptom_counter[department] += weight

        if not extracted_symptoms:
            extracted_symptoms.append("未明确描述症状")
            symptom_counter["全科医学科"] += 1

        if (
            self._has_positive_keyword(text, "胸闷")
            or self._has_positive_keyword(text, "胸口发闷")
        ) and any(
            self._has_positive_keyword(text, keyword) for keyword in self.EXERTIONAL_KEYWORDS
        ):
            symptom_counter["心内科"] += 4
            if "活动后加重" not in extracted_symptoms:
                extracted_symptoms.append("活动后加重")

        if self._count_matches(text, {"腹泻", "拉肚子", "呕吐", "恶心", "胃痛", "腹痛", "胃绞痛"}) >= 2:
            symptom_counter["消化内科"] += 5
            if "胃肠道不适" not in extracted_symptoms:
                extracted_symptoms.append("胃肠道不适")

        if self._count_matches(text, {"骨折", "摔倒", "肿胀", "扭伤", "不能动", "走不了路", "剧痛"}) >= 2:
            symptom_counter["骨科"] += 6
            if "疑似骨伤" not in extracted_symptoms:
                extracted_symptoms.append("疑似骨伤")

        department = symptom_counter.most_common(1)[0][0]
        risk_flag = self._is_high_risk(text)
        elderly_home_observation = self._is_elderly_home_observation_case(text, extracted_symptoms)
        elderly_soon_case = self._is_elderly_soon_case(text, extracted_symptoms)

        if risk_flag:
            urgency = "urgent"
            advice = f"建议尽快前往医院评估，优先挂{department}或直接急诊。"
            warnings = [
                "老人若出现持续胸痛、明显气短、黑便呕血或突然剧烈腹痛，请不要在家等待，优先急诊。",
            ]
        elif elderly_soon_case or any(symptom in extracted_symptoms for symptom in ["胸闷", "胸口发闷", "气短"]):
            urgency = "soon"
            advice = f"考虑到老年人恢复更慢，建议今天或尽快挂{department}门诊，不建议只在家观察。"
            warnings = ["像心慌、胃绞痛、反复腹泻呕吐这类情况，老人建议尽快就医。"]
        elif elderly_home_observation:
            urgency = "routine"
            advice = f"目前可先短时在家观察，如不缓解再挂{department}门诊。"
            warnings = ["老人若只是轻微头晕、恶心且没有加重，可先休息、补水并清淡饮食观察。"]
        else:
            urgency = "routine"
            advice = f"建议先挂{department}门诊，由医生进一步评估。"
            warnings = ["目前更适合常规门诊分诊，如症状持续或加重请尽快就医。"]

        return TriageResult(
            symptoms=extracted_symptoms,
            department=department,
            advice=advice,
            risk_flag=risk_flag,
            urgency=urgency,
            warnings=warnings,
        )

    def _is_high_risk(self, text: str) -> bool:
        if any(self._has_positive_keyword(text, keyword) for keyword in self.HIGH_RISK_KEYWORDS):
            return True
        if self._has_positive_keyword(text, "心慌") and any(
            self._has_positive_keyword(text, keyword) for keyword in {"胸痛", "气短", "晕", "晕厥"}
        ):
            return True
        if self._count_matches(text, self.FRACTURE_URGENT_KEYWORDS) >= 2:
            return True
        if self._count_matches(text, {"腹泻", "拉肚子", "呕吐"}) >= 2 and any(
            self._has_positive_keyword(text, keyword) for keyword in self.DEHYDRATION_KEYWORDS
        ):
            return True
        return False

    def _is_elderly_soon_case(self, text: str, extracted_symptoms: list[str]) -> bool:
        if any(self._has_positive_keyword(text, keyword) for keyword in self.ELDERLY_SOON_KEYWORDS):
            return True
        if self._count_matches(text, self.FRACTURE_SOON_KEYWORDS) >= 1 and any(
            symptom in extracted_symptoms for symptom in {"骨折", "摔倒", "疑似骨伤", "扭伤", "肿胀"}
        ):
            return True
        if any(self._has_positive_keyword(text, keyword) for keyword in self.EXERTIONAL_KEYWORDS) and any(
            symptom in extracted_symptoms for symptom in {"胸闷", "胸口发闷", "心慌", "气短"}
        ):
            return True
        if self._count_matches(text, {"腹泻", "拉肚子", "呕吐", "恶心", "腹痛", "胃绞痛"}) >= 2:
            return True
        if any(self._has_positive_keyword(text, keyword) for keyword in self.ELDERLY_SOON_MODIFIERS) and any(
            symptom in extracted_symptoms for symptom in {"头晕", "恶心", "心慌", "胃痛", "腹痛"}
        ):
            return True
        return False

    def _is_elderly_home_observation_case(self, text: str, extracted_symptoms: list[str]) -> bool:
        if not extracted_symptoms:
            return False
        if any(
            self._has_positive_keyword(text, keyword)
            for keyword in (self.HIGH_RISK_KEYWORDS | self.ELDERLY_SOON_KEYWORDS)
        ):
            return False
        if any(
            self._has_positive_keyword(text, keyword)
            for keyword in (self.EXERTIONAL_KEYWORDS | self.ELDERLY_SOON_MODIFIERS)
        ):
            return False
        if self._count_matches(text, {"腹泻", "拉肚子", "呕吐"}) >= 1:
            return False
        return all(symptom in self.ELDERLY_HOME_OBSERVATION_KEYWORDS for symptom in extracted_symptoms)

    def _count_matches(self, text: str, keywords: set[str]) -> int:
        return sum(1 for keyword in keywords if self._has_positive_keyword(text, keyword))

    def _has_positive_keyword(self, text: str, keyword: str) -> bool:
        return self._text_has_positive_keyword(text, keyword)

    @classmethod
    def _text_has_positive_keyword(cls, text: str, keyword: str) -> bool:
        start = 0
        while True:
            index = text.find(keyword, start)
            if index < 0:
                return False
            prefix = text[max(0, index - 4):index]
            if not any(prefix.endswith(negation) for negation in cls.NEGATION_PREFIXES):
                return True
            start = index + len(keyword)


class LLMTriageAgent(BaseAgent):
    name = "LLMTriageAgent"
    URGENCY_ORDER = {"routine": 0, "soon": 1, "urgent": 2}

    SYSTEM_PROMPT = """
你是老年人就医陪诊系统中的分诊 Agent。
你的职责是把用户的症状描述转换成结构化分诊建议，而不是做疾病诊断。

必须遵守：
1. 只输出适合门诊分诊的建议，不要输出确诊结论。
2. department 只能填写最合适的首诊科室，例如：心内科、呼吸内科、神经内科、消化内科、骨科、内分泌科、全科医学科。
3. urgency 只能是 routine、soon、urgent 之一。
4. risk_flag 仅在存在明显高风险信号时标记为 true，例如：持续胸痛、明显呼吸困难、意识障碍、一侧肢体无力、言语不清、晕厥等。
5. advice 用一句简洁中文说明下一步挂号建议。
6. warnings 输出给老人看的安全提示，必须简短、清晰。
7. symptoms 提取 1 到 5 个关键症状短语，尽量保留用户原意。
8. 如果信息不足，department 可以给出全科医学科，但仍要说明原因。
9. 输出必须严格符合给定的 JSON schema。
10. 这是面向老年人的分诊，分诊阈值要比年轻人更谨慎。
11. 如果只是轻微头晕、轻微恶心、短时反胃，且没有胸痛、气短、反复呕吐腹泻、意识改变、肢体无力等危险信号，可以给 routine，并提示先短时休息、补水、观察。
12. 如果出现心慌、胃绞痛、反复腹泻呕吐、怀疑急性肠胃炎、活动后胸闷或症状明显加重，老年人至少给 soon，提示尽快就医，不要只在家观察。
13. 如果怀疑骨折、摔倒后明显肿胀疼痛、不能活动、走不了路，老年人至少给 soon；若伴随明显畸形、剧痛、开放伤或无法移动，应给 urgent。
""".strip()

    def __init__(
        self,
        fallback_agent: Optional[RuleBasedTriageAgent] = None,
        logger: Optional[Callable[[str, str, str, str], None]] = None,
        ollama_service: Optional[OllamaService] = None,
    ) -> None:
        self.fallback_agent = fallback_agent or RuleBasedTriageAgent()
        self.logger = logger
        self.ollama_service = ollama_service or OllamaService()
        self._result_cache: Dict[str, TriageResult] = {}

    def run(self, symptom_text: str) -> TriageResult:
        cached = self._result_cache.get(symptom_text.strip())
        if cached is not None:
            return cached.model_copy(deep=True)

        if settings.llm_provider != "ollama":
            return self._fallback(symptom_text, f"unsupported_provider:{settings.llm_provider}")

        if not self.ollama_service.ensure_available():
            return self._fallback(symptom_text, "fallback:ollama_unavailable")

        try:
            with httpx.Client(
                trust_env=False,
                timeout=float(settings.ollama_timeout_seconds),
            ) as client:
                response = client.post(
                    f"{settings.ollama_base_url}/api/chat",
                    json={
                        "model": settings.ollama_model,
                        "stream": False,
                        "think": settings.ollama_think,
                        "keep_alive": settings.ollama_keep_alive,
                        "format": TriageResult.model_json_schema(),
                        "messages": [
                            {"role": "system", "content": self.SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": f"请根据这段老人自述做门诊分诊：{symptom_text}",
                            },
                        ],
                        "options": {
                            "temperature": 0,
                            "num_predict": settings.ollama_num_predict,
                        },
                    },
                )
            response.raise_for_status()
            data: Dict = response.json()
            message = (data.get("message") or {}).get("content", "")
            parsed = TriageResult.model_validate_json(message)
            parsed = self._apply_rule_guardrails(symptom_text, parsed)
            self._result_cache[symptom_text.strip()] = parsed
            if self.logger:
                self.logger(settings.ollama_model, symptom_text, parsed.model_dump_json(), "success")
            return parsed
        except Exception as exc:
            return self._fallback(symptom_text, f"fallback:{exc}")

    def _apply_rule_guardrails(self, symptom_text: str, llm_result: TriageResult) -> TriageResult:
        rule_result = self.fallback_agent.run(symptom_text)
        merged = llm_result.model_copy(deep=True)

        if llm_result.department == "全科医学科" and rule_result.department != "全科医学科":
            merged.department = rule_result.department
            merged.advice = rule_result.advice

        if self._should_prefer_rule_routine(symptom_text, rule_result):
            merged.department = rule_result.department
            merged.urgency = rule_result.urgency
            merged.risk_flag = False
            merged.advice = rule_result.advice

        if self.URGENCY_ORDER[rule_result.urgency] > self.URGENCY_ORDER[llm_result.urgency]:
            merged.urgency = rule_result.urgency
            merged.risk_flag = merged.risk_flag or rule_result.risk_flag

        if rule_result.risk_flag and not merged.risk_flag:
            merged.risk_flag = True

        if merged.department == rule_result.department and merged.advice != rule_result.advice:
            merged.advice = rule_result.advice

        merged.symptoms = list(dict.fromkeys((merged.symptoms or []) + (rule_result.symptoms or [])))[:5]
        merged.warnings = list(dict.fromkeys((merged.warnings or []) + (rule_result.warnings or [])))[:4]
        return merged

    @classmethod
    def _should_prefer_rule_routine(cls, symptom_text: str, rule_result: TriageResult) -> bool:
        if rule_result.urgency != "routine" or rule_result.risk_flag:
            return False
        text = symptom_text.strip()
        low_risk_tokens = {"头晕", "恶心", "反胃", "乏力", "轻微头痛", "胃胀"}
        high_risk_tokens = {
            "胸痛",
            "气短",
            "喘不上气",
            "心慌",
            "心悸",
            "胃绞痛",
            "剧烈腹痛",
            "腹泻",
            "拉肚子",
            "呕吐",
            "黑便",
            "便血",
            "呕血",
            "晕厥",
            "意识不清",
            "一侧无力",
            "言语不清",
            "骨折",
            "摔倒",
            "不能动",
            "走不了路",
            "明显畸形",
        }
        if any(RuleBasedTriageAgent._text_has_positive_keyword(text, token) for token in high_risk_tokens):
            return False
        return any(RuleBasedTriageAgent._text_has_positive_keyword(text, token) for token in low_risk_tokens)

    def _fallback(self, symptom_text: str, status: str) -> TriageResult:
        result = self.fallback_agent.run(symptom_text)
        if settings.allow_rule_triage_fallback:
            warning = "当前未完成本地 LLM 分诊，已自动切换为本地规则分诊结果。"
            if warning not in result.warnings:
                result.warnings.append(warning)
        if self.logger:
            self.logger(settings.ollama_model, symptom_text, result.model_dump_json(), status)
        if not settings.allow_rule_triage_fallback:
            raise RuntimeError("Local LLM triage is unavailable and fallback is disabled")
        return result
