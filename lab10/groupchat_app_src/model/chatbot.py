import json
from typing import List, Dict, Any, Optional

import numpy as np
import faiss

from pydantic import BaseModel
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM
)
from sentence_transformers import SentenceTransformer
import os, torch


LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct") 
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "BAAI/bge-small-en-v1.5")
RESOURCES_PATH = os.getenv("RESOURCES_PATH", "resources.json")

TOP_K_RESOURCES = 3



SAFETY_SYSTEM_PROMPT = """You are a supportive mental health support assistant for the MindMe app.

Rules:
- You are NOT a doctor or therapist. Never claim to diagnose any condition.
- Never say things like "You have depression" or "I diagnose you with X".
- Use careful language: talk about "signs", "patterns", "it might help to talk to a professional".
- Provide emotional support: validate feelings, be kind, never judgmental.
- Provide only safe, general self-help strategies (breathing exercises, grounding, journaling, reaching out to friends, sleep hygiene, etc.).
- Encourage seeking professional help when struggles are persistent, severe, or affecting daily life.
- If the user asks for resources, you may reference links or items from the provided resource list.
- If the user mentions self-harm, suicidal thoughts, or immediate danger, you MUST:
  1) Respond with empathy.
  2) Encourage them to reach immediate human help (hotlines, emergency services, trusted people).
  3) Not provide instructions or encouragement for self-harm.
- Do not give medication instructions or specific treatment plans.
Keep responses concise, warm, and clear.
"""


class ChatRequest(BaseModel):
    user_id: str
    message: str
    history: Optional[List[Dict[str, str]]] = None  # [{role: "user"/"assistant", "content": "..."}]


class ChatResponse(BaseModel):
    reply: str
    resources: List[Dict[str, Any]] = []  # optional resource suggestions
    flagged_risk: bool = False



class ResourceRetriever:
    def __init__(self, embed_model_name: str, resources_path: str):
        self.embedder = SentenceTransformer(embed_model_name)
        self.resources = self._load_resources(resources_path)
        self.index, self.resource_vectors = self._build_index(self.resources)

    def _load_resources(self, path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            # Fallback minimal resources; replace with your curated list
            return [
                {
                    "id": "anxiety_coping_basics",
                    "title": "Coping with Anxiety: Practical Strategies",
                    "topics": ["anxiety", "panic", "worry", "stress"],
                    "summary": "Simple breathing, grounding, and routine tips for managing anxiety.",
                    "url": "https://www.nimh.nih.gov/health/topics/anxiety-disorders"
                },
                {
                    "id": "depression_support_basics",
                    "title": "When You Feel Down: Getting Support",
                    "topics": ["low mood", "sadness", "motivation"],
                    "summary": "Information on mood, support options, and when to seek professional help.",
                    "url": "https://www.nimh.nih.gov/health/topics/depression"
                },
                {
                    "id": "us_crisis_988",
                    "title": "988 Suicide & Crisis Lifeline (US)",
                    "topics": ["crisis", "self-harm", "suicide"],
                    "summary": "24/7 free and confidential support for people in distress.",
                    "url": "https://988lifeline.org/"
                }
            ]
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _encode(self, text: str) -> np.ndarray:
        v = self.embedder.encode([text], show_progress_bar=False, normalize_embeddings=True)[0]
        return np.array(v, dtype="float32")

    def _build_index(self, resources: List[Dict[str, Any]]):
        if not resources:
            return None, None

        vectors = []
        for r in resources:
            blob = " ".join([
                r.get("title", ""),
                r.get("summary", ""),
                " ".join(r.get("topics", []))
            ])
            vectors.append(self._encode(blob))

        mat = np.vstack(vectors).astype("float32")
        dim = mat.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(mat)
        return index, mat

    def retrieve(self, query: str, top_k: int = TOP_K_RESOURCES) -> List[Dict[str, Any]]:
        if self.index is None:
            return []

        q_vec = self._encode(query).reshape(1, -1)
        scores, idxs = self.index.search(q_vec, top_k)
        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            r = dict(self.resources[idx])
            r["score"] = float(score)
            results.append(r)
        return results



from transformers import AutoTokenizer, AutoModelForCausalLM
import torch, os

class SupportLLM:
    def __init__(self, model_name: str):
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, use_fast=True, trust_remote_code=True
        )

        # === GPU load ===
        if torch.cuda.is_available():
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                trust_remote_code=True,
                device_map="auto",                           # place on GPU
                torch_dtype=(torch.bfloat16
                             if torch.cuda.is_bf16_supported()
                             else torch.float16),
                low_cpu_mem_usage=True,
            )
        else:
            # CPU fallback
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
            )

        # pad_token → eos
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model.config.pad_token_id = self.tokenizer.eos_token_id

        # Generation knobs (constants)
        self.max_new_tokens = 1000
        self.temperature = 0.7
        self.top_p = 0.9
        self.repetition_penalty = 1.05

    def _to_chat_messages(self, system_prompt, history, user_message):
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        for turn in (history or []):
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role not in ("user", "assistant"):
                role = "user"
            msgs.append({"role": role, "content": content})
        msgs.append({"role": "user", "content": user_message})
        return msgs

    def generate(self, system_prompt, history, user_message) -> str:
        messages = self._to_chat_messages(system_prompt, history, user_message)
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        # >>> ensure tensors are on the model's device (GPU if available)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=True,
                temperature=self.temperature,
                top_p=self.top_p,
                repetition_penalty=self.repetition_penalty,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        gen_ids = outputs[0]
        new_ids = gen_ids[inputs["input_ids"].shape[1]:] 
        text = self.tokenizer.decode(new_ids, skip_special_tokens=True).strip()
        return text.split(messages[-1]["content"])[-1].strip()


# =========================
# INTENT + DIAGNOSIS-GUARD HELPERS
# =========================

RESOURCE_KEYWORDS = [
    "resource", "resources", "help line", "hotline", "support group",
    "where can I get help", "how can I cope", "what can I do about",
    "counseling", "therapy information", "info about"
]

def is_resource_intent(message: str) -> bool:
    m = message.lower()
    return any(kw in m for kw in RESOURCE_KEYWORDS)


def enforce_no_diagnosis(text: str) -> str:
    """
    Simple safety net: avoid hard diagnostic statements.
    You can refine with regex or more patterns.
    """
    bad_phrases = [
        "i diagnose you", "i can diagnose you",
        "you have depression", "you have anxiety",
        "you have bipolar", "you have ptsd",
        "this confirms you have", "it proves you have"
    ]

    lowered = text.lower()
    if any(p in lowered for p in bad_phrases):
        text += (
            "\n\nTo clarify: I cannot provide any diagnosis. "
            "If you're concerned about specific conditions, "
            "please talk with a licensed mental health professional."
        )

    return text


def attach_resources_to_reply(reply: str, resources: List[Dict[str, Any]]) -> str:
    if not resources:
        return reply
    lines = [reply, "", "Here are some resources that might be helpful:"]
    for r in resources:
        line = f"- {r.get('title')}"
        if r.get("url"):
            line += f": {r['url']}"
        if r.get("summary"):
            line += f" — {r['summary']}"
        lines.append(line)
    return "\n".join(lines)


# =========================
# MAIN CHATBOT WRAPPER
# =========================

class MentalHealthChatbot:
    def __init__(self):
        self.retriever = ResourceRetriever(EMBED_MODEL_NAME, RESOURCES_PATH)
        self.llm = SupportLLM(LLM_MODEL_NAME)

    def handle_message(self, req: ChatRequest) -> ChatResponse:
        user_msg = req.message.strip()
        history = req.history or []

        #Resource-seeking?
        if is_resource_intent(user_msg):
            resources = self.retriever.retrieve(user_msg, top_k=TOP_K_RESOURCES)
            base_reply = self.llm.generate(SAFETY_SYSTEM_PROMPT, history, user_msg)
            base_reply = enforce_no_diagnosis(base_reply)
            full_reply = attach_resources_to_reply(base_reply, resources)
            return ChatResponse(
                reply=full_reply,
                resources=resources,
                flagged_risk=False
            )

        #Normal supportive conversation
        base_reply = self.llm.generate(SAFETY_SYSTEM_PROMPT, history, user_msg)
        base_reply = enforce_no_diagnosis(base_reply)
        return ChatResponse(
            reply=base_reply,
            resources=[],
            flagged_risk=False
        )


if __name__ == "__main__":
    print("cuda?", torch.cuda.is_available())
    if torch.cuda.is_available():
      print("device:", torch.cuda.get_device_name(0))

    bot = MentalHealthChatbot()
    demo = [
        "I’ve been anxious before presentations. Any tips?",
        "Where can I find resources for coping with panic attacks?",
        "I feel stuck and unmotivated lately.",
    ]
    for msg in demo:
        res = bot.handle_message(ChatRequest(user_id="u1", message=msg, history=[]))
        print("\nUSER:", msg)
        print("BOT :", res.reply)