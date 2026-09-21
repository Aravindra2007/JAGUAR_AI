"""
Jaguar AI — Memory System.

Two-tier memory:
  - Short-term: the rolling chat window (already lives in state.py).
  - Long-term : persistent semantic memory. Embeds every exchange and
                any user preference, then lets the agent recall the
                most relevant prior context for new queries ("do like
                last time").

Vector backend is pluggable:
  - FAISS (faiss-cpu) when available — fast, local, no server.
  - Chroma (chromadb) when available — persistent client/server.
  - Plain in-memory cosine similarity fallback when neither is
    installed, so the rest of the system keeps working.

Embeddings come from sentence-transformers if available, otherwise we
fall back to a hashed bag-of-words vector. The fallback is much worse
semantically but still allows recall to function.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------
# Storage paths
# ---------------------------------------------------------------

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "jaguar_data",
)
os.makedirs(_DATA_DIR, exist_ok=True)

_SQLITE_PATH = os.path.join(_DATA_DIR, "memory.sqlite3")
_FAISS_PATH = os.path.join(_DATA_DIR, "faiss.index")
_FAISS_META = os.path.join(_DATA_DIR, "faiss_meta.json")
_CHROMA_DIR = os.path.join(_DATA_DIR, "chroma")
_PREFERENCES_PATH = os.path.join(_DATA_DIR, "preferences.json")


# ---------------------------------------------------------------
# Embedding backends
# ---------------------------------------------------------------

_EMBEDDING_MODEL = None
_EMBEDDING_DIM: Optional[int] = None
_EMBED_LOCK = threading.Lock()


def _load_sentence_transformer():
    """Try to load sentence-transformers once. Returns (model, dim)
    or (None, None) if it isn't installed."""
    global _EMBEDDING_MODEL, _EMBEDDING_DIM
    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL, _EMBEDDING_DIM or 384
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        _EMBEDDING_MODEL = model
        _EMBEDDING_DIM = 384
        return model, 384
    except Exception:
        return None, None


def _hash_embed(text: str, dim: int = 384) -> List[float]:
    """Deterministic hashed bag-of-words embedding. Cosine similarity
    over this is meaningfully better than nothing for recall."""
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    if not tokens:
        return [0.0] * dim
    vec = [0.0] * dim
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    # l2-normalise so cosine similarity == dot product
    norm = math.sqrt(sum(v * v for v in vec))
    if norm:
        vec = [v / norm for v in vec]
    return vec


def embed(text: str) -> List[float]:
    """Return a single embedding vector for `text`."""
    if not text:
        return [0.0] * 384
    model, dim = _load_sentence_transformer()
    if model is not None:
        with _EMBED_LOCK:
            try:
                vec = model.encode([text], normalize_embeddings=True)[0]
                return [float(x) for x in vec]
            except Exception:
                pass
    return _hash_embed(text, dim=dim or 384)


# ---------------------------------------------------------------
# Vector index wrapper
# ---------------------------------------------------------------

class _VectorIndex:
    """Pluggable vector index. Uses FAISS > Chroma > in-memory, in
    that order, based on what's installed."""

    def __init__(self):
        self.backend = "memory"
        self.dim: Optional[int] = None
        self._vectors: List[List[float]] = []
        self._faiss = None
        self._chroma = None
        self._chroma_collection = None
        self._init_backend()

    def _init_backend(self):
        # Try FAISS first
        try:
            import faiss  # type: ignore
            import numpy as np  # type: ignore

            if os.path.exists(_FAISS_PATH):
                try:
                    self._faiss = faiss.read_index(_FAISS_PATH)
                except Exception:
                    self._faiss = None
            if self._faiss is not None:
                self.backend = "faiss"
                self.dim = self._faiss.d
                return
        except Exception:
            self._faiss = None

        # Then Chroma
        try:
            import chromadb  # type: ignore
            self._chroma = chromadb.PersistentClient(path=_CHROMA_DIR)
            self._chroma_collection = self._chroma.get_or_create_collection(
                name="jaguar_memory",
                metadata={"hnsw:space": "cosine"},
            )
            self.backend = "chroma"
            self.dim = 384
            return
        except Exception:
            self._chroma = None
            self._chroma_collection = None

        # Fall back to in-memory
        self.backend = "memory"
        self.dim = 384

    def add(self, ids: List[str], vectors: List[List[float]],
            documents: List[str], metadatas: List[Dict[str, Any]]):
        if not ids:
            return
        if self.backend == "faiss" and self._faiss is not None:
            import numpy as np
            arr = np.array(vectors, dtype="float32")
            if self._faiss is None or self._faiss.ntotal == 0:
                self._faiss = None
            if self._faiss is None:
                d = arr.shape[1]
                self._faiss = faiss.IndexFlatIP(d)
                self.dim = d
            # FAISS expects normalised vectors for cosine via inner product
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            arr = arr / norms
            self._faiss.add(arr)
            try:
                import faiss as _faiss_mod
                _faiss_mod.write_index(self._faiss, _FAISS_PATH)
            except Exception:
                pass
            _append_faiss_meta(ids, documents, metadatas)
            return

        if self.backend == "chroma" and self._chroma_collection is not None:
            try:
                self._chroma_collection.add(
                    ids=ids,
                    embeddings=[list(map(float, v)) for v in vectors],
                    documents=documents,
                    metadatas=[json_safe_meta(m) for m in metadatas],
                )
            except Exception:
                pass
            return

        # In-memory fallback
        for i, v in enumerate(vectors):
            self._vectors.append(v)
            _append_memory_record(ids[i], documents[i], metadatas[i])

    def query(self, vector: List[float], top_k: int = 5) -> List[Tuple[str, float, str, Dict[str, Any]]]:
        """Return list of (id, score, document, metadata) tuples."""
        if not vector:
            return []
        if self.backend == "faiss" and self._faiss is not None and self._faiss.ntotal > 0:
            import numpy as np
            arr = np.array([vector], dtype="float32")
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            arr = arr / norms
            k = min(top_k, self._faiss.ntotal)
            scores, idxs = self._faiss.search(arr, k)
            results = []
            meta = _read_faiss_meta()
            for s, i in zip(scores[0].tolist(), idxs[0].tolist()):
                if i < 0 or i >= len(meta):
                    continue
                m = meta[i]
                results.append((m["id"], float(s), m["document"], m["metadata"]))
            return results

        if self.backend == "chroma" and self._chroma_collection is not None:
            try:
                res = self._chroma_collection.query(
                    query_embeddings=[list(map(float, vector))],
                    n_results=top_k,
                )
                out: List[Tuple[str, float, str, Dict[str, Any]]] = []
                ids = (res.get("ids") or [[]])[0]
                docs = (res.get("documents") or [[]])[0]
                metas = (res.get("metadatas") or [[]])[0]
                dists = (res.get("distances") or [[]])[0]
                for i, d in enumerate(ids):
                    score = 1.0 - float(dists[i]) if i < len(dists) else 0.0
                    doc = docs[i] if i < len(docs) else ""
                    meta = metas[i] if i < len(metas) else {}
                    out.append((d, score, doc, meta))
                return out
            except Exception:
                return []

        # In-memory cosine
        if not self._vectors:
            return []
        scores = []
        for i, v in enumerate(self._vectors):
            s = _cosine(vector, v)
            scores.append((i, s))
        scores.sort(key=lambda t: t[1], reverse=True)
        records = _read_memory_records()
        results = []
        for i, s in scores[:top_k]:
            if i < len(records):
                rec = records[i]
                results.append((rec["id"], s, rec["document"], rec["metadata"]))
        return results


def json_safe_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Chroma's metadata store only supports primitives. Flatten
    nested dicts and stringify anything exotic."""
    out: Dict[str, Any] = {}
    for k, v in (meta or {}).items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        else:
            out[k] = json.dumps(v, default=str)
    return out


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    sa = sum(x * x for x in a[:n]) ** 0.5
    sb = sum(x * x for x in b[:n]) ** 0.5
    if not sa or not sb:
        return 0.0
    return sum(a[i] * b[i] for i in range(n)) / (sa * sb)


def _append_faiss_meta(ids: List[str], documents: List[str], metadatas: List[Dict[str, Any]]):
    meta = _read_faiss_meta()
    for i, d, m in zip(ids, documents, metadatas):
        meta.append({"id": i, "document": d, "metadata": json_safe_meta(m)})
    with open(_FAISS_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _read_faiss_meta() -> List[Dict[str, Any]]:
    if not os.path.exists(_FAISS_META):
        return []
    try:
        with open(_FAISS_META, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _append_memory_record(_id: str, document: str, metadata: Dict[str, Any]):
    rec = {"id": _id, "document": document, "metadata": json_safe_meta(metadata)}
    path = os.path.join(_DATA_DIR, "memory_records.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _read_memory_records() -> List[Dict[str, Any]]:
    path = os.path.join(_DATA_DIR, "memory_records.jsonl")
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


# ---------------------------------------------------------------
# Long-term memory
# ---------------------------------------------------------------

_VECTOR_SINGLETON: Optional[_VectorIndex] = None
_VEC_LOCK = threading.Lock()


def _index() -> _VectorIndex:
    global _VECTOR_SINGLETON
    with _VEC_LOCK:
        if _VECTOR_SINGLETON is None:
            _VECTOR_SINGLETON = _VectorIndex()
        return _VECTOR_SINGLETON


@dataclass
class MemoryEntry:
    id: str
    text: str
    kind: str            # "chat", "preference", "task_result", "job_application"
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "kind": self.kind,
            "score": self.score,
            "metadata": self.metadata,
        }


def _short_id() -> str:
    return f"mem_{int(time.time() * 1000)}_{hashlib.md5(os.urandom(8)).hexdigest()[:8]}"


def remember(text: str, kind: str = "chat", metadata: Optional[Dict[str, Any]] = None) -> str:
    """Store `text` in long-term memory. Returns the new entry's id."""
    if not text or not text.strip():
        return ""
    text = text.strip()
    vec = embed(text)
    entry_id = _short_id()
    idx = _index()
    idx.add(
        ids=[entry_id],
        vectors=[vec],
        documents=[text],
        metadatas=[{"kind": kind, **(metadata or {})}],
    )
    return entry_id


def recall(query: str, top_k: int = 5, kind: Optional[str] = None) -> List[MemoryEntry]:
    """Semantic recall over long-term memory."""
    if not query or not query.strip():
        return []
    vec = embed(query)
    idx = _index()
    raw = idx.query(vec, top_k=top_k * 2)  # over-fetch so we can filter
    out: List[MemoryEntry] = []
    for entry_id, score, doc, meta in raw:
        if kind and meta.get("kind") != kind:
            continue
        out.append(MemoryEntry(
            id=entry_id, text=doc, kind=str(meta.get("kind", "chat")),
            score=float(score), metadata=meta,
        ))
        if len(out) >= top_k:
            break
    return out


def recall_context_block(query: str, top_k: int = 4) -> str:
    """Return a plain-text block of the most relevant memories, ready
    to paste into an LLM prompt as extra context."""
    entries = recall(query, top_k=top_k)
    if not entries:
        return ""
    lines = ["Relevant things I remember about this:"]
    for e in entries:
        lines.append(f"- ({e.kind}) {e.text}")
    return "\n".join(lines)


# ---------------------------------------------------------------
# User preferences
# ---------------------------------------------------------------

DEFAULT_PREFERENCES = {
    "tone": "friendly",          # friendly | professional | casual
    "language": "English",
    "name": "",
    "interests": [],
    "communication_style": "concise",   # concise | detailed
    "default_search_engine": "google",
    "wake_word": "hey jaguar",
}


def _load_preferences() -> Dict[str, Any]:
    if not os.path.exists(_PREFERENCES_PATH):
        return dict(DEFAULT_PREFERENCES)
    try:
        with open(_PREFERENCES_PATH, "r", encoding="utf-8") as f:
            stored = json.load(f)
        merged = dict(DEFAULT_PREFERENCES)
        merged.update({k: v for k, v in stored.items() if v is not None})
        return merged
    except Exception:
        return dict(DEFAULT_PREFERENCES)


def _save_preferences(prefs: Dict[str, Any]) -> None:
    with open(_PREFERENCES_PATH, "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)


def get_preferences() -> Dict[str, Any]:
    return _load_preferences()


def update_preference(key: str, value: Any) -> Dict[str, Any]:
    """Update one preference and persist."""
    prefs = _load_preferences()
    prefs[key] = value
    _save_preferences(prefs)
    remember(
        f"User preference: {key} = {value}",
        kind="preference",
        metadata={"preference_key": key},
    )
    return prefs


# ---------------------------------------------------------------
# MySQL-backed job application log
# ---------------------------------------------------------------

def init_results_db():
    """Create the long-term task-results table if it doesn't exist."""
    with sqlite3.connect(_SQLITE_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                kind TEXT NOT NULL,
                title TEXT,
                detail TEXT,
                status TEXT
            )
        """)
        conn.commit()


def log_result(kind: str, title: str, detail: str = "", status: str = "ok"):
    init_results_db()
    with sqlite3.connect(_SQLITE_PATH) as conn:
        conn.execute(
            "INSERT INTO task_results(created_at, kind, title, detail, status) VALUES (?, ?, ?, ?, ?)",
            (time.time(), kind, title, detail, status),
        )
        conn.commit()
    remember(
        f"{kind}: {title} — {detail}",
        kind="task_result",
        metadata={"result_kind": kind, "status": status},
    )


def list_results(kind: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    init_results_db()
    with sqlite3.connect(_SQLITE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if kind:
            cur.execute(
                "SELECT * FROM task_results WHERE kind = ? ORDER BY created_at DESC LIMIT ?",
                (kind, limit),
            )
        else:
            cur.execute(
                "SELECT * FROM task_results ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------
# Periodic chat ingestion helper
# ---------------------------------------------------------------

def ingest_chat_turn(user_text: str, assistant_text: str) -> None:
    """Called after every finished exchange so both halves of the
    conversation land in long-term memory."""
    if user_text:
        remember(f"User said: {user_text}", kind="chat",
                 metadata={"role": "user"})
    if assistant_text:
        remember(f"Jaguar replied: {assistant_text}", kind="chat",
                 metadata={"role": "assistant"})


# Eager init so first recall isn't slow
init_results_db()
