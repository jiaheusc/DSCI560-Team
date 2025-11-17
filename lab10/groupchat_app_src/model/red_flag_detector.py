from typing import Tuple, Dict, Any
from model2vec.inference import StaticModelPipeline

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



class RedFlagDetector:
    """
    Minimal self-harm detector for:
      enguard/tiny-guard-4m-en-prompt-self-harm-binary-moderation

    Returns:
      flagged: True if text is self-harm (label == 'FAIL' or FAIL prob >= threshold)
      score:   probability for FAIL (if available; else 1.0 for FAIL, 0.0 for PASS)
      label:   'FAIL' | 'PASS' from the model
    """

    def __init__(self, threshold: float = 0.50,
                 repo_id: str = "enguard/tiny-guard-4m-en-prompt-self-harm-binary-moderation"):
        self.threshold = float(threshold)
        self.pipe = StaticModelPipeline.from_pretrained(repo_id)

    def detect(self, text: str) -> Tuple[bool, float, str]:
        if not text or not text.strip():
            return (False, 0.0, "PASS")

        label: str = self.pipe.predict([text])[0]                 # 'FAIL' or 'PASS'
        proba: Dict[str, Any] = self.pipe.predict_proba([text])[0]  # e.g., {'FAIL': 0.12, 'PASS': 0.88}

        fail_p = None
        # normalize keys just in case
        if isinstance(proba, dict):
            # make keys upper and pick FAIL if present
            probs_norm = {str(k).upper(): float(v) for k, v in proba.items()}
            fail_p = probs_norm.get("FAIL")

        # if prob not provided, fall back to hard 1/0 from label
        if fail_p is None:
            fail_p = 1.0 if label.upper() == "FAIL" else 0.0

        # final decision:
        # - if label is FAIL, always flag True (hard signal)
        # - else use probability threshold (useful if you want softer behavior)
        flagged = (label.upper() == "FAIL") or (fail_p >= self.threshold)
        return (flagged, fail_p, label)


"""
from red_flag_detector import RedFlagDetector
det = RedFlagDetector(threshold=0.5)
print(det.detect("I feel like hurting myself tonight."))  # -> (True, ~0.9, 'FAIL')
print(det.detect("Thanks, I’m okay today."))              # -> (False, ~0.0, 'PASS')

"""