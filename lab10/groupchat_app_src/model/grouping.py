"""
 Call:
    from grouping_min import GroupAssigner
    ga = GroupAssigner(db_url="mysql+pymysql://chatuser:chatpass@localhost:3306/groupchat")
    gid = ga.assign(user_id) 
"""

import os
import json
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sentence_transformers import SentenceTransformer

DEFAULT_DB_URL = "mysql+pymysql://chatuser:chatpass@localhost:3306/groupchat"
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", "0.65"))     # accept into group if sim >= τ
LENIENCY_GAMMA = float(os.getenv("LENIENCY_GAMMA", "0.07"))   # don't undercut group's avg by > γ
DEFAULT_GROUP_MAX_SIZE = int(os.getenv("DEFAULT_GROUP_MAX_SIZE", "8"))
DROP_SENSITIVE = (os.getenv("DROP_SENSITIVE", "true").lower() == "true")  # exclude Age/Gender from similarity


def _l2(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v) + 1e-12
    return v / n

def _to_blob(v: np.ndarray) -> bytes:
    assert v.dtype == np.float32
    return v.tobytes()

def _from_blob(b: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32, count=dim)


class GroupAssigner:
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


    # ---- questionnaire parsing & embedding (reads existing answers from DB)
    @staticmethod
    def _normalize_answer(ans: Any) -> str:
        if ans is None:
            return ""
        if isinstance(ans, list):
            return "; ".join(str(x) for x in ans if x is not None)
        return str(ans)

    def _render_questionnaire_text(self, q_json: Dict[str, Any]) -> str:
        # expected shape: {"content":{"mood":[{"question":..., "answer":...|[...]}, ...]}}
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
        text_blob = "\n".join(lines).strip()
        return text_blob if text_blob else "no questionnaire content provided"

    def _get_or_build_user_embedding(self, sess, user_id: int) -> Tuple[np.ndarray, int]:
        row = sess.execute(text(
            "SELECT model, dim, vec FROM user_questionnaire_embeddings WHERE user_id=:u"
        ), {"u": user_id}).fetchone()
        if row:
            return _from_blob(row.vec, row.dim), row.dim

        uq = sess.execute(text(
            "SELECT answers FROM user_questionnaires WHERE user_id=:u"
        ), {"u": user_id}).fetchone()
        if uq is None:
            raise ValueError("No questionnaire answers stored for this user_id.")

        q_json = uq.answers if isinstance(uq.answers, dict) else json.loads(uq.answers)
        text_blob = self._render_questionnaire_text(q_json)
        vec = self.embedder.encode([text_blob], normalize_embeddings=True, show_progress_bar=False)[0].astype(np.float32)
        dim = int(vec.shape[0])

        sess.execute(text(
            "REPLACE INTO user_questionnaire_embeddings (user_id, model, dim, vec) "
            "VALUES (:u, :m, :d, :v)"
        ), {"u": user_id, "m": self.embed_model_name, "d": dim, "v": _to_blob(vec)})
        return vec, dim

    # ---- grouping core
    def _fetch_candidate_groups(self, sess):
        return sess.execute(text("""
            SELECT g.id, COALESCE(gp.model, :m) AS model, gp.dim, gp.centroid,
                   gp.n_members, gp.avg_sim, g.max_size,
                   (SELECT COUNT(*) FROM chat_group_users cgu
                    WHERE cgu.group_id = g.id AND cgu.is_active=TRUE) AS cur_size
            FROM chat_groups g
            LEFT JOIN group_profiles gp ON gp.group_id = g.id
            WHERE g.is_active = TRUE
              AND COALESCE((SELECT COUNT(*) FROM chat_group_users cgu
                            WHERE cgu.group_id = g.id AND cgu.is_active=TRUE), 0) < g.max_size
        """), {"m": self.embed_model_name}).fetchall()

    @staticmethod
    def _choose_best_group(candidates, e: np.ndarray,
                           sim_threshold: float, leniency_gamma: float) -> Optional[int]:
        best_gid, best_sim, best_avg = None, -1.0, 0.0
        for row in candidates:
            if row.centroid is None:
                continue
            c = _from_blob(row.centroid, row.dim)
            sim = float(np.dot(c, e))  # cosine (vectors are normalized)
            if sim > best_sim:
                best_gid, best_sim, best_avg = row.id, sim, row.avg_sim
        if best_gid is not None and best_sim >= sim_threshold and best_sim >= (best_avg - leniency_gamma):
            return best_gid
        return None

    def _create_new_group(self, sess, seed_vec: np.ndarray, dim: int) -> int:
        gid = sess.execute(text(
            "INSERT INTO chat_groups (group_name, is_active, max_size) VALUES (:n, TRUE, :ms)"
        ), {"n": "Support Group", "ms": DEFAULT_GROUP_MAX_SIZE}).lastrowid
        sess.execute(text(
            "INSERT INTO group_profiles (group_id, model, dim, centroid, n_members, avg_sim) "
            "VALUES (:g, :m, :d, :c, 0, 0.0)"
        ), {"g": gid, "m": self.embed_model_name, "d": dim, "c": _to_blob(seed_vec)})
        return gid

    @staticmethod
    def _add_member(sess, gid: int, uid: int):
        sess.execute(text("""
            INSERT IGNORE INTO chat_group_users (group_id, user_id, is_active)
            VALUES (:g, :u, TRUE)
        """), {"g": gid, "u": uid})

    @staticmethod
    def _update_centroid(sess, gid: int, e: np.ndarray):
        row = sess.execute(text(
            "SELECT dim, centroid, n_members, avg_sim FROM group_profiles WHERE group_id=:g FOR UPDATE"
        ), {"g": gid}).fetchone()
        if row is None:
            return
        c_old = _from_blob(row.centroid, row.dim)
        n = row.n_members
        sim_to_old = float(np.dot(c_old, e))
        c_new = _l2((c_old * (n / (n + 1.0))) + (e * (1.0 / (n + 1.0))))
        avg_sim_new = (row.avg_sim * n + sim_to_old) / (n + 1.0)
        sess.execute(text(
            "UPDATE group_profiles SET centroid=:c, n_members=:n2, avg_sim=:a WHERE group_id=:g"
        ), {"c": _to_blob(c_new.astype(np.float32)), "n2": n + 1, "a": avg_sim_new, "g": gid})

   


    def assign(self, user_id: int,
               sim_threshold: float = SIM_THRESHOLD,
               leniency_gamma: float = LENIENCY_GAMMA) -> int:
        with self.Session() as sess:
            e, dim = self._get_or_build_user_embedding(sess, user_id)
            candidates = self._fetch_candidate_groups(sess)
            gid = self._choose_best_group(candidates, e, sim_threshold, leniency_gamma)
            if gid is None:
                gid = self._create_new_group(sess, e, dim)
            self._add_member(sess, gid, user_id)
            self._update_centroid(sess, gid, e)
            sess.commit()
            return gid
