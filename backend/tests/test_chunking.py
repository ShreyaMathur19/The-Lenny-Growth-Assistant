import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("ingest", Path(__file__).parents[1] / "scripts" / "ingest_transcripts.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_chunking_uses_overlap_and_preserves_text():
    text = " ".join(f"word{i}" for i in range(1000))
    chunks = module.chunk_text(text, words_per_chunk=200, overlap=50)
    assert len(chunks) > 1
    assert "word150" in chunks[0]
    assert "word150" in chunks[1]
