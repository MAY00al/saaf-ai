"""Monitoring operations shared by the agent and HTTP endpoints."""

from typing import Literal

from pydantic import BaseModel

from saaf.farms.models import RESIDUE_KG_PER_PALM_PER_YEAR
from .repository import FarmGeography, FarmMissing, GeographyRepository
from .satellite import (
    COLLECTION, DATASET_URL, EarthEngineProvider, Mode, Preview, SatelliteBatch,
    SatelliteFailure, SatelliteProvider, SatelliteQuery, Scene,
)

_WARNING = (
    "يصف مؤشر NDVI حالة الغطاء النباتي في البكسلات الصالحة. "
    "لا يحدد عدد النخيل الفردي ولا يثبت توفير مياه الري."
)
_MESSAGES = {
    "farm_not_found": "تعذّر العثور على المزرعة.",
    "boundary_required": "أضف حدود المزرعة أولاً. الإحداثيات المحاكاة لا تُستخدم لجلب صور الأقمار الصناعية.",
    "not_configured": "خدمة Earth Engine غير مهيّأة. اضبط مشروع Google Cloud وبيانات الاعتماد.",
    "authentication_failed": "تعذّر التحقق من صلاحية Earth Engine لهذا المشروع.",
    "provider_unavailable": "تعذّر الوصول إلى بيانات الأقمار الصناعية حالياً.",
    "no_imagery": "لم توجد صور Sentinel‑2 تستوفي نطاق التاريخ وشروط التغطية.",
}


class SatelliteProvenance(BaseModel):
    provider: Literal["Google Earth Engine"] = "Google Earth Engine"
    collection: str = COLLECTION
    source_url: str = DATASET_URL
    reflectance_resolution_m: Literal[10] = 10
    cloud_mask_band: Literal["SCL"] = "SCL"
    cloud_mask_native_resolution_m: Literal[20] = 20
    cloud_percentage_scope: Literal["whole_scene"] = "whole_scene"
    boundary_origin: Literal["user_provided"] = "user_provided"
    boundary_verified: Literal[False] = False


class VegetationResult(BaseModel):
    farm_id: str
    mode: Mode
    status: Literal["ok", "farm_not_found", "boundary_required", "not_configured",
                    "authentication_failed", "provider_unavailable", "no_imagery"]
    answer_ar: str
    warning_ar: str = _WARNING
    geography: FarmGeography | None = None
    provenance: SatelliteProvenance | None = None
    scenes: tuple[Scene, ...] = ()
    preview: Preview | None = None


class FarmWasteEstimate(BaseModel):
    farm_id: str
    simulated_profile: bool
    palm_count: int
    count_scope: Literal["whole_farm"] = "whole_farm"
    count_origin: Literal["simulation_estimate", "reviewed_model_prediction"]
    observation_id: str | None
    estimated_annual_waste_kg: int
    factor_kg_per_palm_per_year: int = RESIDUE_KG_PER_PALM_PER_YEAR
    factor_source_id: Literal["NASSER2016"] = "NASSER2016"
    factor_record_id: Literal["ctx-02"] = "ctx-02"
    warning_ar: str = "تقدير سنوي مبني على عدد النخيل المسجل؛ الكمية الفعلية قد تختلف."


class GeoMonitoring:
    def __init__(self, geography: GeographyRepository, provider: SatelliteProvider | None = None) -> None:
        self.geography = geography
        self.provider = provider if provider is not None else EarthEngineProvider()

    def waste_estimate(self, farm_id: str) -> FarmWasteEstimate:
        farm = self.geography.farms.get_farm(farm_id)
        if farm is None:
            raise FarmMissing
        observation_id = farm.provenance.palm_count_observation_id
        return FarmWasteEstimate(
            farm_id=farm_id, simulated_profile=farm.simulated, palm_count=farm.palm_count,
            count_origin="reviewed_model_prediction" if observation_id else "simulation_estimate",
            observation_id=observation_id,
            estimated_annual_waste_kg=farm.palm_count * RESIDUE_KG_PER_PALM_PER_YEAR,
        )

    def inspect(self, farm_id: str, mode: Mode, options: SatelliteQuery) -> VegetationResult:
        try:
            geography = self.geography.get(farm_id)
        except FarmMissing:
            return VegetationResult(
                farm_id=farm_id, mode=mode, status="farm_not_found", answer_ar=_MESSAGES["farm_not_found"],
            )
        registered = geography.registered_boundary
        if registered is None:
            return VegetationResult(
                farm_id=farm_id, mode=mode, status="boundary_required",
                answer_ar=_MESSAGES["boundary_required"], geography=geography,
            )
        try:
            result = self.provider.fetch(registered.geometry, options, mode)
            batch = SatelliteBatch.model_validate(result.model_dump())
        except SatelliteFailure as exc:
            return VegetationResult(
                farm_id=farm_id, mode=mode, status=exc.status,
                answer_ar=_MESSAGES[exc.status], geography=geography,
            )
        except Exception:
            return VegetationResult(
                farm_id=farm_id, mode=mode, status="provider_unavailable",
                answer_ar=_MESSAGES["provider_unavailable"], geography=geography,
            )
        if not batch.scenes:
            return VegetationResult(
                farm_id=farm_id, mode=mode, status="no_imagery",
                answer_ar=_MESSAGES["no_imagery"], geography=geography,
            )
        latest = max(batch.scenes, key=lambda scene: scene.acquired_at)
        answer = (
            f"أحدث صورة صالحة من Sentinel‑2 بتاريخ {latest.acquired_at.date()}. "
            f"المساحة المحسوبة من الحدود المدخلة {registered.area_ha:.2f} هكتار، "
            f"والجزء الصالح للتحليل {latest.farm_valid_fraction:.0%} من مساحة المزرعة."
        )
        if latest.ndvi:
            answer += (
                f" متوسط NDVI ‏{latest.ndvi.mean:.3f}، من {latest.ndvi.minimum:.3f} "
                f"إلى {latest.ndvi.maximum:.3f} في البكسلات الصالحة."
            )
        if latest.vegetation_fraction_of_valid is not None:
            answer += f" صنّف Sentinel‑2 ‏{latest.vegetation_fraction_of_valid:.0%} من البكسلات الصالحة كغطاء نباتي."
        return VegetationResult(
            farm_id=farm_id, mode=mode, status="ok", answer_ar=f"{answer} {_WARNING}",
            geography=geography, provenance=SatelliteProvenance(), scenes=batch.scenes,
            preview=batch.preview,
        )
