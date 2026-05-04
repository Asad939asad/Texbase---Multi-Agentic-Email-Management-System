"""
vector_store.py
===============
Generates sentence-transformer embeddings for each PO row and stores them
in a ChromaDB persistent collection.

Public API
----------
  get_or_create_collection(chroma_dir, collection_name) -> chromadb.Collection
  embed_and_store(collection, row_id, row_dict, source_pdf, table_name) -> str
    Returns the ChromaDB document ID used.
"""

import uuid
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# ── Model (loaded once, shared across calls) ───────────────────────────────
_model = None

def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print("[VectorStore] Loading SentenceTransformer model (all-MiniLM-L6-v2)…")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[VectorStore] Model loaded.")
    return _model


# ── ChromaDB client ────────────────────────────────────────────────────────

def get_or_create_collection(chroma_dir: str,
                             collection_name: str):
    """
    Return (or create) a persistent ChromaDB collection.

    Parameters
    ----------
    chroma_dir      : absolute path where ChromaDB will persist its data
    collection_name : sanitized table name from db_manager (used as collection name)

    Returns
    -------
    chromadb.Collection
    """
    # Chroma collection names must be 3-63 chars, alphanumeric + hyphens
    safe_name = collection_name[:63].replace("_", "-").strip("-") or "po-collection"

    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection(
        name=safe_name,
        metadata={"hnsw:space": "cosine"},
    )
    print(f"[VectorStore] Collection ready: '{safe_name}' ({collection.count()} existing docs)")
    return collection


# ── Embed + Store ──────────────────────────────────────────────────────────

def _row_to_text(row_dict: dict) -> str:
    """
    Convert a row dict to a flat string suitable for embedding.
    e.g. "product_name: Cotton Fabric | quantity: 500 | unit_price: 3.50"
    Skip internal meta keys (prefixed with __).
    """
    parts = []
    for k, v in row_dict.items():
        if k.startswith("__") or not v:
            continue
        parts.append(f"{k}: {v}")
    return " | ".join(parts)


def embed_and_store(collection,
                    row_id: int,
                    row_dict: dict,
                    source_pdf: str,
                    table_name: str) -> str:
    """
    Embed a single PO row using SentenceTransformer and upsert into ChromaDB.

    Parameters
    ----------
    collection  : ChromaDB collection object
    row_id      : SQLite rowid (used to build a stable document ID)
    row_dict    : the row data dict (column → value)
    source_pdf  : original PDF filename
    table_name  : SQLite table name (for metadata)

    Returns
    -------
    str — the ChromaDB document ID
    """
    model       = _get_model()
    text        = _row_to_text(row_dict)
    doc_id      = f"{table_name}__row_{row_id}"

    if not text.strip():
        # Nothing meaningful to embed
        return doc_id

    embedding = model.encode(text).tolist()

    collection.upsert(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[text],
        metadatas=[{
            "source_pdf": source_pdf,
            "table_name": table_name,
            "row_id":     str(row_id),
        }],
    )
    return doc_id


# ── Similarity Search (bonus utility) ─────────────────────────────────────

def search_similar(collection,
                   query_text: str,
                   n_results: int = 5) -> list:
    """
    Search the vector store for rows semantically similar to query_text.

    Returns
    -------
    list[dict] — each dict has keys: id, document, metadata, distance
    """
    model     = _get_model()
    embedding = model.encode(query_text).tolist()

    results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for i in range(len(results["ids"][0])):
        output.append({
            "id":       results["ids"][0][i],
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return output
