"""Normalize Arabic input for deterministic phrase matching."""

import re
import unicodedata

_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670]")
_LETTERS = str.maketrans("أإآٱىةؤئـ", "اااايهوي ")


def normalize(query: str) -> str:
    text = unicodedata.normalize("NFKC", query).lower()
    return " ".join(_DIACRITICS.sub("", text).translate(_LETTERS).split())
