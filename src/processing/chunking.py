from pathlib import Path
from datetime import datetime, timezone
import hashlib

import pandas as pd
from chonkie import Pipeline


PROJECT_ROOT = Path("/Users/andreasp/personal-projects/RAG_App for Policy Eval")

BRONZE_DIR = PROJECT_ROOT / "data" / "bronze" / "parsed_markdown"
SILVER_DIR = PROJECT_ROOT / "data" / "silver"
CHUNKS_PATH = SILVER_DIR / "chunks.parquet"


pipe = (
    Pipeline()
    .chunk_with("recursive", tokenizer="gpt2", chunk_size=1000, recipe="markdown")
    .refine_with("overlap", context_size=2000)
    .refine_with(
        "embeddings",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    )
)


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_markdown_file(md_file: Path) -> list[dict]:
    text = md_file.read_text(encoding="utf-8")
    doc = pipe.run(texts=text)

    source_doc_id = hash_text(str(md_file.name))

    rows = []
    for i, chunk in enumerate(doc.chunks):
        chunk_id = hash_text(f"{source_doc_id}:{i}:{chunk.text}")

        rows.append(
            {
                "chunk_id": chunk_id,
                "source_doc_id": source_doc_id,
                "source_file": md_file.name,
                "chunk_index": i,
                "text": chunk.text,
                "text_hash": hash_text(chunk.text),
                "chunking_strategy": "recursive_markdown_overlap",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    return rows


def build_chunks_table() -> None:
    SILVER_DIR.mkdir(parents=True, exist_ok=True)

    md_files = list(BRONZE_DIR.glob("*.md"))

    all_rows = []
    for md_file in md_files:
        rows = chunk_markdown_file(md_file)
        all_rows.extend(rows)
        print(f"Chunked {md_file.name}: {len(rows)} chunks")

    df = pd.DataFrame(all_rows)

    if df.empty:
        print("No markdown files found.")
        return

    df = df.drop_duplicates(subset=["chunk_id"])
    df.to_parquet(CHUNKS_PATH, index=False)

    print(f"Saved {len(df)} chunks to {CHUNKS_PATH}")


if __name__ == "__main__":
    build_chunks_table()