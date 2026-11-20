import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from saaf.knowledge.corpus import load_corpus
from saaf.knowledge.evaluation import CASES, evaluate
from saaf.knowledge.retrieval import EmbeddingUnavailable, KnowledgeIndex

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "saaf_knowledge_base.json"


class FixtureEmbeddings:
    """One-hot vectors with deliberately preassigned case labels."""

    def __init__(self):
        corpus, _ = load_corpus(CORPUS)
        self.records = {record.text_ar: i for i, record in enumerate(corpus.records)}
        self.ids = {record.id: i for i, record in enumerate(corpus.records)}
        self.labels = dict(CASES)
        self.batches = []
        self.queries = []

    def vector(self, index):
        return [float(i == index) for i in range(len(self.records) + 1)]

    def embed_documents(self, texts):
        self.batches.append(texts)
        return [self.vector(self.records[text]) for text in texts]

    def embed_query(self, text):
        self.queries.append(text)
        ids = self.labels.get(text, ())
        return self.vector(self.ids[ids[0]] if ids else len(self.records))


@pytest.fixture
def setup_index(tmp_path):
    embeddings = FixtureEmbeddings()
    path = tmp_path / "chroma"
    return KnowledgeIndex(CORPUS, path, embeddings), path, embeddings


def test_lossless_corpus_and_source_resolution():
    corpus, _ = load_corpus(CORPUS)
    original = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert len(corpus.records) == 14
    assert corpus.model_dump(exclude_unset=True) == original
    for record in corpus.records:
        assert corpus.sources[record.source_id].url == original["sources"][record.source_id]["url"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [("id", "bc-01", "duplicate record ID"), ("id", "bad id", "pattern"),
     ("source_id", "MISSING", "unknown source"), ("text_ar", "  ", "pattern"),
     ("conditions", [], "dictionary")],
)
def test_invalid_records(tmp_path, field, value, message):
    original = json.loads(CORPUS.read_text(encoding="utf-8"))
    original["records"][0][field] = value
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_corpus(path)


def test_duplicate_json_key(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"sources": {}, "sources": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_corpus(path)


def test_idempotent_ingestion_and_persistence(setup_index):
    index, path, embeddings = setup_index
    assert index.ingest() == 14
    assert index.ingest() == 0
    assert embeddings.batches == [[record.text_ar for record in index.corpus.records]]
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    script = (
        "import sys; from pathlib import Path; "
        "from saaf.knowledge.retrieval import KnowledgeIndex; "
        "index = KnowledgeIndex(Path(sys.argv[1]), Path(sys.argv[2]), None); "
        "assert index.ingest() == 0; assert index.collection.count() == 14"
    )
    subprocess.run([sys.executable, "-c", script, str(CORPUS), str(path)],
                   env=env, check=True, timeout=30)


def test_changed_snapshot_and_model_create_separate_indexes(setup_index, tmp_path):
    index, path, embeddings = setup_index
    index.ingest()
    original = json.loads(CORPUS.read_text(encoding="utf-8"))
    removed_id = original["records"].pop()["id"]
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(original), encoding="utf-8")
    rebuilt = KnowledgeIndex(changed, path, embeddings)
    assert rebuilt.name != index.name
    assert rebuilt.ingest() == 13
    assert removed_id not in rebuilt.collection.get(include=[])["ids"]
    assert index.collection.count() == 14
    assert KnowledgeIndex(changed, path, embeddings, model="other").name != rebuilt.name


def test_retrieval_scores_full_evidence_top_k_and_filters(setup_index):
    index, _, embeddings = setup_index
    index.ingest()
    result = index.search(CASES[0][0], top_k=1, topic="الاحتفاظ بالماء")
    assert result.status == "ok"
    hit, = result.hits
    assert hit.record.id == "bc-02"
    assert hit.record.conditions["setting"] == "مختبر"
    assert hit.record.caveat_ar
    assert hit.record.values["fc_increase_pct_at_2pct"] == 6.64
    assert hit.source == index.corpus.sources["ALKHASHA2018"]
    assert hit.score == pytest.approx(1)
    assert len(index.search(CASES[0][0], top_k=2, min_score=-1).hits) == 2
    assert index.search(CASES[0][0], topic="مجهول").reason == "no_relevant_hits"
    assert index.search(" ").reason == "empty_query"
    assert " " not in embeddings.queries


def test_empty_index_and_embedding_failure(setup_index, monkeypatch):
    index, _, embeddings = setup_index
    assert index.search("سؤال").reason == "no_relevant_hits"

    def fail(_):
        raise OSError("offline")

    with monkeypatch.context() as patch:
        patch.setattr(embeddings, "embed_documents", fail)
        with pytest.raises(EmbeddingUnavailable):
            index.ingest()
        assert index.collection.count() == 0
    index.ingest()
    monkeypatch.setattr(embeddings, "embed_query", fail)
    with pytest.raises(EmbeddingUnavailable):
        index.search("سؤال")


def test_arabic_benchmark_pipeline_with_fixture_vectors(setup_index):
    index, _, _ = setup_index
    index.ingest()
    report = evaluate(index, top_k=3, min_score=0.35)
    assert len(report["cases"]) == 13
    assert report["accuracy"] == report["positive_hit_rate_at_k"] == 1
    assert report["positive_mrr_at_k"] == report["negative_rejection_rate"] == 1
