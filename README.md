# SAAF | سَعَف

SAAF is an Arabic-first AI platform for date palm residue management, evidence-grounded biochar recommendations, collection planning, environmental impact assessment, and palm monitoring.

SAAF supports Arabic scientific retrieval, simulated farm profiles, recommendations, LangGraph routing, simulated collection requests, and impact reporting. Phase 6 requires owner approval.

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

Configure the embedding provider and credentials as described below. Use `SAAF_CHROMA_DIR` to override `var/chroma`.

```sh
python -m saaf.knowledge ingest
python -m saaf.knowledge search "ما أثر الفحم الحيوي على تبخر الماء من التربة؟" --top-k 3
python -m saaf.knowledge evaluate --top-k 3 --min-score 0.35
```

One vector represents each complete Arabic record. The corpus digest, embedding provider, embedding model, and index format identify a collection. A change selects a separate collection and rebuilds it on first use. Switching back reuses the earlier matching collection. Chat model changes use the existing vector index. Older collections occupy local disk until explicitly removed. Results include cosine similarity, the original record with its scientific metadata, and the resolved source. An optional `--topic` filters by the exact Arabic topic. Blank queries or queries with no hit above the cutoff return `insufficient_evidence`.

The benchmark covers 10 evidence-seeking questions and three negatives, including a topically similar question about measured farm irrigation savings. It reports case accuracy, positive hit rate and mean reciprocal rank at k, negative rejection rate, and per-query IDs and scores. A positive passes when its expected record is returned. A negative passes when no hits survive. Fixture embeddings deliberately encode the expected labels to verify benchmark and retrieval mechanics. Live evaluation requires credentials. The default cosine cutoff of 0.35 is provisional. Semantically related records can score highly even when they cannot answer a question.

## Arabic recommendation agent

Copy [.env.example](.env.example) to `.env` in the repository root and supply the selected provider's key. The AI CLIs load that file, and exported environment variables take precedence. Set `SAAF_CHAT_PROVIDER` and `SAAF_EMBEDDING_PROVIDER` independently to `openai` or `gemini`. Set `SAAF_CHAT_MODEL` and `SAAF_EMBEDDING_MODEL` to override the selected defaults. Chat model overrides must support structured output.

| Provider | Credential | Default chat | Default embeddings |
| --- | --- | --- | --- |
| OpenAI | `OPENAI_API_KEY` | `gpt-4.1-mini` | `text-embedding-3-small` |
| Gemini Developer API | `GOOGLE_API_KEY` or `GEMINI_API_KEY` | `gemini-3.1-flash-lite` | `gemini-embedding-001` |

For Gemini, set both provider fields to `gemini` and leave both model fields blank to use the defaults. The opt-in live test always uses the listed Gemini models, which Google offers on its free tier, subject to project quota. [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)

Seed the farm database before using a farm ID in the CLI.

```sh
python -m saaf.farms seed
python -m saaf.agents "وش أراعي قبل أحط فحم حيوي في تربتي؟" --farm-id SIM-002
python -m saaf.agents "ما الجرعة المرجعية للتربة الرملية؟"
python -m pytest -q tests/live_recommendation.py
```

The agent runs a bounded sequence of typed, read-only farm lookup, soil assessment, and scientific search. LangChain passes the question, relevant farm attributes, retrieved records, and corpus rules to the configured chat provider. The model classifies the question and selects record IDs. The agent validates those IDs and renders Arabic evidence and recommendations using the original record text, citations, caveats, and fixed guidance. Output statuses are `ok`, `needs_input`, `insufficient_evidence`, and `unavailable`. `simulated_data` is true when a simulated profile was used and null when no profile was used.

The offline suite runs Arabic and Saudi dialect scenarios with controlled model decisions. Live model interpretation and retrieval relevance still depend on the configured models and corpus coverage. The agent uses soil sand percentage as context and does not infer a complete texture class from it. It applies pH and salinity cautions and gives no field prescription or numerical irrigation savings forecast.

## Orchestration

```sh
python -m saaf.orchestration "وش أراعي قبل أحط فحم حيوي؟" --farm-id SIM-002
python -m saaf.orchestration
python -m saaf.orchestration --evaluate-routing
python -m pytest -q tests/live_orchestration.py
```

The interactive CLI keeps the active farm and last supported request in memory. Use `/farm ID` to select a farm for the next turn, `/reset` to clear context, and `/exit` to quit. An inline `SIM-NNN` also supplies the farm ID. A switch to another farm clears the previous question. Conflicting IDs and multi-intent requests ask for clarification.

Routing uses normalized Arabic phrases and selected Saudi expressions. Recommendation uses the configured providers. Impact can use the chat provider to select an explanation of computed results and falls back to a deterministic Arabic explanation. Monitoring returns `not_implemented`. The routing benchmark measures intent and candidate matching on the labeled examples. The explicit live test is excluded from the default suite.

### Simulated collection

Seed farms and open `python -m saaf.orchestration` for multi-turn confirmation.

1. Enter `أبغى طلب جمع للسعف`, then supply a farm ID such as `SIM-001`.
2. Enter the requested pickup amount, for example `٣٠٠ كجم`. The annual waste estimate appears separately. Quantities use positive whole kilograms.
3. Review the simulated date and quantity. Enter `أؤكد` to save or `إلغاء المسودة` to discard. Use `طلباتي` or `تتبع الطلب COL-…` to retrieve requests for the active farm. To cancel a saved request, enter `إلغاء الطلب COL-…` with its full ID.

Demo pickups use the next future Monday, Wednesday, or Saturday in Riyadh time. No carrier or dispatch service is connected. Drafts are session state. Confirmed and cancelled requests persist in SQLite. An identical farm, date, and quantity resolves to the existing record, including after cancellation.

### Impact reporting

Ask `وش إجمالي الطلبات حسب المنطقة؟` for the registry and request breakdown, or `كم الكمية المؤكدة في القصيم؟` for a regional report. Reports distinguish estimated annual waste from user-entered quantities on confirmed demo requests. A confirmation represents a recorded request and carries no field fulfillment data.

Requests such as `كم الانبعاثات المتجنبة؟` return `insufficient_data` with the required measurements and factors. The current datasets supply no validated inputs for biochar production, stored carbon, avoided emissions, or measured irrigation savings.
