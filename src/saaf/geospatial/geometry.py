"""Validate GeoJSON polygon topology and calculate geodesic area."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pyproj import Geod
from shapely.geometry import Point, Polygon, mapping
from shapely.geometry.polygon import orient

Longitude = Annotated[float, Field(strict=True, ge=-180, le=180)]
Latitude = Annotated[float, Field(strict=True, ge=-90, le=90)]
Position = tuple[Longitude, Latitude]
_GEOD = Geod(ellps="WGS84")


class GeoPolygon(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    type: Literal["Polygon"]
    coordinates: tuple[tuple[Position, ...], ...] = Field(min_length=1)

    def polygon(self) -> Polygon:
        return Polygon(self.coordinates[0], self.coordinates[1:])

    @model_validator(mode="after")
    def validate_geometry(self) -> "GeoPolygon":
        if sum(map(len, self.coordinates)) > 5000:
            raise ValueError("boundary exceeds 5000 positions")
        for ring in self.coordinates:
            if len(ring) < 4 or ring[0] != ring[-1] or len(set(ring[:-1])) < 3:
                raise ValueError("each ring must be closed with at least three distinct positions")
        polygon = self.polygon()
        west, _, east, _ = polygon.bounds
        if east - west >= 180:
            raise ValueError("antimeridian-crossing boundaries are not supported")
        if not polygon.is_valid or polygon.area <= 0 or self.area_ha() <= 0:
            raise ValueError("polygon topology or area is invalid")
        return self

    def area_ha(self) -> float:
        area_m2, _ = _GEOD.geometry_area_perimeter(orient(self.polygon(), sign=1))
        return abs(area_m2) / 10_000

    def ee_geometry(self) -> dict:
        return mapping(orient(self.polygon(), sign=1))


class FarmBoundaryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    boundary: GeoPolygon
    latitude: Latitude | None = None
    longitude: Longitude | None = None

    @model_validator(mode="after")
    def validate_location(self) -> "FarmBoundaryInput":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("provide latitude and longitude together")
        if self.latitude is not None and not self.boundary.polygon().covers(Point(self.longitude, self.latitude)):
            raise ValueError("provided farm point must be inside or on the boundary")
        return self
