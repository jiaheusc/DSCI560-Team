"""
    @software{minishlab2024model2vec,
    author       = {Stephan Tulkens and {van Dongen}, Thomas},
    title        = {Model2Vec: Fast State-of-the-Art Static Embeddings},
    year         = {2024},
    publisher    = {Zenodo},
    doi          = {10.5281/zenodo.17270888},
    url          = {https://github.com/MinishLab/model2vec},
    license      = {MIT}
    }

"""





# - Self-harm: enguard/tiny-guard-4m-en-prompt-self-harm-binary-moderation
# - Hate     : enguard/tiny-guard-4m-en-prompt-hate-binary-moderation
#
#   detect_self_harm(text) -> 'PASS' | 'FAIL'
#   detect_hate(text)      -> 'PASS' | 'FAIL'
#   check_both(text)       -> {'self_harm': 'PASS|FAIL', 'hate': 'PASS|FAIL'}
#   batch_check_both(texts)-> [{'self_harm':..., 'hate':...}, ...]
#
# Install:
#   pip install "model2vec[inference]" torch

from typing import List, Dict
from model2vec.inference import StaticModelPipeline


_SELF_HARM_MODEL = None
_HATE_MODEL = None

def _get_self_harm_model() -> StaticModelPipeline:
    global _SELF_HARM_MODEL
    if _SELF_HARM_MODEL is None:
        _SELF_HARM_MODEL = StaticModelPipeline.from_pretrained(
            "enguard/tiny-guard-8m-en-prompt-self-harm-binary-moderation"
        )
    return _SELF_HARM_MODEL

def _get_hate_model() -> StaticModelPipeline:
    global _HATE_MODEL
    if _HATE_MODEL is None:
        _HATE_MODEL = StaticModelPipeline.from_pretrained(
            "enguard/tiny-guard-8m-en-prompt-hate-binary-moderation"
        )
    return _HATE_MODEL


def detect_self_harm(text: str) -> str:
    """
    Return 'PASS' or 'FAIL' from the self-harm model.
    Empty/whitespace is treated as 'PASS'.
    """
    t = (text or "").strip()
    if not t:
        return "PASS"
    return _get_self_harm_model().predict([t])[0]

def detect_hate(text: str) -> str:
    """
    Return 'PASS' or 'FAIL' from the hate model.
    Empty/whitespace is treated as 'PASS'.
    """
    t = (text or "").strip()
    if not t:
        return "PASS"
    return _get_hate_model().predict([t])[0]

def check_both(text: str) -> Dict[str, str]:
    """
    Check both categories for a single string.
    Returns {'self_harm': 'PASS|FAIL', 'hate': 'PASS|FAIL'}.
    """
    return {
        "self_harm": detect_self_harm(text),
        "hate": detect_hate(text),
    }

def batch_check_both(texts: List[str]) -> List[Dict[str, str]]:
    """
    Batch version for efficiency: runs each model once across the non-empty subset,
    then stitches results back to the original order.
    """
    if not texts:
        return []

    cleaned = [(x or "").strip() for x in texts]
    idx = [i for i, s in enumerate(cleaned) if s]

    out_self: List[str] = ["PASS"] * len(cleaned)
    out_hate: List[str] = ["PASS"] * len(cleaned)

    if idx:
        non_empty = [cleaned[i] for i in idx]
        sh_labels = _get_self_harm_model().predict(non_empty)
        ht_labels = _get_hate_model().predict(non_empty)
        for k, i in enumerate(idx):
            out_self[i] = sh_labels[k]
            out_hate[i] = ht_labels[k]

    return [{"self_harm": s, "hate": h} for s, h in zip(out_self, out_hate)]


