# SAAF frontend API guide

The local server listens on `http://127.0.0.1:8000`. API routes use `/api/v1`. Swagger UI is at `/docs`, ReDoc at `/redoc`, and the machine-readable schema at `/openapi.json`. The schema can generate frontend types.

## Local startup

Run from the repository root in an activated Python 3.11+ virtual environment.

```sh
python -m pip install -e ".[test,vision]"
python -m saaf.farms seed
python -m uvicorn saaf.api.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

Set server options in `.env` using `.env.example`. If you override the SQLite path in `.env`, pass that same path to `python -m saaf.farms seed --db PATH`. Set `SAAF_CORS_ORIGINS` to the comma-separated frontend origins, including their ports. Defaults include `http://localhost:5173` and `http://127.0.0.1:5173`. Provider credentials belong in the backend environment. Recommendation uses the configured chat and embedding providers. Impact reports have an offline Arabic fallback. Monitoring uses the configured local checkpoint.

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
