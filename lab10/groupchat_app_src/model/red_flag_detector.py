from typing import List, Dict, Any, Optional
import json, re


class LLMRedFlagJudge:

    SYSTEM_PROMPT = (
        "You are a safety and support assistant for a mental-health group chat. "
        "Classify the given message (with brief recent context) into exactly one severity level:\n"
        "1 = nothing_happens  → benign or routine content.\n"
        "2 = notice           → potentially concerning content (subtle self-harm ideation, "
        "hopelessness, harassment hints, escalating conflict) that merits support/monitoring.\n"
        "3 = alert            → explicit or strongly implied self-harm/suicide intent, "
        "imminent danger, or severe hate/harassment targeting a person/group. Immediate escalation.\n\n"
        "Also provide a coarse category: one of [self-harm, hate, harassment, other]. "
        "Do NOT give medical diagnoses. Be concise and neutral."
    )

    OUTPUT_INSTRUCTIONS = (
        "Return STRICT JSON with keys exactly:\n"
        "{\n"
        '  "level": 1|2|3,\n'
        '  "label": "nothing_happens"|"notice"|"alert",\n'
        '  "category": "self-harm"|"hate"|"harassment"|"other",\n'
        '  "rationale": "one short sentence explaining the decision"\n'
        "}\n"
        "No extra text."
    )

    def __init__(self, llm=None, model_name: Optional[str] = None):
        """
        llm: an instance of SupportLLM from your chatbot.py (preferred, reuses the loaded model)
        model_name: if llm is None, provide a HF model name (e.g., 'Qwen/Qwen2.5-1.5B-Instruct')
        """
        if llm is not None:
            self.llm = llm
        else:
            from chatbot import SupportLLM 
            self.llm = SupportLLM(model_name or "Qwen/Qwen2.5-1.5B-Instruct")

        self._base_temp = getattr(self.llm, "temperature", 0.7)
        self._base_topp = getattr(self.llm, "top_p", 0.9)
        self._base_rep  = getattr(self.llm, "repetition_penalty", 1.05)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
        return {}

    async def classify(self, message: str, recent: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        message: the new message to judge
        recent:  optional list of recent chat strings (oldest -> newest)
        """
        recent = recent or []
        context = "Recent messages:\n" + "\n".join(f"- {r}" for r in recent) if recent else "Recent messages: (none)"
        user_prompt = (
            f"{context}\n\n"
            f"Message to classify:\n\"\"\"{message.strip()}\"\"\"\n\n"
            f"{self.OUTPUT_INSTRUCTIONS}"
        )

        orig_t, orig_p, orig_r = self.llm.temperature, self.llm.top_p, self.llm.repetition_penalty
        self.llm.temperature, self.llm.top_p, self.llm.repetition_penalty = 0.2, 0.95, 1.0
        out = self.llm.generate(self.SYSTEM_PROMPT, history=[], user_message=user_prompt).strip()
        self.llm.temperature, self.llm.top_p, self.llm.repetition_penalty = orig_t, orig_p, orig_r

        obj = self._parse_json(out)

        lvl_map = {1: "nothing_happens", 2: "notice", 3: "alert"}
        level = int(obj.get("level", 1)) if str(obj.get("level", "")).strip().isdigit() else 1
        if level not in (1, 2, 3):
            level = 1
        label = obj.get("label") or lvl_map[level]
        if label not in ("nothing_happens", "notice", "alert"):
            label = lvl_map[level]
        category = obj.get("category", "other")
        if category not in ("self-harm", "hate", "harassment", "other"):
            category = "other"
        rationale = str(obj.get("rationale", "")).strip() or "No rationale provided."

   
        from chatbot import enforce_no_diagnosis  # reuse your helper
        rationale = enforce_no_diagnosis(rationale)

        return {
            "level": level,
            "label": label,
            "category": category,
            "rationale": rationale,
            "raw": out  # keep raw for logging/audit if you want
        }

    def batch_classify(self, texts: List[str]) -> List[Dict[str, Any]]:
        return [self.classify(t) for t in texts]

"""
bot = MentalHealthChatbot()             
from red_flag_detector import LLMRedFlagJudge
judge = LLMRedFlagJudge(llm=bot.llm)


res = judge.classify(
    "I don't want to be here anymore.",
    recent=["are you okay?", "we care about you"]
)
print(res)
# -> {'level': 3, 'label': 'alert', 'category': 'self-harm', 'rationale': '...','raw': '...'}
"""