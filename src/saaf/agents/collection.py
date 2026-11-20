"""Collect pickup details and confirm a simulated SQLite request."""

import re
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

from saaf.collection.commands import REQUEST_ID, confirmation_action, pickup_quantity
from saaf.collection.models import MAX_QUANTITY_KG, CollectionResult, PickupDraft
from saaf.collection.repository import CollectionRepository
from saaf.farms import FarmRepository

from .tools import get_farm_profile

_RIYADH = timezone(timedelta(hours=3))
_LABEL = "محاكاة فقط. لا يترتب على الطلب استلام ميداني."
_TRACKING = re.compile(r"متابعة|تتبع|حالة الطلب|طلباتي|طلبات الجمع|طلبات الاستلام")
_CANCEL = re.compile(r"^(?:إلغاء|الغاء|ألغِ|ألغ|الغ)\s+(?:الطلب\s+)?", re.IGNORECASE)
_STATUS_AR = {"confirmed": "مؤكد في المحاكاة", "cancelled": "ملغى في المحاكاة"}


def _next_pickup(now: datetime) -> date:
    pickup = now.astimezone(_RIYADH).date() + timedelta(days=1)
    while pickup.weekday() not in {0, 2, 5}:
        pickup += timedelta(days=1)
    return pickup


class CollectionAgent:
    def __init__(
        self, farms: FarmRepository, requests: CollectionRepository,
        *, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.farms = farms
        self.requests = requests
        self.clock = clock

    def plan_collection(
        self, query: str, farm_id: str | None, draft: PickupDraft | None = None,
        *, continuing: bool = False,
    ) -> CollectionResult:
        action = confirmation_action(query)
        profile = get_farm_profile(self.farms, farm_id)
        if profile is None:
            return CollectionResult(
                status="needs_input", answer_ar=f"أرسل معرّف مزرعة مسجلة للمتابعة. {_LABEL}",
                missing_information=("معرّف مزرعة مسجلة",),
            )
        annual = profile.est_residue_kg_per_year

        def result(status, message, **fields):
            return CollectionResult(
                status=status, answer_ar=f"{message} التقدير السنوي للمخلفات: {annual} كجم. {_LABEL}",
                estimated_annual_residue_kg=annual, **fields,
            )

        if draft and draft.farm_id != profile.farm_id:
            draft = None
        if action == "decline":
            return result("ok", "أُغلقت المسودة.")
        if action == "confirm":
            if draft is None:
                return result("needs_input", "لا توجد مسودة لهذه المزرعة. أرسل كمية جديدة بالكيلوغرام.",
                              missing_information=("كمية الاستلام بالكيلوغرام",))
            draft = PickupDraft.model_validate(draft.model_dump())
            now = self.clock()
            if draft.pickup_date != _next_pickup(now):
                return result("needs_input", "الموعد المقترح لم يعد صالحاً. أرسل الكمية لاقتراح موعد جديد.",
                              missing_information=("كمية الاستلام بالكيلوغرام",))
            request = self.requests.confirm(draft, now.astimezone(timezone.utc))
            return result(
                "ok", f"الطلب {request.request_id}: {_STATUS_AR[request.status]} لكمية "
                f"{request.requested_quantity_kg} كجم بتاريخ {request.pickup_date}.", request=request,
            )

        matches = {match.group().upper() for match in REQUEST_ID.finditer(query)}
        if len(matches) > 1:
            return result("needs_input", "أرسل رقم طلب واحد للمتابعة.", draft=draft,
                          missing_information=("رقم طلب واحد",))
        match = REQUEST_ID.search(query)
        if match:
            request_id = match.group().upper()
            request = (
                self.requests.cancel(request_id, farm_id=profile.farm_id)
                if _CANCEL.match(query.strip()) and REQUEST_ID.fullmatch(_CANCEL.sub("", query.strip(), count=1))
                else self.requests.get(request_id, farm_id=profile.farm_id)
            )
            if request is None:
                return result("not_found", "لم أجد هذا الطلب في المزرعة المحددة.", draft=draft)
            return result(
                "ok", f"الطلب {request.request_id}: {_STATUS_AR[request.status]}، "
                f"{request.requested_quantity_kg} كجم، {request.pickup_date}.", request=request, draft=draft,
            )
        if _TRACKING.search(query):
            if "رقم" in query or "حالة الطلب" in query or "تتبع" in query:
                return result("needs_input", "أرسل رقم طلب الجمع للمتابعة.", draft=draft,
                              missing_information=("رقم الطلب",))
            requests = tuple(self.requests.list(farm_id=profile.farm_id))
            summary = "، ".join(f"{item.request_id} ({_STATUS_AR[item.status]})" for item in requests)
            return result("ok", summary or "لا توجد طلبات لهذه المزرعة.", requests=requests, draft=draft)

        quantity = pickup_quantity(query, allow_bare=continuing)
        if quantity is None or not 0 < quantity <= MAX_QUANTITY_KG:
            return result(
                "needs_input", "أرسل الكمية الفعلية المراد استلامها كعدد صحيح موجب بالكيلوغرام.",
                missing_information=("كمية الاستلام بالكيلوغرام",),
            )
        pickup = _next_pickup(self.clock())
        draft = PickupDraft(farm_id=profile.farm_id, requested_quantity_kg=quantity, pickup_date=pickup)
        return result(
            "awaiting_confirmation", f"الموعد المقترح حسب التوفر المحاكى: {pickup}. "
            f"كمية الاستلام المدخلة: {quantity} كجم. اكتب «أؤكد» لحفظ الطلب أو «إلغاء المسودة» لرفضه.",
            draft=draft,
        )
