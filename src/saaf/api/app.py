"""FastAPI entry point for the SAAF local MVP."""

import os
import sqlite3
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from saaf.agents.impact import ImpactResult
from saaf.agents.tools import FarmId
from saaf.collection.models import CollectionRequest
from saaf.collection.repository import CollectionRepository
from saaf.farms import Farm, FarmAlreadyExists, FarmProfile, FarmRepository, FarmStatistics
from saaf.geospatial.geometry import FarmBoundaryInput, GeoPolygon
from saaf.geospatial.repository import FarmGeography, FarmMissing, GeographyRepository
from saaf.geospatial.satellite import Mode, SatelliteProvider, SatelliteQuery
from saaf.geospatial.service import FarmWasteEstimate, GeoMonitoring, VegetationResult
from saaf.orchestration.contracts import ImpactPort, OrchestrationResponse
from saaf.orchestration.graph import Orchestrator
from saaf.orchestration.runtime import build_orchestrator
from saaf.providers import load_environment

from .models import (
    ChatInput, ChatResponse, CollectionId, Confirmation, CountConfirmation, ErrorResponse,
    AreaResult, FarmPatch, Health, ImpactInput, ObservationId, PickupConfirmation, PickupInput,
    Region, SessionInfo,
)
from .sessions import Session, SessionCapacity, SessionMissing, Sessions

PREFIX = "/api/v1"
MAX_IMAGE_BYTES = 40 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}


@dataclass(frozen=True)
class Services:
    farms: FarmRepository
    collections: CollectionRepository
    impact: ImpactPort
    orchestrator: Orchestrator


def _fail(status: int, code: str, message: str):
    raise HTTPException(status, detail={"code": code, "message_ar": message})


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message_ar": message}})


def _services(request: Request) -> Services:
    return request.app.state.services


def _public_result(session: Session, result: OrchestrationResponse) -> ChatResponse:
    monitoring = result.monitoring
    if monitoring:
        observation = monitoring.observation
        if observation:
            session.save_image(observation.observation_id, Path(observation.annotated_image))
            url = f"{PREFIX}/sessions/{session.id}/images/{observation.observation_id}"
            observation = observation.model_copy(update={"annotated_image": url})
        monitoring = monitoring.model_copy(update={"observation": observation, "pending_review": None})
    session.context = result.context
    return ChatResponse(
        intent=result.intent, status=result.status, answer_ar=result.answer_ar, session=session.info(),
        candidate_intents=result.candidate_intents, recommendation=result.recommendation,
        collection=result.collection, impact=result.impact, monitoring=monitoring,
    )


def _turn(request: Request, session: Session, message: str, **options) -> ChatResponse:
    result = _services(request).orchestrator.run(message, context=session.context, **options)
    return _public_result(session, result)


def _farm(request: Request, farm_id: str) -> FarmProfile:
    farm = _services(request).farms.get_farm(farm_id)
    if farm is None:
        _fail(404, "farm_not_found", "تعذّر العثور على المزرعة.")
    return farm


def create_app(
    services: Services | None = None, *, cors_origins: list[str] | None = None,
    session_ttl_seconds: int | None = None,
    satellite_provider: SatelliteProvider | None = None,
) -> FastAPI:
    load_environment()
    origins = cors_origins if cors_origins is not None else [
        value.strip() for value in os.getenv(
            "SAAF_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",") if value.strip()
    ]
    if "*" in origins:
        raise ValueError("SAAF_CORS_ORIGINS requires explicit origins")
    ttl = int(os.getenv("SAAF_SESSION_TTL_SECONDS", "3600")) if session_ttl_seconds is None else session_ttl_seconds
    if ttl <= 0:
        raise ValueError("SAAF_SESSION_TTL_SECONDS must be positive")

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        root = Path("var")
        root.mkdir(exist_ok=True)
        with TemporaryDirectory(prefix="api-", dir=root) as temp:
            application.state.files = Path(temp).resolve()
            application.state.sessions = Sessions(ttl)
            farms = services.farms if services is not None else FarmRepository()
            geography = GeoMonitoring(GeographyRepository(farms), satellite_provider)
            application.state.geospatial = geography
            if services is None:
                collections = CollectionRepository(farms)
                graph, impact = build_orchestrator(
                    farms, collections, image_output=Path(temp) / "annotations", geospatial=geography,
                )
                application.state.services = Services(farms, collections, impact, graph)
            else:
                application.state.services = services
            yield

    app = FastAPI(
        title="SAAF API", version="1.0.0",
        description="Arabic-first local API for simulated farms, date-palm waste and evidence-based insights.",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def safe_errors(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            return _error(500, "internal_error", "تعذّر إكمال الطلب.")

    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"], allow_credentials=False,
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return _error(422, "invalid_request", "تحقق من صيغة الطلب والحقول المطلوبة.")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        if isinstance(exc.detail, dict) and {"code", "message_ar"} <= exc.detail.keys():
            return JSONResponse(status_code=exc.status_code, content={"error": exc.detail}, headers=exc.headers)
        return _error(exc.status_code, "http_error", "تعذّر تنفيذ طلب HTTP.")

    @app.exception_handler(SessionMissing)
    async def session_missing(request, exc):
        return _error(404, "session_not_found", "الجلسة غير موجودة أو انتهت صلاحيتها.")

    @app.exception_handler(SessionCapacity)
    async def session_capacity(request, exc):
        return _error(503, "session_capacity", "تعذّر إنشاء جلسة إضافية الآن.")

    @app.exception_handler(FarmMissing)
    async def missing_geospatial_farm(request, exc):
        return _error(404, "farm_not_found", "تعذّر العثور على المزرعة.")

    @app.get("/health/live", tags=["Health"], response_model=Health)
    def live():
        return Health(status="ok")

    @app.get("/health/ready", tags=["Health"], response_model=Health)
    def ready(request: Request):
        try:
            _services(request).farms.list_farms()
            _services(request).collections.list(farm_id="")
        except sqlite3.Error:
            _fail(503, "database_unavailable", "قاعدة البيانات غير متاحة.")
        configured = os.getenv("SAAF_PALM_WEIGHTS")
        return Health(status="ok", database="ok",
                      vision_weights_configured=bool(configured and Path(configured).is_file()))

    router = APIRouter(prefix=PREFIX, responses={
        404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse},
        500: {"model": ErrorResponse}, 503: {"model": ErrorResponse},
    })

    @router.post("/sessions", status_code=201, response_model=SessionInfo, tags=["Sessions"])
    def create_session(request: Request):
        return request.app.state.sessions.create()

    @router.get("/sessions/{session_id}", response_model=SessionInfo, tags=["Sessions"])
    def get_session(request: Request, session_id: UUID):
        with request.app.state.sessions.use(session_id) as session:
            return session.info()

    @router.delete("/sessions/{session_id}", status_code=204, tags=["Sessions"])
    def delete_session(request: Request, session_id: UUID):
        if not request.app.state.sessions.delete(session_id):
            _fail(409, "session_busy", "يوجد طلب قيد التنفيذ في هذه الجلسة.")
        return Response(status_code=204)

    @router.post("/sessions/{session_id}/chat", response_model=ChatResponse, tags=["Chat"])
    def chat(request: Request, session_id: UUID, body: ChatInput):
        with request.app.state.sessions.use(session_id) as session:
            return _turn(request, session, body.message, farm_id=body.farm_id)

    @router.get("/farms", response_model=list[FarmProfile], tags=["Farms"])
    def list_farms(request: Request, region: Region | None = None):
        return _services(request).farms.list_farms(region=region)

    @router.get("/farms/statistics", response_model=FarmStatistics, tags=["Farms"])
    def farm_statistics(request: Request, region: Region | None = None):
        return _services(request).farms.statistics(region=region)

    @router.post("/farms", status_code=201, response_model=FarmProfile, tags=["Farms"])
    def create_farm(request: Request, body: Farm):
        try:
            return _services(request).farms.create_farm(body)
        except FarmAlreadyExists:
            _fail(409, "farm_exists", "معرّف المزرعة مستخدم.")

    @router.get("/farms/{farm_id}", response_model=FarmProfile, tags=["Farms"])
    def get_farm(request: Request, farm_id: FarmId):
        return _farm(request, farm_id)

    @router.patch("/farms/{farm_id}", response_model=FarmProfile, tags=["Farms"])
    def update_farm(request: Request, farm_id: FarmId, body: FarmPatch):
        farm = _services(request).farms.update_farm(farm_id, **body.model_dump(exclude_unset=True))
        if farm is None:
            _fail(404, "farm_not_found", "تعذّر العثور على المزرعة.")
        return farm

    @router.delete("/farms/{farm_id}", status_code=204, tags=["Farms"])
    def delete_farm(request: Request, farm_id: FarmId):
        try:
            deleted = _services(request).farms.delete_farm(farm_id)
        except sqlite3.IntegrityError:
            _fail(409, "farm_has_collections", "تعذّر حذف مزرعة لها طلبات جمع محفوظة.")
        if not deleted:
            _fail(404, "farm_not_found", "تعذّر العثور على المزرعة.")
        return Response(status_code=204)

    @router.post("/geography/area", response_model=AreaResult, tags=["Geography"])
    def calculate_boundary_area(body: GeoPolygon):
        return AreaResult(area_ha=body.area_ha())

    @router.put("/farms/{farm_id}/boundary", response_model=FarmGeography, tags=["Geography"])
    def register_boundary(request: Request, farm_id: FarmId, body: FarmBoundaryInput):
        return request.app.state.geospatial.geography.register(farm_id, body)

    @router.get("/farms/{farm_id}/boundary", response_model=FarmGeography, tags=["Geography"])
    def get_boundary(request: Request, farm_id: FarmId):
        return request.app.state.geospatial.geography.get(farm_id)

    @router.get("/farms/{farm_id}/boundary/area", response_model=AreaResult, tags=["Geography"])
    def registered_boundary_area(request: Request, farm_id: FarmId):
        registered = request.app.state.geospatial.geography.get(farm_id).registered_boundary
        if registered is None:
            _fail(404, "boundary_required", "أضف حدود المزرعة أولاً.")
        return AreaResult(area_ha=registered.area_ha)

    @router.get("/farms/{farm_id}/waste-estimate", response_model=FarmWasteEstimate, tags=["Geography"])
    def registered_waste_estimate(request: Request, farm_id: FarmId):
        return request.app.state.geospatial.waste_estimate(farm_id)

    @router.get("/farms/{farm_id}/satellite/{mode}", response_model=VegetationResult, tags=["Satellite"])
    def satellite(request: Request, farm_id: FarmId, mode: Mode,
                  options: Annotated[SatelliteQuery, Query()]):
        """Return recent true-color imagery, NDVI with a map preview, or NDVI history."""
        result = request.app.state.geospatial.inspect(farm_id, mode, options)
        if result.status == "farm_not_found":
            raise FarmMissing
        return result

    @router.post("/sessions/{session_id}/collections/propose", response_model=ChatResponse, tags=["Collection"])
    def propose_collection(request: Request, session_id: UUID, body: PickupInput):
        with request.app.state.sessions.use(session_id) as session:
            return _turn(request, session, f"جمع المخلفات {body.requested_quantity_kg} كجم", farm_id=body.farm_id)

    @router.post("/sessions/{session_id}/collections/confirm", response_model=ChatResponse, tags=["Collection"])
    def confirm_collection(request: Request, session_id: UUID, body: PickupConfirmation):
        with request.app.state.sessions.use(session_id) as session:
            if session.context.pickup_draft != body.draft:
                _fail(409, "draft_mismatch", "المسودة لم تعد معلّقة في هذه الجلسة.")
            return _turn(request, session, "أؤكد", farm_id=body.draft.farm_id)

    @router.get("/farms/{farm_id}/collections", response_model=list[CollectionRequest], tags=["Collection"])
    def list_collections(request: Request, farm_id: FarmId):
        _farm(request, farm_id)
        return _services(request).collections.list(farm_id=farm_id)

    @router.get("/farms/{farm_id}/collections/{request_id}", response_model=CollectionRequest, tags=["Collection"])
    def get_collection(request: Request, farm_id: FarmId, request_id: CollectionId):
        item = _services(request).collections.get(request_id, farm_id=farm_id)
        if item is None:
            _fail(404, "collection_not_found", "طلب الجمع غير موجود لهذه المزرعة.")
        return item

    @router.post("/farms/{farm_id}/collections/{request_id}/cancel",
                 response_model=CollectionRequest, tags=["Collection"])
    def cancel_collection(request: Request, farm_id: FarmId, request_id: CollectionId, body: Confirmation):
        item = _services(request).collections.cancel(request_id, farm_id=farm_id)
        if item is None:
            _fail(404, "collection_not_found", "طلب الجمع غير موجود لهذه المزرعة.")
        return item

    @router.get("/impact", response_model=ImpactResult, tags=["Impact"])
    def impact_summary(request: Request, region: Region | None = None):
        return _services(request).impact.estimate_impact("إجمالي المزارع والطلبات", region=region)

    @router.post("/impact/assess", response_model=ImpactResult, tags=["Impact"])
    def assess_impact(request: Request, body: ImpactInput):
        return _services(request).impact.estimate_impact(body.message, region=body.region)

    @router.post(
        "/sessions/{session_id}/monitoring/detect", response_model=ChatResponse, tags=["Monitoring"],
        responses={413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}},
        openapi_extra={"requestBody": {"required": True, "content": {
            mime: {"schema": {"type": "string", "format": "binary"}} for mime in IMAGE_TYPES
        }}},
    )
    async def detect(request: Request, session_id: UUID, farm_id: FarmId, whole_farm: bool = False):
        mime = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if mime not in IMAGE_TYPES:
            _fail(415, "unsupported_image_type", "أرسل صورة JPEG أو PNG.")

        def analyze(path: Path):
            with request.app.state.sessions.use(session_id) as session:
                return _turn(request, session, "رصد النخيل", farm_id=farm_id,
                             image_path=path, whole_farm=whole_farm)

        with TemporaryDirectory(dir=request.app.state.files) as temp:
            image = Path(temp) / f"upload{IMAGE_TYPES[mime]}"
            size = 0
            with image.open("wb") as stream:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_IMAGE_BYTES:
                        _fail(413, "image_too_large", "حجم الصورة يتجاوز الحد المسموح.")
                    stream.write(chunk)
            if not size:
                _fail(422, "missing_image", "أرفق صورة للتحليل.")
            return await run_in_threadpool(analyze, image)

    @router.post("/sessions/{session_id}/monitoring/confirm", response_model=ChatResponse, tags=["Monitoring"])
    def confirm_count(request: Request, session_id: UUID, body: CountConfirmation):
        with request.app.state.sessions.use(session_id) as session:
            review = session.context.count_review
            if review is None or review.observation_id != body.observation_id:
                _fail(409, "review_mismatch", "لم يعد رصد العدد معلّقاً في هذه الجلسة.")
            return _turn(request, session, "أؤكد تحديث العدد", farm_id=review.farm_id)

    @router.get(
        "/sessions/{session_id}/images/{observation_id}", tags=["Monitoring"], response_class=Response,
        responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}},
    )
    def annotated_image(request: Request, session_id: UUID, observation_id: ObservationId):
        with request.app.state.sessions.use(session_id) as session:
            path = session.images.get(observation_id)
            if path is None or not path.is_file():
                _fail(404, "image_not_found", "الصورة المعلّمة غير متاحة لهذه الجلسة.")
            return Response(path.read_bytes(), media_type="image/png", headers={"Cache-Control": "no-store"})

    app.include_router(router)
    return app


app = create_app()
