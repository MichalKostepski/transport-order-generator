from __future__ import annotations

import re
from typing import Dict


EMPTY_DRIVER: Dict[str, str] = {
    "full_name": "",
    "id_card": "",
    "pesel": "",
    "truck_registration": "",
    "trailer_registration": "",
    "phone": "",
}


def _clean(value: str) -> str:
    value = value.strip().strip("-–—•;,")
    return re.sub(r"\s+", " ", value)


def _value_after_label(line: str) -> str:
    parts = re.split(r"\s*[:=-]\s*", line, maxsplit=1)
    return _clean(parts[1]) if len(parts) == 2 else ""


def parse_driver_text(text: str) -> Dict[str, str]:
    """Parse driver details pasted from WhatsApp/Messenger/SMS.

    The parser intentionally accepts many Polish label variants and also tries
    to recognize PESEL, phone numbers and a name from unlabeled lines.
    """
    result = dict(EMPTY_DRIVER)
    raw_lines = [_clean(line) for line in text.replace("\t", " ").splitlines()]
    lines = [line for line in raw_lines if line]

    label_patterns = {
        "full_name": re.compile(r"^(kierowca|imi[eę]\s*i\s*nazwisko|imi[eę]\s*nazwisko|nazwisko)", re.I),
        "id_card": re.compile(r"^(seria.*d\.?\s*os|dow[oó]d|nr\s*dowodu|dokument)", re.I),
        "pesel": re.compile(r"^pesel", re.I),
        "truck_registration": re.compile(r"^(rejestracja\s*(pojazdu|auta|ci[aą]gnika)|pojazd|auto|ci[aą]gnik|samoch[oó]d)", re.I),
        "trailer_registration": re.compile(r"^(rejestracja\s*(naczepy|przyczepy)|naczepa|przyczepa)", re.I),
        "phone": re.compile(r"^(nr\s*)?(telefonu|telefon|tel\.?|kom\.?)", re.I),
    }

    unlabeled: list[str] = []
    for line in lines:
        matched = False
        for key, pattern in label_patterns.items():
            if pattern.search(line):
                value = _value_after_label(line)
                if not value:
                    value = _clean(pattern.sub("", line, count=1))
                if value:
                    result[key] = value
                matched = True
                break
        if not matched:
            unlabeled.append(line)

    # Strong pattern recognizers for information written without labels.
    if not result["pesel"]:
        match = re.search(r"(?<!\d)(\d{11})(?!\d)", text.replace(" ", ""))
        if match:
            result["pesel"] = match.group(1)

    if not result["phone"]:
        phone_candidates = re.findall(r"(?<!\d)(?:\+48[\s-]?)?(?:\d[\s-]?){9}(?!\d)", text)
        for candidate in phone_candidates:
            digits = re.sub(r"\D", "", candidate)
            if len(digits) in (9, 11) and digits != result["pesel"]:
                result["phone"] = _clean(candidate)
                break

    if not result["full_name"]:
        for line in unlabeled:
            no_digits = not re.search(r"\d", line)
            words = re.findall(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż-]+", line)
            if no_digits and 2 <= len(words) <= 5:
                result["full_name"] = " ".join(words)
                break

    # If two obvious registration-like unlabeled values remain, use their order.
    reg_candidates: list[str] = []
    for line in unlabeled:
        compact = re.sub(r"[\s-]", "", line).upper()
        if re.fullmatch(r"[A-Z0-9]{5,10}", compact) and re.search(r"[A-Z]", compact) and re.search(r"\d", compact):
            if compact not in reg_candidates and compact != result["id_card"].replace(" ", "").upper():
                reg_candidates.append(compact)
    if not result["truck_registration"] and reg_candidates:
        result["truck_registration"] = reg_candidates.pop(0)
    if not result["trailer_registration"] and reg_candidates:
        result["trailer_registration"] = reg_candidates.pop(0)

    for key, value in result.items():
        result[key] = _clean(value)
    return result
