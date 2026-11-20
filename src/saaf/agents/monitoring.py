"""Review a local date-palm image prediction before changing a demo farm."""

from pathlib import Path
from uuid import uuid4

from saaf.farms import FarmRepository
from saaf.farms.models import RESIDUE_KG_PER_PALM_PER_YEAR
from saaf.monitoring.inference import (
    Detector, InvalidImage, ModelUnavailable, MonitoringSettings, YoloDetector, annotate_image, load_image,
)
from saaf.monitoring.models import CountReview, Detection, MonitoringResult, PalmObservation
from saaf.monitoring.repository import apply_count_review

from .tools import get_farm_profile


class MonitoringAgent:
    def __init__(
        self, farms: FarmRepository, settings: MonitoringSettings, detector: Detector | None = None,
    ) -> None:
        self.farms = farms
        self.settings = settings
        self.detector = detector if detector is not None else YoloDetector(settings.weights)

    def inspect_palms(
        self, farm_id: str | None, image: Path | None, *, whole_farm: bool = False,
    ) -> MonitoringResult:
        whole_farm = whole_farm is True
        if image is None:
            return MonitoringResult(status="needs_input", error_code="missing_image",
                                    answer_ar="أرفق صورة جوية محلية بصيغة JPEG أو PNG.")
        profile = get_farm_profile(self.farms, farm_id)
        if profile is None:
            return MonitoringResult(status="needs_input", answer_ar="أرسل معرّف مزرعة مسجلة لربط الرصد بها.")
        try:
            pixels, digest = load_image(image)
        except InvalidImage:
            return MonitoringResult(status="needs_input", error_code="invalid_image",
                                    answer_ar="الصورة غير صالحة. اختر ملف JPEG أو PNG محلياً قابلاً للقراءة.")
        except ImportError:
            return MonitoringResult(status="unavailable", error_code="inference_failed",
                                    answer_ar="ثبّت ملحق الرؤية المحلي لقراءة الصور.")
        try:
            model_id = self.detector.model_id
            raw = self.detector.predict(pixels, self.settings)
            detections = tuple(
                Detection.model_validate(item.model_dump()) for item in raw
            )
            width, height = pixels.size
            if any(item.xyxy[2] > width or item.xyxy[3] > height for item in detections):
                raise ValueError("bounding box exceeds image dimensions")
            accepted = tuple(item for item in detections if item.confidence >= self.settings.confidence)
            observation_id = f"OBS-{uuid4().hex.upper()}"
            annotated = self.settings.output_dir / f"{observation_id}.png"
            annotate_image(pixels, accepted, annotated)
        except ModelUnavailable:
            return MonitoringResult(status="unavailable", error_code="missing_model",
                                    answer_ar="أوزان رصد نخيل التمر غير متاحة. اضبط مسار الأوزان المدرّبة محلياً.")
        except Exception:
            return MonitoringResult(status="unavailable", error_code="inference_failed",
                                    answer_ar="تعذّر تحليل الصورة أو حفظ الصورة المعلّمة.")

        count = len(accepted)
        estimated = count * RESIDUE_KG_PER_PALM_PER_YEAR
        observation = PalmObservation(
            observation_id=observation_id, farm_id=profile.farm_id, image_sha256=digest,
            model_id=model_id, annotated_image=str(annotated), image_size=pixels.size,
            confidence_threshold=self.settings.confidence, detections=accepted,
            detected_count=count, estimated_annual_waste_kg=estimated, whole_farm_attested=whole_farm,
        )
        answer = (
            f"تنبؤ النموذج في الصورة: {count} نخلة. التقدير السنوي للنخيل المرصود: {estimated} كجم. "
            "ملف المزرعة محاكًى. ربط الصورة بالملف يعتمد على اختيارك، والعدّ يخص الصورة فقط."
        )
        if not whole_farm:
            return MonitoringResult(status="ok", answer_ar=answer, observation=observation)
        if len(detections) >= self.settings.max_detections:
            return MonitoringResult(status="ok", observation=observation,
                                    answer_ar=answer + " بلغ الكشف حدّه الأقصى، لذا لا يصلح لتحديث السجل.")
        review = CountReview(
            observation_id=observation_id, farm_id=profile.farm_id, predicted_count=count,
            previous_count=profile.palm_count, previous_observation_id=profile.provenance.palm_count_observation_id,
            model_id=model_id, image_sha256=digest,
        )
        return MonitoringResult(
            status="awaiting_confirmation", observation=observation, pending_review=review,
            answer_ar=answer + f" العدد المسجل حالياً {profile.palm_count}. "
            "راجع الصورة المعلّمة واكتب «أؤكد تحديث العدد» لتخزين هذا التنبؤ.",
        )

    def confirm_count(self, farm_id: str | None, review: CountReview | None) -> MonitoringResult:
        if not review or review.farm_id != farm_id:
            return MonitoringResult(status="needs_input", answer_ar="لا توجد مراجعة عدّ معلّقة لهذه المزرعة.")
        if not apply_count_review(self.farms, review):
            return MonitoringResult(status="needs_input", error_code="stale_review",
                                    answer_ar="تغيّر السجل منذ المراجعة. أعد رصد الصورة قبل التحديث.")
        return MonitoringResult(
            status="ok", updated_farm_id=review.farm_id,
            answer_ar="حُفظ العدد في سجل المزرعة المحاكاة كمصدره تنبؤ نموذج بعد تأكيدك.",
        )
