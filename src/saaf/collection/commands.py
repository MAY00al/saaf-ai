"""Recognize unambiguous demo pickup inputs."""

import re

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_CONFIRM = re.compile(r"(?:أؤكد(?: الطلب)?|اؤكد(?: الطلب)?|أكد(?: الطلب)?|اكد(?: الطلب)?|تأكيد(?: الطلب)?|تاكيد(?: الطلب)?|confirm)")
_DECLINE = re.compile(r"(?:لا|لا أؤكد|لا اؤكد|رفض|إلغاء المسودة|الغاء المسودة)")
REQUEST_ID = re.compile(r"(?<![\w-])COL-[A-F0-9]{32}(?![\w-])", re.IGNORECASE | re.ASCII)
_QUANTITY = re.compile(
    r"(?<![\w.,٫٬+\-−])([+−-]?\s*[0-9]+)\s*(?:كيلوغرام(?:ات)?|كيلوجرام(?:ات)?|كجم|كغ|كيلو(?:\s+غرام)?|kg)(?!\w)",
    re.IGNORECASE,
)
_BARE = re.compile(r"[0-9]+")


def confirmation_action(query: str) -> str | None:
    text = query.strip().rstrip(".!").strip().lower()
    if _CONFIRM.fullmatch(text):
        return "confirm"
    if _DECLINE.fullmatch(text):
        return "decline"
    return None


def pickup_quantity(query: str, *, allow_bare: bool) -> int | None:
    text = query.translate(_DIGITS).strip()
    if re.search(r"[0-9][.,٫٬]\s+[0-9]", text):
        return None
    matches = _QUANTITY.findall(text)
    if not matches and allow_bare and _BARE.fullmatch(text):
        matches = [text]
    if len(matches) != 1:
        return None
    digits = "".join(matches[0].split())
    if not digits.isascii() or not digits.isdecimal() or len(digits) > 19:
        return None
    return int(digits)


def has_quantity_input(query: str) -> bool:
    return bool(re.search(r"[0-9]", query.translate(_DIGITS)) and re.search(
        r"كيلو|كجم|كغ|\bkg\b|طن|^\s*[+\-−]?[0-9٠-٩۰-۹.,٫٬]+\s*$", query, re.IGNORECASE,
    ))
