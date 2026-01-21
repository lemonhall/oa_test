from __future__ import annotations


def is_iso_date(value: str) -> bool:
    if len(value) != 10:
        return False
    return value[4] == "-" and value[7] == "-" and value[:4].isdigit() and value[5:7].isdigit() and value[8:10].isdigit()


def is_hhmm(value: str) -> bool:
    if len(value) != 5:
        return False
    return value[2] == ":" and value[:2].isdigit() and value[3:5].isdigit()

