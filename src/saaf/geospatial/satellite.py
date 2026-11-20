"""Typed Sentinel-2 observations and a lazy Earth Engine adapter."""

import base64
import os
from datetime import date, datetime, timedelta, timezone
from functools import cached_property
from typing import Literal, Protocol
from urllib.request import urlopen

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .geometry import GeoPolygon

COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
DATASET_URL = "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED"
Mode = Literal["imagery", "ndvi", "history"]
ProviderStatus = Literal["not_configured", "authentication_failed", "provider_unavailable", "no_imagery"]


def _today() -> date:
    return datetime.now(timezone.utc).date()


class SatelliteQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    start_date: date | None = None
    end_date: date = Field(default_factory=_today)
    max_scene_cloud_pct: float = Field(default=80, ge=0, le=100)
    min_clear_fraction: float = Field(default=0.5, gt=0, le=1)
    limit: int = Field(default=6, ge=1, le=12)

    @property
    def since(self) -> date:
        return self.start_date or self.end_date - timedelta(days=89)

    @model_validator(mode="after")
    def validate_dates(self) -> "SatelliteQuery":
        if self.end_date > _today() or not 0 <= (self.end_date - self.since).days <= 365:
            raise ValueError("use a past or current window of at most 366 inclusive days")
        return self


class NDVIStats(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    mean: float = Field(ge=-1, le=1)
    minimum: float = Field(ge=-1, le=1)
    maximum: float = Field(ge=-1, le=1)

    @model_validator(mode="after")
    def validate_order(self) -> "NDVIStats":
        if not self.minimum <= self.mean <= self.maximum:
            raise ValueError("NDVI statistics out of order")
        return self


class Scene(BaseModel):
    scene_id: str
    acquired_at: datetime
    scene_cloud_pct: float = Field(ge=0, le=100, allow_inf_nan=False)
    farm_valid_fraction: float = Field(ge=0, le=1, allow_inf_nan=False)
    vegetation_fraction_of_valid: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    ndvi: NDVIStats | None = None


class Preview(BaseModel):
    encoding: Literal["base64"] = "base64"
    media_type: Literal["image/png"] = "image/png"
    kind: Literal["true_color", "ndvi"]
    crs: Literal["EPSG:4326"] = "EPSG:4326"
    bounds: tuple[float, float, float, float]
    data: str


class SatelliteBatch(BaseModel):
    scenes: tuple[Scene, ...]
    preview: Preview | None = None


class SatelliteFailure(RuntimeError):
    def __init__(self, status: ProviderStatus) -> None:
        super().__init__(status)
        self.status = status


class SatelliteProvider(Protocol):
    def fetch(self, boundary: GeoPolygon, options: SatelliteQuery, mode: Mode) -> SatelliteBatch: ...


def ndvi_band(image):
    """Works with Earth Engine bands and an injected arithmetic double in tests."""
    nir, red = image.select("B8"), image.select("B4")
    total = nir.add(red)
    positive = total.gt(0)
    return nir.subtract(red).updateMask(positive).divide(total.updateMask(positive)).rename("NDVI")


class EarthEngineProvider:
    def __init__(self, project: str | None = None) -> None:
        self.project = project or os.getenv("SAAF_EE_PROJECT")

    @cached_property
    def ee(self):
        if not self.project:
            raise SatelliteFailure("not_configured")
        try:
            import ee
        except ImportError as exc:
            raise SatelliteFailure("not_configured") from exc
        try:
            credentials_file = os.getenv("SAAF_EE_SERVICE_ACCOUNT_FILE")
            if credentials_file:
                from google.oauth2 import service_account

                credentials = service_account.Credentials.from_service_account_file(
                    credentials_file,
                    scopes=["https://www.googleapis.com/auth/earthengine",
                            "https://www.googleapis.com/auth/cloud-platform"],
                )
                ee.Initialize(credentials=credentials, project=self.project)
            else:
                ee.Initialize(project=self.project)
        except (OSError, ValueError) as exc:
            raise SatelliteFailure("authentication_failed") from exc
        except Exception as exc:
            raise _provider_error(exc) from exc
        return ee

    def fetch(self, boundary: GeoPolygon, options: SatelliteQuery, mode: Mode) -> SatelliteBatch:
        ee = self.ee
        try:
            area = ee.Geometry(boundary.ee_geometry(), proj="EPSG:4326", geodesic=True)
            collection = (
                ee.ImageCollection(COLLECTION).filterBounds(area)
                .filterDate(options.since.isoformat(), (options.end_date + timedelta(days=1)).isoformat())
                .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", options.max_scene_cloud_pct))
                .sort("system:time_start", False).limit(60)
            )
            stats_reducer = ee.Reducer.mean().combine(ee.Reducer.minMax(), sharedInputs=True)

            def image_bands(image):
                scl = image.select("SCL")
                # Keep dark pixels, vegetation, bare soil and water; exclude unclassified,
                # invalid/saturated data, shadows, clouds, cirrus and snow/ice.
                clear = scl.eq(2).Or(scl.eq(4)).Or(scl.eq(5)).Or(scl.eq(6))
                bands = image.select(["B4", "B8", "B3", "B2"]).updateMask(clear)
                ndvi = ndvi_band(bands)
                vegetation = scl.eq(4).updateMask(ndvi.mask()).rename("vegetation")
                return bands.addBands(ndvi).addBands(vegetation)

            def describe(image):
                observed = image_bands(image)
                band = observed.select("NDVI")
                valid = band.mask().unmask(0, sameFootprint=False).rename("valid")
                stats = band.addBands(valid).addBands(observed.select("vegetation")).reduceRegion(
                    stats_reducer, area, scale=10, maxPixels=1_000_000,
                )
                return image.set({"saaf_clear": stats.get("valid_mean"), "saaf_stats": stats})

            count = options.limit if mode == "history" else 1
            selected = collection.map(describe).filter(ee.Filter.gte(
                "saaf_clear", options.min_clear_fraction,
            )).sort("system:time_start", False).limit(count)

            def metadata(image):
                return image.set("saaf_metadata", ee.Dictionary({
                    "scene_id": ee.String(f"{COLLECTION}/").cat(ee.String(image.get("system:index"))),
                    "timestamp": image.get("system:time_start"),
                    "cloud": image.get("CLOUDY_PIXEL_PERCENTAGE"),
                    "coverage": image.get("saaf_clear"), "stats": image.get("saaf_stats"),
                }))

            records = selected.map(metadata).aggregate_array("saaf_metadata").getInfo()
            scenes = tuple(Scene(
                scene_id=row["scene_id"],
                acquired_at=datetime.fromtimestamp(row["timestamp"] / 1000, timezone.utc),
                scene_cloud_pct=row["cloud"], farm_valid_fraction=row["coverage"],
                vegetation_fraction_of_valid=row["stats"].get("vegetation_mean"),
                ndvi=None if mode == "imagery" else NDVIStats(
                    mean=row["stats"]["NDVI_mean"], minimum=row["stats"]["NDVI_min"],
                    maximum=row["stats"]["NDVI_max"],
                ),
            ) for row in records if row["stats"].get("NDVI_mean") is not None)
            if not scenes:
                return SatelliteBatch(scenes=())
            if mode == "history":
                return SatelliteBatch(scenes=tuple(reversed(scenes)))

            bounds = boundary.polygon().bounds
            rectangle = ee.Geometry.Rectangle(list(bounds), proj="EPSG:4326", geodesic=False)
            pixels = image_bands(ee.Image(scenes[0].scene_id)).clip(area)
            if mode == "imagery":
                style = pixels.visualize(bands=["B4", "B3", "B2"], min=0, max=3500)
            else:
                style = pixels.select("NDVI").visualize(min=-1, max=1, palette=["313695", "ffffbf", "006837"])
            url = style.getThumbURL({"region": rectangle, "crs": "EPSG:4326", "dimensions": 512, "format": "png"})
            with urlopen(url, timeout=20) as stream:
                png = stream.read(2 * 1024 * 1024 + 1)
            if not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png) > 2 * 1024 * 1024:
                raise SatelliteFailure("provider_unavailable")
            return SatelliteBatch(scenes=scenes, preview=Preview(
                kind="true_color" if mode == "imagery" else "ndvi", bounds=bounds,
                data=base64.b64encode(png).decode("ascii"),
            ))
        except SatelliteFailure:
            raise
        except Exception as exc:
            raise _provider_error(exc) from exc


def _provider_error(exc: Exception) -> SatelliteFailure:
    # Classify privately; OAuth messages and thumbnail URLs never enter the public response.
    text = str(exc).lower()
    auth_markers = ("authenticate", "credential", "permission", "not registered", "unauthenticated", "invalid_grant",
                    "access denied", "forbidden", "401", "403", "earth engine api has not been used")
    status = "authentication_failed" if any(pattern in text for pattern in auth_markers) else "provider_unavailable"
    return SatelliteFailure(status)
