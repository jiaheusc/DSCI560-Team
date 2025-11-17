import json
import os
from typing import List, Dict, Any, Optional

import numpy as np
import faiss
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import (
    pipeline,
    AutoTokenizer,
    AutoModelForCausalLM
)
from sentence_transformers import SentenceTransformer



LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "mistralai/Mistral-7B-Instruct-v0.3") 
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "BAAI/bge-small-en-v1.5")
SELF_HARM_MODEL_NAME = os.getenv(
    "SELF_HARM_MODEL_NAME",
    "enguard/tiny-guard-4m-en-prompt-self-harm-binary-moderation"
)

RESOURCES_PATH = os.getenv("RESOURCES_PATH", "resources.json")

TOP_K_RESOURCES = 3
SELF_HARM_THRESHOLD = 0.5  # tune based on your experiments


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

CRISIS_TEMPLATE = """I'm really glad you reached out and shared this. 

I’m an AI assistant, not a medical professional, so I can’t fully understand everything you’re going through or give a diagnosis. But what you’re describing sounds very important.

If you are in immediate danger or feel you might act on these thoughts, please:
- Contact your local emergency number right now, or
- Call or text a crisis hotline (for example, 988 in the U.S. for the Suicide & Crisis Lifeline), or
- Reach out to someone you trust (friend, family member, counselor) and tell them how you're feeling.

You deserve support from real people who can help you stay safe. If you’d like, I can also share some supportive resources and ideas for coping while you reach out for help.
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


# =========================
# SAFETY / MODERATION
# =========================

class SafetyChecker:
    def __init__(self, model_name: str):
        # Binary: SAFE vs SELF-HARM / crisis
        self.pipe = pipeline("text-classification", model=model_name, top_k=None)

    def is_self_harm_risk(self, text: str) -> bool:
        """
        Expects model with labels like:
        - "NON_SELF_HARM", "SELF_HARM" or similar.
        Adjust label names based on the HF model card.
        """
        preds = self.pipe(text)[0]
        # Normalize to dict
        label_scores = {p["label"].lower(): p["score"] for p in preds}
        # Heuristic: any self-harm-ish label above threshold
        for label, score in label_scores.items():
            if "self" in label or "harm" in label or "suic" in label:
                if score >= SELF_HARM_THRESHOLD:
                    return True
        return False


# =========================
# LLM WRAPPER
# =========================

class SupportLLM:
    def __init__(self, model_name: str):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.gen = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            max_new_tokens=512,
            do_sample=True,
            top_p=0.9,
            temperature=0.7,
        )

    def build_prompt(self, system_prompt: str,
                     history: List[Dict[str, str]],
                     user_message: str) -> str:

        prompt_parts = [f"[SYSTEM]\n{system_prompt}\n"]
        if history:
            for turn in history:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role == "user":
                    prompt_parts.append(f"[USER]\n{content}\n")
                else:
                    prompt_parts.append(f"[ASSISTANT]\n{content}\n")
        prompt_parts.append(f"[USER]\n{user_message}\n[ASSISTANT]\n")
        return "\n".join(prompt_parts)

    def generate(self,
                 system_prompt: str,
                 history: List[Dict[str, str]],
                 user_message: str) -> str:
        prompt = self.build_prompt(system_prompt, history, user_message)
        out = self.gen(prompt, num_return_sequences=1)[0]["generated_text"]
        # Take only content after last [ASSISTANT]
        last = out.rfind("[ASSISTANT]")
        if last != -1:
            answer = out[last + len("[ASSISTANT]"):].strip()
        else:
            answer = out.strip()
        return answer


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
        self.safety = SafetyChecker(SELF_HARM_MODEL_NAME)
        self.llm = SupportLLM(LLM_MODEL_NAME)

    def handle_message(self, req: ChatRequest) -> ChatResponse:
        user_msg = req.message.strip()
        history = req.history or []

        # 1. Self-harm / crisis detection
        if self.safety.is_self_harm_risk(user_msg):
            return ChatResponse(
                reply=CRISIS_TEMPLATE,
                resources=[
                    r for r in self.retriever.retrieve("suicide self-harm crisis help", top_k=TOP_K_RESOURCES)
                ],
                flagged_risk=True
            )

        # 2. Resource-seeking?
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

        # 3. Normal supportive conversation
        base_reply = self.llm.generate(SAFETY_SYSTEM_PROMPT, history, user_msg)
        base_reply = enforce_no_diagnosis(base_reply)
        return ChatResponse(
            reply=base_reply,
            resources=[],
            flagged_risk=False
        )
















