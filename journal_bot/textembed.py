"""Robuster Text-Embedding-Zugang (MiniLM), ohne DOI, lokal, kostenfrei.

Warum eigen und nicht direkt `sentence_transformers`: in der Projektumgebung ist
`torchvision` gegen `torch` versionsschief (`operator torchvision::nms does not
exist`), und `transformers` zieht den Vision-Pfad beim Import eager mit. Das legt
JEDES `SentenceTransformer(...)` lahm — auch den bestehenden Ranker. Wir sperren
`torchvision` vor dem Import hart aus; der reine Text-Pfad (BERT) lädt dann
sauber. Reine Umgehung, kein Eingriff in die Installation.

Das Modell ist dasselbe wie im Ranker (`all-MiniLM-L6-v2`), damit Publikations-
und Artikel-Embeddings im selben Raum liegen. Wichtig fürs Filtern: MiniLM
braucht nur Titel + Abstract, KEIN DOI — also erreicht es genau die
Kernzeitschriften (Computational Culture, MedienPädagogik, …), an denen die
OpenAlex-Anreicherung leer bleibt.
"""

from __future__ import annotations

import os
import sys

import numpy as np

# Sonst warnt (und deadlockt potenziell) der HF-Tokenizer beim Fork nach einem
# Encode — relevant, seit das Screening im Digest-Lauf einbettet. Nur setzen,
# wenn der Nutzer nichts vorgegeben hat.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

MODEL_NAME = "all-MiniLM-L6-v2"
_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        # torchvision aussperren, BEVOR transformers es (kaputt) importiert.
        if "torchvision" not in sys.modules:
            sys.modules["torchvision"] = None  # type: ignore[assignment]
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(MODEL_NAME)
    return _MODEL


def encode(texts: list[str], *, normed: bool = True) -> np.ndarray:
    """Texte einbetten; standardmässig L2-normiert (dann ist Skalarprodukt = Kosinus)."""
    m = _get_model()
    v = np.asarray(m.encode(texts, show_progress_bar=False, batch_size=64),
                   dtype="float32")
    if normed:
        v /= (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)
    return v
