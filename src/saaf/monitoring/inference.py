"""Validate local aerial image files and run a trusted YOLO detector on CPU."""

import os
from functools import cached_property
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from .models import Detection

_PALM_LABELS = {"date_palm", "date_palm_crown", "palm_tree"}
_MAX_BYTES = 40 * 1024 * 1024
_MAX_PIXELS = 40_000_000


class InvalidImage(ValueError):
    pass


class ModelUnavailable(RuntimeError):
    pass


class MonitoringSettings(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    weights: Path | None = None
    confidence: float = Field(default=0.25, gt=0, le=1)
    image_size: int = Field(default=640, ge=32, le=4096, multiple_of=32)
    max_detections: int = Field(default=3000, ge=1, le=10000)
    output_dir: Path = Path("var/monitoring")

    @classmethod
    def from_environment(cls) -> "MonitoringSettings":
        return cls(
            weights=os.getenv("SAAF_PALM_WEIGHTS") or None,
            confidence=os.getenv("SAAF_PALM_CONFIDENCE") or 0.25,
            image_size=os.getenv("SAAF_PALM_IMAGE_SIZE") or 640,
            max_detections=os.getenv("SAAF_PALM_MAX_DETECTIONS") or 3000,
            output_dir=os.getenv("SAAF_PALM_OUTPUT_DIR") or "var/monitoring",
        )


class Detector(Protocol):
    @property
    def model_id(self) -> str: ...
    def predict(self, image, settings: MonitoringSettings) -> tuple[Detection, ...]: ...


def load_image(path: Path):
    from PIL import Image, ImageOps

    try:
        if not path.is_file():
            raise InvalidImage("image must be a local regular file")
        with path.open("rb") as stream:
            content = stream.read(_MAX_BYTES + 1)
        if len(content) > _MAX_BYTES:
            raise InvalidImage("image file is too large")
        with Image.open(BytesIO(content), formats=("JPEG", "PNG")) as source:
            width, height = source.size
            # Pillow's ordinary JPEG reader may not expose frame metadata.
            if min(width, height) < 32 or width * height > _MAX_PIXELS or getattr(source, "n_frames", 1) != 1:
                raise InvalidImage("unsupported image dimensions or frame count")
            source.load()
            return ImageOps.exif_transpose(source).convert("RGB"), sha256(content).hexdigest()
    except (OSError, Image.DecompressionBombError) as exc:
        raise InvalidImage("expected a decodable JPEG or PNG") from exc


class YoloDetector:
    def __init__(self, weights: Path | None) -> None:
        self.weights = weights

    @cached_property
    def _loaded(self):
        if self.weights is None or self.weights.suffix.lower() != ".pt" or not self.weights.is_file():
            raise ModelUnavailable("configure local palm checkpoint")
        try:
            from ultralytics import YOLO

            with self.weights.open("rb") as stream:
                digest = sha256()
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            model = YOLO(str(self.weights.resolve()), task="detect")
            ids = [int(index) for index, label in model.names.items()
                   if label.strip().lower().replace("-", "_").replace(" ", "_") in _PALM_LABELS]
            if not ids or model.task != "detect":
                raise ModelUnavailable("checkpoint has no supported date palm detection class")
            return model, ids, f"{self.weights.name}@sha256:{digest.hexdigest()}"
        except Exception as exc:
            raise ModelUnavailable("date palm checkpoint is unavailable") from exc

    @property
    def model_id(self) -> str:
        return self._loaded[2]

    def predict(self, image, settings: MonitoringSettings) -> tuple[Detection, ...]:
        model, ids, _ = self._loaded
        result, = model.predict(
            source=image, device="cpu", conf=settings.confidence, imgsz=settings.image_size,
            max_det=settings.max_detections, classes=ids, agnostic_nms=True,
            save=False, verbose=False,
        )
        boxes = result.boxes
        if boxes is None:
            raise RuntimeError("checkpoint did not return detection boxes")
        return tuple(
            Detection(confidence=score, xyxy=tuple(box))
            for box, score in zip(boxes.xyxy.cpu().tolist(), boxes.conf.cpu().tolist(), strict=True)
        )


def annotate_image(image, detections: tuple[Detection, ...], path: Path) -> None:
    from PIL import ImageDraw

    canvas = image.copy()
    draw = ImageDraw.Draw(canvas)
    for detection in detections:
        x1, y1, _, _ = detection.xyxy
        draw.rectangle(detection.xyxy, outline="#00ff72", width=3)
        draw.text((x1 + 3, y1 + 3), f"Date palm {detection.confidence:.2f}", fill="#00ff72", stroke_width=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, format="PNG")
