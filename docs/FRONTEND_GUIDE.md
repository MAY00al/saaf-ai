# SAAF frontend developer guide

SAAF (سَعَف) is an Arabic-first platform for date palm farmers and farm managers. It brings together farm records, palm-residue planning, aerial palm detection, satellite vegetation observations, and scientific guidance about biochar. Agricultural advisors can use the cited research and warnings to discuss results with farmers. The current handoff targets a trusted local demo with simulated farm and collection records.

## Local setup

Accept the private GitHub repository invitation and clone using the URL supplied by the owner. Run the following from PowerShell with Python 3.11 or newer and Git installed. Replace `OWNER_REPOSITORY_URL` with that URL.

```powershell
git clone OWNER_REPOSITORY_URL saaf-ai
Set-Location saaf-ai
git switch -c feat/frontend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test,vision,satellite]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

On macOS/Linux use `python3 -m venv .venv`, `source .venv/bin/activate`, and copy `.env.example` to `.env` only if `.env` is missing. The backend uses FastAPI and Uvicorn, SQLite, LangGraph, LangChain, and ChromaDB. The `test` extra adds the test tooling, `vision` adds the YOLO runtime, and `satellite` adds Earth Engine support.

| Backend configuration | Setup |
| --- | --- |
| Database | `SAAF_SQLITE_PATH` defaults to `var/saaf.sqlite3`. If you change it, pass the same path to the seed command with `--db`. Seeding adds the 20 simulated profiles without duplicating them or overwriting local edits. |
| Scientific retrieval | Set `SAAF_CHAT_PROVIDER` and `SAAF_EMBEDDING_PROVIDER` independently to `openai` or `gemini`. Set the corresponding `OPENAI_API_KEY` or `GOOGLE_API_KEY` in the backend. Optional model overrides are `SAAF_CHAT_MODEL` and `SAAF_EMBEDDING_MODEL`. Use the repository's index rebuild workflow when switching embeddings. [Live retrieval setup](../README.md#live-retrieval) |
| Palm detection | Use the trusted `models/best.pt` from the private clone and verify its SHA‑256 against the evaluation report. The template already sets `SAAF_PALM_WEIGHTS=models/best.pt`. Run from the repository root. Keep the checkpoint within the authorized educational team. [CPU monitoring setup](../README.md#local-cpu-palm-monitoring) |
| Satellite | Set `SAAF_EE_PROJECT` to a registered project and authenticate for the account running the backend. If using service-account credentials, point `SAAF_EE_SERVICE_ACCOUNT_FILE` at a private local file. [Earth Engine setup](../README.md#farm-boundaries-and-satellite-monitoring) |
| CORS | `SAAF_CORS_ORIGINS` accepts a comma-separated list of exact origins with scheme and port. The defaults are `http://localhost:5173,http://127.0.0.1:5173`. Set the actual frontend origin when using a different port and restart the backend. |

```powershell
python -m saaf.farms seed
python -m uvicorn saaf.api.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

Use one worker. Check [liveness](http://127.0.0.1:8000/health/live) and [readiness](http://127.0.0.1:8000/health/ready). Readiness checks SQLite and reports checkpoint presence. Run the [team smoke tests](API_INTEGRATION.md#team-smoke-tests) to verify each service. In [Swagger UI](http://127.0.0.1:8000/docs), use **Try it out** to confirm request bodies, response codes, and enum values. Use the [OpenAPI schema](http://127.0.0.1:8000/openapi.json) to generate client types and [ReDoc](http://127.0.0.1:8000/redoc) to browse the contract. The browser needs only the API base URL. Keep `.env` and credentials out of Git, and keep credentials and model weights out of client bundles and static assets.

## Farmer journey

1. Open the dashboard and see a simulation notice, regional totals, and the active farm. Select an existing profile or open farm registration.
2. Enter the farm details, keeping unknown soil and irrigation values unknown. Open the map, draw or import a boundary, preview its area, and explicitly save it.
3. Open monitoring and upload an authorized top-down aerial or drone image. Review the boxes, count, confidence, and image-scoped waste estimate. If the image covers the whole farm, attest coverage and separately confirm any proposed change to the stored palm count.
4. Select a date range in satellite monitoring. Review usable imagery, the NDVI overlay and statistics, and historical observations when available.
5. Ask the assistant in Arabic about biochar suitability, provide missing context when requested, and inspect scientific citations and warnings.
6. Enter the pickup quantity, review the proposed date and simulation label, and confirm. Track the resulting request by ID and confirm any cancellation.
7. Open impact reports to compare regional totals and confirmed request quantities. Review missing-data explanations for unsupported environmental indicators.

## Screen-to-API map

All paths in this table are relative to `/api/v1`. Replace `{farm_id}`, `{session_id}`, `{request_id}`, and `{observation_id}` with values returned by the API.

| Screen | What to build | Routes |
| --- | --- | --- |
| Dashboard | Farm selector, region filter, registry totals, active-farm waste estimate, and links to monitoring and requests. Keep aggregate estimates separate from individual farm estimates. | `GET /farms`, `GET /farms/statistics`, `GET /impact`, `GET /farms/{farm_id}/waste-estimate` |
| Farm management and registration | List and filter farms, show soil and irrigation details, create or edit profiles, and confirm deletion. Use the full OpenAPI `Farm` schema for creation, including `simulated: true` and an initial annual estimate consistent with 35 kg per palm per year. Use the monitoring workflow for palm-count changes. | `GET /farms?region=…`, `POST /farms`, `GET /farms/{farm_id}`, `PATCH /farms/{farm_id}`, `DELETE /farms/{farm_id}` |
| Interactive farm map | Draw or import a closed WGS84 GeoJSON Polygon, validate it, preview geodesic hectares, then save it. Distinguish the user-provided outline and area from the simulated registry point and area. | `POST /geography/area`, `GET` and `PUT /farms/{farm_id}/boundary`, `GET /farms/{farm_id}/boundary/area` |
| Palm monitoring | Upload one image, show original and annotated views, detection boxes and confidences, image count and waste estimate, and whole-farm review where eligible. | `POST /sessions/{session_id}/monitoring/detect`, `GET /sessions/{session_id}/images/{observation_id}`, `POST /sessions/{session_id}/monitoring/confirm` |
| Satellite and NDVI | Set dates, load true-color and NDVI overlays on demand, show acquisition date and quality, and chart observations. Offer boundary registration when needed. | `GET /farms/{farm_id}/satellite/imagery`, `GET /farms/{farm_id}/satellite/ndvi`, `GET /farms/{farm_id}/satellite/history` |
| AI assistant | Arabic chat with an active-farm indicator, clarification, cited recommendations, and structured agent results. | `POST /sessions`, `GET` and `DELETE /sessions/{session_id}`, `POST /sessions/{session_id}/chat` |
| Waste collection and tracking | Capture whole kilograms, show the estimated annual waste separately, review the proposed pickup, track the saved request, and confirm cancellation. | `POST /sessions/{session_id}/collections/propose`, `POST /sessions/{session_id}/collections/confirm`, `GET /farms/{farm_id}/collections`, `GET /farms/{farm_id}/collections/{request_id}`, `POST /farms/{farm_id}/collections/{request_id}/cancel` |
| Environmental impact | Region-filtered metrics for farms, palms, estimated annual waste, and confirmed collection quantities. Show request status and region breakdowns and missing inputs for other indicators. | `GET /impact?region=…`, `POST /impact/assess` |

## Request and response examples

The examples use illustrative identifiers and dates. Response fragments omit unrelated fields. The [API integration reference](API_INTEGRATION.md) contains more payloads and the full Swagger walkthrough.

### Sessions and recommendations

Send an empty `POST /api/v1/sessions`. A session response includes the ID, current farm, and expiration.

```json
{"session_id":"17d85621-37bb-49b0-932c-3db654191553","farm_id":null,"expires_at":"2026-11-20T16:00:00Z"}
```

Send the next request to `POST /api/v1/sessions/{session_id}/chat`.

```json
{"farm_id":"SIM-002","message":"هل البيوشار مناسب لتربة مزرعتي؟"}
```

Render `answer_ar` and branch on `intent` and `status`. For recommendations, render `recommendation.sources`, `evidence_level`, `warnings`, and `missing_information` alongside the answer. Each citation should expose the title, link, record and source IDs, source and evidence types, available study conditions, and caveats. Preserve laboratory and field distinctions and attach the simulation badge using `simulated_data`. Use the returned text and evidence for suitability guidance and show unsupported dosage or savings claims as evidence gaps.

### Farms, map, and satellite

To create a demo farm, send the full profile to `POST /api/v1/farms`. Example request:

```json
{
  "farm_id":"DEMO-101","region":"الرياض","lat":24.71,"lon":46.67,
  "area_ha":2,"palm_count":10,"est_residue_kg_per_year":350,
  "soil_sand_pct":null,"soil_ph":null,"irrigation_system":null,
  "irrigation_water_saline":null,"current_disposal":null,"simulated":true
}
```

An edit to a known soil attribute can use `PATCH /api/v1/farms/DEMO-101` with `{"soil_ph":7.5}`. Use the returned profile to refresh the detail view. For boundary area preview, send the bare `boundary` value to `POST /api/v1/geography/area`. To register it, send the wrapper below to `PUT /api/v1/farms/SIM-001/boundary`.

```json
{
  "boundary": {
    "type": "Polygon",
    "coordinates": [[[-0.3736,51.8091],[-0.3724,51.8091],[-0.3724,51.8098],[-0.3736,51.8098],[-0.3736,51.8091]]]
  },
  "latitude": 51.80946,
  "longitude": -0.37301
}
```

Use this public Broadbalk demo geometry with the isolated database in the Swagger walkthrough. GeoJSON coordinates are `[longitude, latitude]`. Close each ring, accept holes, and surface server validation errors for self-intersections, unsupported multipolygons, or antimeridian crossings. If included, the optional point needs both coordinates and must be inside or on the polygon. Read `registered_boundary.area_ha` for calculated hectares and `registered_boundary.origin` for provenance. The user-provided boundary is unverified.

Example request after saving the demo boundary:

```http
GET /api/v1/farms/SIM-001/satellite/ndvi?start_date=2026-05-01&end_date=2026-07-31&max_scene_cloud_pct=80&min_clear_fraction=0.5
```

Date bounds are inclusive, with a default 90-day window and a maximum 366-day window. The history endpoint accepts `limit` from 1 to 12. Render acquisition dates, scene cloud coverage, and valid pixel fraction inside the farm separately. NDVI uses Sentinel‑2 red and near-infrared bands at 10 m native resolution. Plot NDVI mean, minimum, and maximum from qualifying scenes and leave gaps between observations. The SCL vegetation fraction uses the 20 m classification band. Render `preview.data` as a base64 PNG mapped to EPSG:4326 `preview.bounds` in `[west,south,east,north]` order. Display the NDVI scale from −1 to +1. NDVI indicates vegetation conditions and cannot establish individual palm counts or measured irrigation savings. Show `boundary_required`, `not_configured`, `authentication_failed`, `provider_unavailable`, and `no_imagery` as distinct states. Avoid background polling.

### Palm detection and counting

Send the file itself as the body of `POST /api/v1/sessions/{session_id}/monitoring/detect?farm_id=SIM-001` with `Content-Type: image/jpeg` or `image/png`. The maximum is 40 MiB. Avoid multipart encoding. Resolve `monitoring.observation.annotated_image` against the API origin. If drawing boxes yourself, transform `detections[].xyxy` from image pixels using the returned `image_size`.

Use `whole_farm=true` only after a coverage attestation. When the server returns `awaiting_confirmation`, show the existing farm, proposed count, and annotated image before sending `POST /api/v1/sessions/{session_id}/monitoring/confirm`.

```json
{"confirmed":true,"observation_id":"OBS-0123456789ABCDEF0123456789ABCDEF"}
```

Display the prediction and its provenance alongside the farm's simulation status. A detection count describes the uploaded image. The stored count changes only after the eligible review is confirmed. Fetch the farm profile and `/waste-estimate` again after confirmation. Label both waste outputs as estimates, preserve count scope, and show the documented factor and source (`ctx-02`).

### Collection and impact

Send `{"farm_id":"SIM-001","requested_quantity_kg":120}` to `POST /api/v1/sessions/{session_id}/collections/propose`. Copy `collection.draft` from the response verbatim after user review. An illustrative `POST /api/v1/sessions/{session_id}/collections/confirm` request is below.

```json
{"confirmed":true,"draft":{"farm_id":"SIM-001","requested_quantity_kg":120,"pickup_date":"2026-11-21"}}
```

Track `collection.request.request_id` under the same farm. Cancellation takes `{"confirmed":true}`. Confirmed quantities represent simulated pickup requests using the farmer's requested kilograms. Show the pickup date as simulated availability.

Send `{"message":"كم الانبعاثات المتجنبة؟"}` to `POST /api/v1/impact/assess`. An HTTP 200 can return `"status":"insufficient_data"` with available `metrics` and `gaps[].missing_information`. Keep missing estimates distinct from zero. Biochar yield, stored carbon, avoided emissions, and water savings require applicable measurements and documented factors.

## UI behavior and safeguards

- Set `lang="ar"` and `dir="rtl"`. Use CSS logical properties, Arabic labels, accessible keyboard focus, and responsive layouts. Isolate identifiers, numbers, coordinates, URLs, and dates with bidirectional markup where needed. Keep map controls, legends, and confirmation actions usable on a narrow screen.
- Keep the active farm visible across pages. Use the server-issued session for chat and confirmation flows, and send the farm ID when switching context. Farm switches discard old drafts. Clear client-side drafts and stale view data on switches, guard against late responses from the previous farm, and use the returned session as the source of truth. Treat the session ID and annotation URLs as private, including in analytics. Session expiration is one hour of inactivity by default, and a server restart clears sessions. Start fresh and re-propose after expiration.
- Require a separate user action for pickup confirmation, cancellation, stored palm-count changes, boundary saves, and deletions. Show the target farm and the values being saved, disable repeat submission while pending, and refresh from the server on conflict or an uncertain write outcome.
- Label data at the point of use. Registry fields and collections are simulated, boundaries are user-provided and unverified, YOLO counts are model predictions, and live Sentinel‑2 values are satellite observations with acquisition dates and quality limits. Annual residue is an estimate. Keep unknown fields and unavailable indicators visibly unknown.
- Give loading, empty, missing-data, and unavailable states their own UI. Read the body `status` on HTTP 200 for outcomes such as `needs_input`, `awaiting_confirmation`, `insufficient_evidence`, `insufficient_data`, and `unavailable`. Render Arabic messages from the response. For HTTP errors, use the stable envelope below. Handle 404 by checking the farm or session, 409 by refreshing current state, 413 and 415 by correcting the upload, 422 by fixing invalid inputs, and 5xx by offering a retry for reads. Avoid automatically replaying confirmation requests.

```json
{"error":{"code":"session_not_found","message_ar":"الجلسة غير موجودة أو انتهت صلاحيتها."}}
```

## Collaboration and verification status

Develop in `frontend/` on a separate `feat/frontend` branch. The frontend developer can choose the framework and map library. Keep frontend dependencies and configuration in that directory. Build against the current OpenAPI contract, preserve agent behavior and response shapes, and raise backend contract changes separately. A practical first PR covers health, the farm selector, and the dashboard against seeded data.

| Capability | Current verification |
| --- | --- |
| Farm CRUD, sessions, routing, recommendations, collection and impact | Covered by offline regression and HTTP integration tests, including the four agents with provider doubles where applicable. The opt-in Gemini HTTP smoke test remains unverified. |
| Local YOLO CPU inference | Trained weights exercised through LangGraph and a local HTTP upload that returned an annotated PNG. The Al Ain evaluation used 93 held-out tiles and did not verify spatial independence. It does not establish accuracy in a new geography or across whole farms. |
| Geospatial and satellite contracts | Polygon validation, geodesic area, vegetation calculations, preview handling, and failure states were verified offline. A Phase 8 run passed 164 tests. On a later repeat, 163 passed and the Chroma persistence test timed out, then passed in isolation. |
| Live Earth Engine | CLI authentication and an authenticated initialization probe succeeded for `saaf-ai`. Live Sentinel‑2 retrieval, cloud-masked NDVI, true-color and NDVI previews, and history through FastAPI remain pending the Broadbalk smoke test. Use the [Swagger walkthrough](API_INTEGRATION.md#swagger-walkthrough-using-public-agricultural-coordinates) for that check. |

The MVP runs on loopback with a shared simulated registry, local SQLite, and in-memory single-worker sessions. Authentication, authorization, and tenant isolation are required before exposing it beyond trusted local callers. Each session retains at most eight recent annotations. Satellite availability depends on imagery, cloud masking, provider access, and quotas. Collection has no live dispatch or verified pickup, and scientific recommendations depend on available evidence and provider access.
