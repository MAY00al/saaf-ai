# SAAF frontend API guide

The local server listens on `http://127.0.0.1:8000`. API routes use `/api/v1`. Swagger UI is at `/docs`, ReDoc at `/redoc`, and the machine-readable schema at `/openapi.json`. The schema can generate frontend types.

## Local startup

Accept the private GitHub invitation, clone the team repository, and run from its root in a Python 3.11+ virtual environment. Follow the [team setup commands](../README.md#team-local-setup) to create and activate the environment and copy `.env.example` to `.env`.

```sh
python -m pip install -e ".[test,vision,satellite]"
python -m saaf.farms seed
python -m uvicorn saaf.api.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

Set server options in `.env` using `.env.example`. If you override the SQLite path in `.env`, pass that same path to `python -m saaf.farms seed --db PATH`. Set `SAAF_CORS_ORIGINS` to the comma-separated frontend origins, including their ports. Defaults include `http://localhost:5173` and `http://127.0.0.1:5173`. Provider credentials belong in the backend environment. Impact reports have an offline Arabic fallback. The template points monitoring to the trusted `models/best.pt` from the private clone. Start frontend work on `feat/frontend` in `frontend/` using the [frontend guide](FRONTEND_GUIDE.md).

## Team smoke tests

1. Run `python -m pytest -q` for offline regression coverage. In Swagger, check `GET /health/ready`, list farms, and create a session using `POST /api/v1/sessions`. Use a disposable local database when confirming changes.
2. For real recommendations, create your own [Gemini API key](https://aistudio.google.com/apikey). Set `GOOGLE_API_KEY`, `SAAF_CHAT_PROVIDER=gemini`, and `SAAF_EMBEDDING_PROVIDER=gemini` in `.env`. Leave model overrides empty unless needed, then restart. Send a chat question for `SIM-002`, such as «هل البيوشار مناسب لتربة مزرعتي؟», and inspect returned citations and warnings. For a focused RAG and citation check, run `python -m pytest -q tests/live_api.py`. This test makes real provider calls. An offline pass does not verify Gemini availability or quota.
3. Propose a collection for `SIM-001` with the example below, submit the exact returned draft after reviewing it, and verify the saved request through the farm's collection endpoints. Use `GET /api/v1/impact` to see the confirmed quantity and `POST /api/v1/impact/assess` to verify the missing-data state for avoided emissions.
4. Upload an authorized aerial JPEG or PNG using the raw-body endpoint. Confirm the response contains detections and an annotated image URL. Keep `whole_farm` off to exercise inference without changing the farm count.
5. Preview area and register a polygon using the [Swagger walkthrough](#swagger-walkthrough-using-public-agricultural-coordinates). For live Sentinel‑2 requests, each developer runs `earthengine authenticate` under their own Google account and sets `SAAF_EE_PROJECT` to a registered project they can use. Restart the API. Run the three Swagger satellite modes or the opt-in `python -m pytest -q -s tests/live_earth_engine.py`. Project initialization was verified previously. Live imagery, NDVI previews, and history through FastAPI remain pending verification.

This is a single-worker, loopback MVP with a shared simulated registry. Sessions are in memory, expire after one hour of inactivity by default, and disappear on restart. The server keeps at most eight recent annotations per session. The session ID grants access to that session's context and images. Treat it as private. Add authentication and authorization before exposing the service beyond trusted local callers.

## Routes

| Method and path | Purpose |
| --- | --- |
| `GET /health/live`, `GET /health/ready` | Process liveness and SQLite readiness. Readiness also reports whether the weights file is configured and present. |
| `POST /sessions`, `GET /sessions/{session_id}`, `DELETE /sessions/{session_id}` | Create, inspect, and end a conversation. |
| `POST /sessions/{session_id}/chat` | Send one Arabic message and an optional current farm ID. |
| `GET /farms`, `GET /farms/statistics` | List profiles or totals with optional `region` query filter. |
| `POST /farms`, `GET /farms/{farm_id}`, `PATCH /farms/{farm_id}`, `DELETE /farms/{farm_id}` | Manage simulated farms. Create with the full `Farm` schema and its matching residue estimate. PATCH accepts descriptive and soil fields. Palm-count updates use monitoring confirmation. |
| `POST /sessions/{session_id}/collections/propose`, `POST /sessions/{session_id}/collections/confirm` | Propose a pickup and confirm its exact draft. |
| `GET /farms/{farm_id}/collections`, `GET /farms/{farm_id}/collections/{request_id}`, `POST /farms/{farm_id}/collections/{request_id}/cancel` | Track or cancel a persisted simulated pickup. Cancellation requires `{"confirmed":true}`. |
| `GET /impact`, `POST /impact/assess` | Get deterministic totals by optional region, or assess an environmental question. |
| `POST /sessions/{session_id}/monitoring/detect` | Upload one JPEG or PNG as the raw body. Query parameters are `farm_id` and optional `whole_farm=true`. |
| `GET /sessions/{session_id}/images/{observation_id}` | Fetch the annotated PNG from the originating session. |
| `POST /sessions/{session_id}/monitoring/confirm` | Confirm the pending observation and update the simulated farm count. |
| `PUT /farms/{farm_id}/boundary`, `GET /farms/{farm_id}/boundary` | Register or read a user-provided polygon and optional point. The response includes the separate simulated registry location. |
| `POST /geography/area`, `GET /farms/{farm_id}/boundary/area` | Calculate WGS84 geodesic area in hectares from a supplied or registered polygon. |
| `GET /farms/{farm_id}/satellite/imagery`, `/satellite/ndvi`, `/satellite/history` | Get the latest suitable true-color image, NDVI statistics and preview, or historical NDVI observations. |
| `GET /farms/{farm_id}/waste-estimate` | Get the whole-farm estimate based on the stored simulated or reviewed model count. It includes the source and scope. |

Except health and documentation routes, prefix each path above with `/api/v1`.

## Chat and citations

Create a session with an empty `POST /api/v1/sessions`, then use its returned `session_id` for subsequent turns. Reuse the same session ID to retain farm context. Supply a different `farm_id` to switch farms and discard pending drafts from the old farm.

Example session response:

```json
{"session_id":"17d85621-37bb-49b0-932c-3db654191553","farm_id":null,"expires_at":"2026-11-20T16:00:00Z"}
```

```json
{"message":"وش قالت الدراسات العلمية عن عدد النخيل؟","farm_id":"SIM-002"}
```

Successful chat responses include `intent`, `status`, `answer_ar`, `session`, `candidate_intents`, and the relevant result object. A recommendation includes source record IDs and URLs, evidence levels, applicable study conditions and caveats, warnings, and `simulated_data`. Use citations from the response and show the simulation label beside farm-derived results.

## Collection

Propose a pickup with a confirmed user-entered quantity in whole kilograms. The proposal response includes a separate annual estimate and `collection.draft`. Its `awaiting_confirmation` status means the user must review the proposal before the frontend sends confirmation.

```json
{"farm_id":"SIM-001","requested_quantity_kg":120}
```

Confirmation example with an illustrative date. Copy the actual draft from the proposal response verbatim.

```json
{"confirmed":true,"draft":{"farm_id":"SIM-001","requested_quantity_kg":120,"pickup_date":"2026-11-21"}}
```

On success, use `collection.request.request_id` to track the saved request. An already-used or changed confirmation returns HTTP 409. The status is for simulated pickup requests.

## Impact and image upload

Send `{"message":"كم الانبعاثات المتجنبة؟"}` to `POST /api/v1/impact/assess`. An HTTP 200 response can have `status: "insufficient_data"`, with missing measurements and factors in `gaps` and available simulated totals in `metrics`.

Selected fields from an insufficient-data response:

```json
{
  "status":"insufficient_data",
  "simulated":true,
  "gaps":[{
    "indicator":"avoided_emissions",
    "label_ar":"الانبعاثات المتجنبة",
    "missing_information":["خط أساس وحدود مقارنة محددة","بيانات النقل والمعالجة المقاسة","عوامل انبعاث موثقة للسيناريوهين"]
  }]
}
```

Send the browser's `File` directly as the request body with its `image/jpeg` or `image/png` content type. The server accepts up to 40 MiB. Render the annotation using the API origin plus the relative URL in `monitoring.observation.annotated_image`. Preserve the `farm_simulated` and `count_origin` fields. A partial image provides an image-scoped count. Use `whole_farm=true` only after the user attests coverage. If the response is `awaiting_confirmation`, show the annotated image and proposed count before sending an explicit confirmation in the same session:

```json
{"confirmed":true,"observation_id":"OBS-0123456789ABCDEF0123456789ABCDEF"}
```

## Responses and errors

Domain outcomes such as `needs_input`, `awaiting_confirmation`, `insufficient_evidence`, `insufficient_data`, and agent `unavailable` can be HTTP 200. Branch on the body status. HTTP 404 covers missing or expired resources, 409 covers conflicts, 413 covers an oversized image, 415 covers the wrong image media type, and 422 covers an invalid request. Error responses have a stable envelope:

```json
{"error":{"code":"session_not_found","message_ar":"الجلسة غير موجودة أو انتهت صلاحيتها."}}
```

Create a fresh session after expiration and repeat the proposal rather than replaying a prior confirmation. Use `python -m pytest -q` for the offline suite and `python -m pytest -q tests/live_api.py` for an opt-in provider smoke test.

## Farm boundaries and vegetation

Upload a GeoJSON Polygon in longitude, latitude order. Rings must be closed. Holes are supported. Multipolygons and antimeridian crossings require preprocessing. Optional named coordinates must both be present and inside or on the polygon. When omitted, the API reports an interior point derived from the user boundary. The example below is illustrative.

```json
{
  "boundary":{"type":"Polygon","coordinates":[[[49.52,25.40],[49.521,25.40],[49.521,25.401],[49.52,25.401],[49.52,25.40]]]},
  "latitude":25.4005,
  "longitude":49.5205
}
```

Send the wrapper to `PUT /api/v1/farms/SIM-001/boundary`, or send the bare GeoJSON Polygon to `POST /api/v1/geography/area` for a calculation without saving. Read `registered_boundary.area_ha` for the calculated area. `stored_location` and `stored_area_ha` retain their original simulation meaning.

Satellite endpoints accept optional `start_date` and `end_date` as inclusive ISO calendar dates, `max_scene_cloud_pct` (default 80), `min_clear_fraction` (default 0.5), and a history `limit` from 1 to 12. The default window covers the last 90 days. Maximum window length is 366 days. Requests consider up to 60 recent candidate scenes. A scene cloud percentage describes the full Sentinel‑2 tile. Farm valid fraction describes usable pixels inside the supplied boundary after masking. `vegetation_fraction_of_valid` is the fraction of those pixels that Sentinel‑2 classifies as vegetation using SCL class 4 at 20 m native resolution. Each qualifying NDVI scene includes mean, minimum, and maximum at 10 m reflectance resolution. History is oldest first and contains observations for suitable scenes rather than interpolated dates.

For a recent image or NDVI preview, render `preview.data` as a base64 PNG overlay with `preview.bounds` in `[west,south,east,north]` and CRS EPSG:4326. The NDVI scale spans −1 to +1, from blue through pale yellow to green. Use `scenes` for a time-series chart. Use the boundary geometry for the outline.

Satellite responses can return `boundary_required`, `not_configured`, `authentication_failed`, `provider_unavailable`, or `no_imagery` with no observations. NDVI does not establish palm counts or measured irrigation savings. Waste is estimated from the stored whole-farm count using `ctx-02`; the YOLO response retains its image count scope. See the [Earth Engine setup in README](../README.md#farm-boundaries-and-satellite-monitoring) for account and permission requirements.

### Swagger walkthrough using public agricultural coordinates

This demonstration uses a small sampling rectangle around the point published for the Broadbalk long-term wheat experiment in Harpenden, UK. The rectangle is an analytical test boundary. The published point comes from [Rothamsted Research](https://www.era.rothamsted.ac.uk/experiment/rbk1).

1. Run these commands in PowerShell from the repository root after installing the satellite extra and authenticating. They isolate the demo from existing farm boundaries.

   ```powershell
   $env:SAAF_SQLITE_PATH = "var/broadbalk-demo.sqlite3"
   python -m saaf.farms seed --db var/broadbalk-demo.sqlite3
   python -m uvicorn saaf.api.app:app --host 127.0.0.1 --port 8000 --no-access-log
   ```

2. Open [Swagger UI](http://127.0.0.1:8000/docs). Select **PUT /api/v1/farms/{farm_id}/boundary**, click **Try it out**, and enter `SIM-001`.
3. Paste the JSON below and click **Execute**. Check for `registered_boundary.origin: "user_provided"` and an area in hectares.

```json
{
  "boundary": {
    "type": "Polygon",
    "coordinates": [[[-0.3736,51.8091],[-0.3724,51.8091],[-0.3724,51.8098],[-0.3736,51.8098],[-0.3736,51.8091]]]
  },
  "longitude": -0.37301,
  "latitude": 51.80946
}
```

4. Select **GET /api/v1/farms/{farm_id}/satellite/{mode}**. Use `SIM-001`, `start_date=2026-05-01`, `end_date=2026-07-31`, `max_scene_cloud_pct=80`, `min_clear_fraction=0.5`, and `limit=3`. Execute once for each mode:
   - `imagery` returns Sentinel‑2 scene metadata and a true-color base64 PNG.
   - `ndvi` returns mean, minimum, and maximum NDVI and a colorized base64 PNG.
   - `history` returns up to three observations in chronological order.

For a terminal equivalent, request `GET /api/v1/farms/SIM-001/satellite/ndvi?start_date=2026-05-01&end_date=2026-07-31&max_scene_cloud_pct=80&min_clear_fraction=0.5&limit=3`. Check the JSON `status` before rendering. Run the three modes once for a smoke test. The UI should avoid automatically polling Earth Engine.
