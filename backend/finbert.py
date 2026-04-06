"""FinBERT GPU-accelerated sentiment analysis for financial text.

Uses ProsusAI/finbert — a BERT model fine-tuned on financial news and filings.
Falls back to VADER if CUDA is unavailable or model fails to load.

RTX 5080 (Blackwell) requires:
  - CUDA 12.6+
  - PyTorch 2.6+
  - transformers >= 4.40.0
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import GPU stack — gracefully degrade if missing
try:
    import torch
    from transformers import BertTokenizer, BertForSequenceClassification
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.warning("PyTorch/transformers not installed — falling back to VADER")


FINBERT_MODEL = "ProsusAI/finbert"
# FinBERT label mapping (model outputs these class indices)
LABEL_MAP = {0: "positive", 1: "negative", 2: "neutral"}
SCORE_MAP = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}

# Max tokens FinBERT can handle (BERT limit is 512)
MAX_TOKENS = 512
# Batch size — tune based on VRAM. RTX 5080 16GB can handle 64+ easily
BATCH_SIZE = 32


@dataclass
class FinBERTResult:
    text: str
    label: str       # "positive", "negative", "neutral"
    score: float     # -1.0 to +1.0
    confidence: float  # softmax probability of winning class
    positive_prob: float
    negative_prob: float
    neutral_prob: float


class FinBERTAnalyzer:
    """GPU-accelerated financial sentiment using FinBERT.

    Usage:
        analyzer = FinBERTAnalyzer()
        result = analyzer.analyze("Apple beats earnings expectations")
        print(result.score)   # e.g. +0.92
    """

    def __init__(self, device: Optional[str] = None):
        self.ready = False
        self.device = None
        self._tokenizer = None
        self._model = None

        if not HAS_TORCH:
            logger.warning("FinBERT unavailable — PyTorch not installed")
            return

        self._setup_device(device)
        self._load_model()

    def _setup_device(self, device: Optional[str]):
        if device:
            self.device = torch.device(device)
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info("FinBERT using GPU: %s (%.1f GB VRAM)", gpu_name, vram_gb)
        else:
            self.device = torch.device("cpu")
            logger.warning("CUDA not available — FinBERT running on CPU (slower)")

    def _load_model(self):
        try:
            logger.info("Loading FinBERT model from HuggingFace...")
            self._tokenizer = BertTokenizer.from_pretrained(FINBERT_MODEL)
            self._model = BertForSequenceClassification.from_pretrained(FINBERT_MODEL)
            self._model = self._model.to(self.device)
            self._model.eval()  # inference mode
            self.ready = True
            logger.info("FinBERT loaded successfully on %s", self.device)
        except Exception as exc:
            logger.error("Failed to load FinBERT: %s — falling back to VADER", exc)
            self.ready = False

    def analyze(self, text: str) -> Optional[FinBERTResult]:
        """Analyze a single text. Returns None if model not ready."""
        if not self.ready:
            return None
        results = self.analyze_batch([text])
        return results[0] if results else None

    def analyze_batch(self, texts: list[str]) -> list[FinBERTResult]:
        """Analyze a batch of texts efficiently on GPU.

        Processes in chunks of BATCH_SIZE to avoid OOM on very large inputs.
        """
        if not self.ready or not texts:
            return []

        all_results = []
        for i in range(0, len(texts), BATCH_SIZE):
            chunk = texts[i : i + BATCH_SIZE]
            all_results.extend(self._run_inference(chunk))
        return all_results

    def _run_inference(self, texts: list[str]) -> list[FinBERTResult]:
        """Run a single batch through the model."""
        try:
            inputs = self._tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=MAX_TOKENS,
                return_tensors="pt",
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model(**inputs)

            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
            probs_cpu = probs.cpu().numpy()

            results = []
            for j, text in enumerate(texts):
                pos_p = float(probs_cpu[j][0])
                neg_p = float(probs_cpu[j][1])
                neu_p = float(probs_cpu[j][2])

                winning_idx = int(probs_cpu[j].argmax())
                label = LABEL_MAP[winning_idx]
                confidence = float(probs_cpu[j][winning_idx])

                # Compound score: positive - negative (weighted by confidence)
                score = (pos_p - neg_p)

                results.append(
                    FinBERTResult(
                        text=text[:200],
                        label=label,
                        score=round(score, 4),
                        confidence=round(confidence, 4),
                        positive_prob=round(pos_p, 4),
                        negative_prob=round(neg_p, 4),
                        neutral_prob=round(neu_p, 4),
                    )
                )
            return results

        except Exception as exc:
            logger.error("FinBERT inference error: %s", exc)
            return []

    def score_articles(self, articles: list[dict]) -> tuple[float, int]:
        """Score a list of news article dicts. Returns (avg_score, count)."""
        if not articles:
            return 0.0, 0

        texts = [
            f"{a.get('title', '')}. {a.get('summary', '')}" for a in articles
        ]
        results = self.analyze_batch(texts)
        if not results:
            return 0.0, 0

        avg = sum(r.score for r in results) / len(results)
        return round(avg, 4), len(results)

    def score_texts(self, texts: list[str]) -> tuple[float, int]:
        """Score a list of raw text strings. Returns (avg_score, count)."""
        if not texts:
            return 0.0, 0
        results = self.analyze_batch(texts)
        if not results:
            return 0.0, 0
        avg = sum(r.score for r in results) / len(results)
        return round(avg, 4), len(results)

    @property
    def device_name(self) -> str:
        if not HAS_TORCH:
            return "N/A (PyTorch missing)"
        if self.device and self.device.type == "cuda":
            return torch.cuda.get_device_name(0)
        return "CPU"

    @property
    def cuda_version(self) -> Optional[str]:
        if HAS_TORCH and torch.cuda.is_available():
            return torch.version.cuda
        return None


# Singleton — loaded once at startup
_instance: Optional[FinBERTAnalyzer] = None


def get_finbert() -> FinBERTAnalyzer:
    """Get or create the global FinBERT instance."""
    global _instance
    if _instance is None:
        _instance = FinBERTAnalyzer()
    return _instance
