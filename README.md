# SAAF | سَعَف

SAAF is an Arabic-first AI platform for date palm residue management, evidence-grounded biochar recommendations, collection planning, environmental impact assessment, and palm monitoring.

Phase 1 provides scientific evidence ingestion, Arabic semantic search, and a retrieval benchmark. Phase 2 adds a SQLite repository for simulated farm profiles. Phase 3 requires owner approval.

| Input | Intended use |
| --- | --- |
| [Knowledge base](data/saaf_knowledge_base.json) | Curated Arabic evidence for cited answers, with study conditions and caveats |
| [Simulated farms](data/saaf_simulated_farms.json) | Demo profiles and test fixtures, labeled simulated in every output derived from them |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the dataset audit and interfaces, [ROADMAP.md](ROADMAP.md) for phase gates, and [AGENTS.md](AGENTS.md) for repository instructions.

## Install and test

From the repository root, use Python 3.11 or newer in an activated virtual environment.

```sh
python -m pip install -e ".[test]"
python -m pytest -q
```

Offline tests use temporary SQLite and ChromaDB databases and deterministic fixture embeddings. They make no paid API calls.

## Simulated farm database

Run from the repository root. The repository creates the database and schema on first use. The default path is `var/saaf.sqlite3`. Set `SAAF_SQLITE_PATH` or pass `--db` to use a different path. Seeding requires no API credentials.

```sh
python -m saaf.farms seed
```

```python
from saaf.farms import FarmRepository, get_farm_profile

repository = FarmRepository()
profile = get_farm_profile(repository, "SIM-001")  # FarmProfile | None
farms = repository.list_farms(region="الأحساء")
stats = repository.statistics(region="الأحساء")
```

The `farms` table uses `farm_id` as its primary key and indexes `region`. It stores coordinates, area in hectares, palm count, estimated residue in kg/year, soil sand percentage and pH, irrigation system and salinity flag, disposal method, the simulation flag, and provenance. Profiles identify seed rows, locally edited seed rows, and local simulations. A missing farm ID returns `None`. Nullable soil, irrigation, and disposal fields represent unknowns in local profiles. The importer requires complete fixture rows.

Use `create_farm(Farm(...))`, `get_farm(farm_id)`, `update_farm(farm_id, **changes)`, and `delete_farm(farm_id)` for local data management. Duplicate creates raise `FarmAlreadyExists`. Seeding inserts missing IDs in one transaction and preserves existing rows and local edits. Reseeding restores a deleted fixture row. Palm count changes recalculate estimated residue using the fixture's 35 kg per palm per year factor, attributed to `NASSER2016` via knowledge record `ctx-02`. Region filtering uses exact names. Statistics report count and total area, palm count, and estimated annual residue, all labeled simulated. The database accepts simulated profiles only.

## Live retrieval

Set `OPENAI_API_KEY` in the shell environment before running these commands. The CLI reads environment variables directly. [.env.example](.env.example) lists the settings. Use `SAAF_EMBEDDING_MODEL` to override `text-embedding-3-small`, or `SAAF_CHROMA_DIR` to override `var/chroma`.

```sh
python -m saaf.knowledge ingest
python -m saaf.knowledge search "ما أثر الفحم الحيوي على تبخر الماء من التربة؟" --top-k 3
python -m saaf.knowledge evaluate --top-k 3 --min-score 0.35
```

One vector represents each complete Arabic record. The corpus digest, embedding model, and index format version identify a collection. Repeated ingestion skips existing IDs. A source or model change selects a new collection and rebuilds on the next invocation. Older collections occupy local disk until explicitly removed. Results include cosine similarity, the original record with its scientific metadata, and the resolved source. An optional `--topic` filters by the exact Arabic topic. Blank queries or queries with no hit above the cutoff return `insufficient_evidence`.

The benchmark covers 10 evidence-seeking questions and three negatives, including a topically similar question about measured farm irrigation savings. It reports case accuracy, positive hit rate and mean reciprocal rank at k, negative rejection rate, and per-query IDs and scores. A positive passes when its expected record is returned. A negative passes when no hits survive. Fixture embeddings deliberately encode the expected labels to verify benchmark and retrieval mechanics. Live evaluation requires credentials. The default cosine cutoff of 0.35 is provisional. Semantically related records can score highly even when they cannot answer a question.
