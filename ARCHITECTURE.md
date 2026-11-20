# SAAF architecture

## Dataset audit

### Scientific knowledge

`saaf_knowledge_base.json` contains 14 Arabic records, seven source entries, and six agent rules. Its `about` section reports verification on 2026-11-18, describes the official and peer-reviewed sources, gives attribution guidance for CC BY research, and directs retrieval to embed `text_ar` and carry `source_id`, `evidence_level`, and `caveat_ar`. This audit covers the supplied JSON. Source verification and licensing assertions come from its metadata.

- Context records cover a dated official palm and production snapshot, a literature residue estimate based on older work, a qualitative disposal claim, and national agricultural water context. Preserve scope and date where supplied. The structured palm total stores 37 while the Arabic text says “more than 37 million.” Render from the qualified text. The water record has no reference year in the supplied data.
- Biochar records describe research production conditions, laboratory soil columns, greenhouse tomato pots, and calcareous-soil experiments. The 2% weight-based rate is a laboratory-derived reference for sandy soils. The greenhouse inputs and results apply to the stated crop and test conditions. The alkalinity and phosphorus records use Conocarpus biochar. Preserve that feedstock distinction.
- Soil moisture, field capacity, infiltration, conductivity, and evaporation measurements provide no farm irrigation savings factor. The evidence lacks palm field trials, validated farm-specific doses, characterized local biochar batches, and field-scale irrigation or yield outcomes.
- `values`, `conditions`, and `caveat_ar` are optional. Some numbers appear only in the text. Use complete record text and explicitly supplied provenance, with unavailable context left unknown. Check text/value agreement and source pointers during ingestion. Use source type and date for official figures, and experimental setting for experimental figures.

### Simulated farm profiles

`saaf_simulated_farms.json` contains 20 synthetic profiles, ten each in الأحساء and القصيم, all marked `simulated: true`. The `about` section reports seed 2026 and documents randomized points, area, density-derived palm counts, synthetic soil and irrigation attributes, and biased disposal categories. Points are approximate demo locations. The file proposes Sentinel-2 and SoilGrids as future sources. Those are candidates subject to suitability checks and field validation.

- Observed sample ranges are 2.3–11.8 ha, 260–1,693 palms, 70–90% sand, pH 7.8–8.6, and 9,100–59,255 kg/year of estimated residue. Each annual residue value is the simulated palm count multiplied by the published estimate of 35 kg per palm per year from `ctx-02`. These ranges describe the fixture. A yearly estimate provides no pickup inventory.
- The fixture has no verified parcel boundaries, measured palm counts, soil samples with depth and dates, or irrigation water EC. The salinity boolean is a demo input. Any gridded soil estimate should carry source, depth, resolution, uncertainty where published, and sampling or retrieval date.
- Collection needs pickup quantities, material and moisture details, availability windows, access, facility acceptance and capacity, and distance or route data. Impact needs a defined baseline, measured mass and moisture, conversion yield, transport and processing inputs, and sourced, applicable factors with units and uncertainty. Verified water impact also needs measured irrigation volume and a suitable comparison.
- The simulated farm fixture has no verified parcel boundaries or farm-level reference counts. User-entered boundaries support satellite analysis with explicit provenance. Crown counts use high-resolution aerial imagery and a reviewed YOLO prediction.

## Application design

FastAPI and the CLI share a runtime factory that wires LangGraph, repositories, and lazily initialized agent adapters. LangChain integrates configurable OpenAI or Gemini chat and embeddings. Agents receive use-case inputs and call injected services. SQLite stores mutable farm and workflow records. ChromaDB serves a rebuildable scientific search index. The original JSON inputs remain the source artifacts.

**Knowledge flow.** Validate IDs and cross-references, then embed one `text_ar` per record. Store scalar metadata for filtering and hydrate full conditions, caveats, and source details by record ID from the validated corpus. Track corpus and embedding configuration so index rebuilds are repeatable. Evaluate Arabic retrieval on an annotated question set, including hard negatives. Return insufficient evidence if retrieved material cannot support the claim.

**Farm flow.** Validate and transactionally import fixtures keyed by farm ID. Keep simulation origin explicit and distinguish measured, estimated, and unknown fields. Farm lookups supply typed context. Query results from a simulated profile keep that label through routing, calculation, and HTTP serialization.

**Control flow.** The CLI invokes an acyclic LangGraph with a typed `AgentState`. A normalized Arabic rule-based router selects recommendation, collection, impact, or monitoring, or requests clarification. A turn runs at most one agent. The Recommendation Agent calls typed read-only farm and evidence tools that validate arguments, farm identity, and evidence membership. The graph preserves structured output and maps failures to Arabic messages.

Conversation context holds the active farm ID, previous intent and question, and temporary collection and monitoring drafts. A recognized follow-up can reuse the previous question for the same farm. Switching farms discards the previous question and drafts. Conflicting IDs stop dispatch. The CLI keeps context in memory. The HTTP boundary owns context in bounded, expiring single-worker sessions and serializes turns per session. Dedicated confirmation routes match an exact collection draft or a pending observation ID against that state.

The HTTP API validates typed JSON requests and responses, accepts bounded raw image uploads, and exposes generated images through session-scoped URLs. Arabic error envelopes omit raw input and exception details. Explicit CORS origins allow the local frontend to call the API. The local MVP runs on loopback and has no shared session backend or user authentication.

**Collection.** The collection service reads the simulation profile, captures the user's quantity in kilograms, and proposes the next simulated availability date. It checks farm identity and proposal date at confirmation. The SQLite `collection_requests` table stores request ID, farm foreign key, requested quantity, pickup date, creation timestamp, status, and simulation flag. A unique farm/date/quantity key makes repeated writes idempotent. Tracking is farm-scoped. Cancellation records a local status transition.

**Impact.** Deterministic aggregation computes registry totals and confirmed request quantities, plus status counts by region. The chat model selects how to frame the precomputed report in Arabic. A fixed fallback explains the report without provider access. Environmental indicators return typed missing-data lists until applicable measurements and documented factors are available.

**Monitoring.** The local CPU adapter loads only explicitly configured date palm weights and runs on a decoded JPEG or PNG. Predictions are image-scoped and retain pixel-space boxes, confidence scores, image and model identifiers, and an annotated PNG. An attested whole-farm image enables a review record scoped to the active farm. A separate confirmation uses a transaction and compares the previous count and observation ID before replacing the simulation's count and residue estimate. Confirmed predictions carry their own provenance. A farm switch discards the pending review. The GPU training and held-out evaluation workflow lives in a [separate Colab notebook](notebooks/train_palm_yolo_colab.ipynb).

The Colab workflow audits the pinned Al Ain TIFF/Pascal VOC release, converts paired examples to PNG/YOLO, and creates a seeded image-level split. The experimental report records exact source revision and declares spatial independence unverified. Independently sourced, labeled imagery is required for any claim of geographic generalization.

**Geospatial monitoring.** SQLite stores user-provided GeoJSON boundary inputs in a farm-keyed table separate from the simulated registry. Shapely validates topology and PyProj calculates WGS84 ellipsoidal area. Optional user coordinates must fall in the polygon. Otherwise, the GIS response supplies an interior representative point derived from the boundary. Earth Engine queries run only against registered user polygons. The Earth Engine adapter reads the Sentinel‑2 harmonized surface-reflectance collection, masks unusable SCL classes, and calculates NDVI with B8 and B4. The recent scene and history responses include scene-wide cloud percentage and farm-level valid pixel fraction. The server retrieves thumbnails for geographic overlays and returns PNG bytes with bounds. Earth Engine credentials and temporary thumbnail URLs stay on the server.

The satellite branch of the Monitoring Agent explains results in Arabic and leaves the farm count untouched. The whole-farm waste endpoint uses the stored count, distinguishing a simulation estimate from a reviewed model prediction. A YOLO observation retains image-level scope even when the user attests coverage.

## Proposed contracts

Agent results carry a status (`ok`, `needs_input`, `insufficient_evidence`, or `unavailable`), Arabic text, typed output, warnings, and provenance as applicable. The orchestrator also returns `unsupported` and `not_implemented`. Citations resolve to record ID, source ID, title, URL, evidence type, and available conditions and caveats. Quantities carry a unit and an origin or calculation method.

| Component | Inputs | Output and responsibility |
| --- | --- | --- |
| Knowledge retrieval service | Arabic query, optional topic filter | Ranked evidence records or insufficient evidence. Provides context to agents. |
| Farm service | Farm ID, filters, or validated import records | Farm profile, list, or import result with provenance. Owns validation and persistence. |
| Recommendation Agent | Arabic question and optional farm profile | Cited evidence summary and applicable cautions. Apply alkaline-soil caution at pH ≥ 8 and salinity caution when indicated. Treat unknown pH and salinity explicitly. Any reference to amendments or treated biochar follows the dataset rules, carries the available evidence limits, and calls for specialist review. |
| Orchestrator | Arabic request and structured context such as farm ID | Routed agent result or a clarification. Validates tool inputs and preserves evidence and provenance. |
| Collection Agent | Farm ID and confirmed pickup details, plus optional facility and routing inputs | Internal request draft and missing inputs, or a proposed plan when the required logistics data exist. Uses explicit availability and capacity inputs. |
| Impact Agent | Scenario boundary and baseline, activity quantities, and applicable sourced factors | Reproducible scenario estimate with method, units, assumptions, and uncertainty where supported. Deterministic calculations run in a service. Missing factors produce an explicit data gap. |
| Palm Monitoring Agent | Local authorized aerial image, simulation farm ID, optional whole-farm attestation | Image-scoped detections, annotated image, waste estimate, and optional pending review. A matching separate confirmation can persist the predicted count with provenance. |

## Directory layout

```text
data/                         Original JSON inputs
src/saaf/
  domain/                     Typed contracts and provenance
  knowledge/                  Corpus ingestion and Chroma retrieval
  farms/                      Farm service and SQLite repository
  agents/                     Recommendation, collection, impact, monitoring
  orchestration/              LangGraph routing and typed tool bindings
  collection/                 Pickup workflow and persistence
  impact/                     Deterministic scenario calculations
  monitoring/                 Imagery validation and YOLO adapter
  api/                        FastAPI routes and dependency wiring
tests/                        Pytest tests added with each phase
var/                          Ignored local indexes and databases
```

Phase 0 creates the top-level source and test scaffolding. Add subpackages, entry points, dependency declarations, and database schema in the phase that first uses them.
