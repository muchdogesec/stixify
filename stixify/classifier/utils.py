import os
from typing import List

import openai


from .models import DocumentEmbedding


class ClusteringCancelled(Exception):
    pass


def _openai_client():
    openai.api_key = os.getenv("OPENAI_API_KEY")
    return openai.Client()


def compute_embedding_for_document(doc: DocumentEmbedding):
    """Fetch a document by id, compute embedding using OpenAI small-3."""
    if not doc.text:
        raise ValueError("Document text is empty, cannot compute embedding")

    client = _openai_client()
    try:
        resp = client.embeddings.create(
            input=doc.text, model="text-embedding-3-small", dimensions=512
        )
        vec = resp.data[0].embedding  # list of floats
        # store as list of floats; `updated_at` is auto-updated by the model
        doc.embedding = vec
        doc.save(update_fields=["embedding", "updated_at"])
        print(f"Saved embedding for doc {doc.pk}")
    except Exception as e:
        print(f"Embedding failed for {doc.pk}: {e}")
        raise


def create_embedding_text(*texts: List[str]) -> str:
    """Create a single string to embed from multiple text fields."""
    # simple concat with separator, could be improved with field weighting or truncation
    texts = [t.strip() for t in texts if t and t.strip()]
    return " | ".join(texts)