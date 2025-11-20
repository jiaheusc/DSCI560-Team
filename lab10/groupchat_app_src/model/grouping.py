
"""
Usage:
    rec = GroupRecommender(db_url="mysql+pymysql://chatuser:chatpass@localhost:3306/groupchat")
    result = rec.recommend(user_id=42)
    # result -> {'decision':'group', 'group_id': 5, 'score':0.72, 'threshold':0.65, 'reason':'passes_threshold'}
    # or      -> {'decision':'new_group', 'score':0.58, 'threshold':0.65, 'reason':'below_threshold'}
"""

import os, json
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sentence_transformers import SentenceTransformer

DEFAULT_DB_URL =  "sqlite+aiosqlite:////absolute/path/to/groupchat.db"

EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")

SIM_THRESHOLD     = float(os.getenv("SIM_THRESHOLD",     "0.65"))  # accept if sim >= τ
LENIENCY_GAMMA    = float(os.getenv("LENIENCY_GAMMA",    "0.07"))  # don't undercut group avg by > γ
DROP_SENSITIVE    = (os.getenv("DROP_SENSITIVE", "true").lower() == "true")  # exclude Age/Gender from similarity
MAX_GROUP_FILTER  = True  # only consider groups that aren't full

def _from_blob(b: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32, count=dim)

def _l2(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v) + 1e-12
    return v / n

class GroupRecommender:
    SENSITIVE_QUESTIONS = {"Age Group", "Gender"}
    QUESTION_WEIGHTS = {
        "What are you mainly looking for here?": 1.4,
        "What are you currently struggling with the most?": 1.6,
        "What kind of group atmosphere feels most comfortable to you?": 1.3,
        "How do you prefer to communicate?": 1.2,
    }

    def __init__(self, db_url: Optional[str] = None,
                 embed_model: str = EMBED_MODEL,
                 drop_sensitive: bool = DROP_SENSITIVE):
        self.db_url = db_url or DEFAULT_DB_URL
        self.engine = create_engine(self.db_url, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine)
        self.embedder = SentenceTransformer(embed_model)
        self.embed_model_name = embed_model
        self.drop_sensitive = drop_sensitive

    # ---------- public ----------
    def recommend(self, user_id: int) -> Dict[str, Any]:
        """
        Returns a read-only recommendation dict:
          - decision: 'group' | 'new_group' | 'no_groups_configured'
          - group_id: int | None
          - score: float (best cosine)
          - threshold: float
          - reason: short string
          - top_candidates: [(group_id, sim)]  (first 5 for transparency)
        """
        with self.Session() as sess:
            # 1) get user embedding (read-only; try cache first; never write)
            e, dim = self._get_user_embedding_readonly(sess, user_id)
            if e is None:
                # build on the fly (still read-only; do not store)
                q_json = self._load_answers(sess, user_id)
                if q_json is None:
                    return {"decision":"no_groups_configured","group_id":None,"score":0.0,
                            "threshold":SIM_THRESHOLD,"reason":"no_questionnaire","top_candidates":[]}
                e, dim = self._embed_answers(q_json)

            # 2) fetch candidate groups (active; not full if MAX_GROUP_FILTER)
            candidates = self._fetch_candidates(sess)

            if not candidates:
                return {"decision":"no_groups_configured","group_id":None,"score":0.0,
                        "threshold":SIM_THRESHOLD,"reason":"no_active_groups","top_candidates":[]}

            # 3) score each group's centroid
            sims = []
            for row in candidates:
                if row.centroid is None:
                    continue
                c = _from_blob(row.centroid, row.dim)
                sims.append((row.id, float(np.dot(c, e)), float(row.avg_sim)))

            if not sims:
                return {"decision":"no_groups_configured","group_id":None,"score":0.0,
                        "threshold":SIM_THRESHOLD,"reason":"no_group_centroids","top_candidates":[]}

            sims.sort(key=lambda x: x[1], reverse=True)
            top5 = [(gid, round(sim, 4)) for gid, sim, _ in sims[:5]]

            best_gid, best_sim, best_avg = sims[0]

            # 4) gating rules (read-only recommendation)
            if best_sim >= SIM_THRESHOLD and best_sim >= (best_avg - LENIENCY_GAMMA):
                return {
                    "decision": "group",
                    "group_id": int(best_gid),
                    "score": float(best_sim),
                    "threshold": SIM_THRESHOLD,
                    "reason": "passes_threshold",
                    "top_candidates": top5
                }
            else:
                return {
                    "decision": "new_group",
                    "group_id": None,
                    "score": float(best_sim),
                    "threshold": SIM_THRESHOLD,
                    "reason": "below_threshold" if best_sim < SIM_THRESHOLD else "undercuts_group_avg",
                    "top_candidates": top5
                }


    def _get_user_embedding_readonly(self, sess, user_id: int) -> Tuple[Optional[np.ndarray], Optional[int]]:
        row = sess.execute(text(
            "SELECT model, dim, vec FROM user_questionnaire_embeddings WHERE user_id=:u"
        ), {"u": user_id}).fetchone()
        if not row:
            return None, None
        return _l2(_from_blob(row.vec, row.dim)), row.dim

    def _load_answers(self, sess, user_id: int) -> Optional[Dict[str, Any]]:
        row = sess.execute(text(
            "SELECT answers FROM user_questionnaires WHERE user_id=:u"
        ), {"u": user_id}).fetchone()
        if not row:
            return None
        return row.answers if isinstance(row.answers, dict) else json.loads(row.answers)

    def _embed_answers(self, q_json: Dict[str, Any]) -> Tuple[np.ndarray, int]:
        text_blob = self._render_questionnaire_text(q_json)
        v = self.embedder.encode([text_blob], normalize_embeddings=True, show_progress_bar=False)[0].astype(np.float32)
        return v, int(v.shape[0])

    def _render_questionnaire_text(self, q_json: Dict[str, Any]) -> str:
        items: List[Dict[str, Any]] = q_json.get("content", {}).get("mood", [])
        lines: List[str] = []
        for item in items:
            q = str(item.get("question", "")).strip()
            a = self._normalize_answer(item.get("answer"))
            if not q or not a:
                continue
            if self.drop_sensitive and q in self.SENSITIVE_QUESTIONS:
                continue
            w = self.QUESTION_WEIGHTS.get(q, 1.0)
            line = f"{q}: {a}"
            if w > 1.0:
                repeats = 1 if w < 1.35 else 2
                for _ in range(repeats):
                    lines.append(line)
            else:
                lines.append(line)
        txt = "\n".join(lines).strip()
        return txt if txt else "no questionnaire content provided"

    @staticmethod
    def _normalize_answer(ans: Any) -> str:
        if ans is None:
            return ""
        if isinstance(ans, list):
            return "; ".join(str(x) for x in ans if x is not None)
        return str(ans)

    def _fetch_candidates(self, sess):
        base_sql = """
            SELECT g.id, COALESCE(gp.model, :m) AS model, gp.dim, gp.centroid,
                   gp.n_members, gp.avg_sim, g.max_size,
                   (SELECT COUNT(*) FROM chat_group_users cgu
                    WHERE cgu.group_id = g.id AND cgu.is_active=TRUE) AS cur_size
            FROM chat_groups g
            LEFT JOIN group_profiles gp ON gp.group_id = g.id
            WHERE g.is_active = TRUE
        """
        if MAX_GROUP_FILTER:
            base_sql += " AND COALESCE((SELECT COUNT(*) FROM chat_group_users cgu WHERE cgu.group_id = g.id AND cgu.is_active=TRUE), 0) < g.max_size"
        return sess.execute(text(base_sql), {"m": self.embed_model_name}).fetchall()

