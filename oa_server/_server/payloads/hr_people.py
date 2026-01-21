from __future__ import annotations

from typing import Any

from .common import is_iso_date
from ..jsonutil import json_dumps


def try_build(
    request_type: str,
    *,
    title: str,
    body: str,
    payload: dict[str, Any],
) -> tuple[bool, str, str, str | None]:
    if request_type == "onboarding":
        name = str(payload.get("name", "")).strip()
        start_date = str(payload.get("start_date", "")).strip()
        dept = str(payload.get("dept", "")).strip()
        position = str(payload.get("position", "")).strip()
        if not name or not start_date or not dept or not position:
            raise ValueError("invalid_payload")
        if not is_iso_date(start_date):
            raise ValueError("invalid_payload")
        if not title:
            title = f"入职：{name}（{start_date}）"
        if not body:
            body = f"部门：{dept}\n岗位：{position}"
        payload = dict(payload)
        payload["name"] = name
        payload["start_date"] = start_date
        payload["dept"] = dept
        payload["position"] = position
        return True, title, body, json_dumps(payload)

    if request_type == "probation":
        name = str(payload.get("name", "")).strip()
        start_date = str(payload.get("start_date", "")).strip()
        end_date = str(payload.get("end_date", "")).strip()
        result = str(payload.get("result", "")).strip().lower()
        comment = str(payload.get("comment", "")).strip()
        if result in {"通过", "pass", "yes", "ok"}:
            result = "pass"
        if result in {"不通过", "fail", "no"}:
            result = "fail"
        if not name or not start_date or not end_date or result not in {"pass", "fail"}:
            raise ValueError("invalid_payload")
        if not is_iso_date(start_date) or not is_iso_date(end_date):
            raise ValueError("invalid_payload")
        result_text = "通过" if result == "pass" else "不通过"
        if not title:
            title = f"转正：{name} {start_date}~{end_date}"
        if not body:
            body = f"结果：{result_text}" + (f"\n说明：{comment}" if comment else "")
        payload = dict(payload)
        payload["name"] = name
        payload["start_date"] = start_date
        payload["end_date"] = end_date
        payload["result"] = result
        payload["comment"] = comment
        return True, title, body, json_dumps(payload)

    if request_type == "resignation":
        name = str(payload.get("name", "")).strip()
        last_day = str(payload.get("last_day", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        handover = str(payload.get("handover", "")).strip()
        if not name or not last_day or not reason:
            raise ValueError("invalid_payload")
        if not is_iso_date(last_day):
            raise ValueError("invalid_payload")
        if not title:
            title = f"离职：{name}（最后工作日 {last_day}）"
        if not body:
            body = f"原因：{reason}" + (f"\n交接：{handover}" if handover else "")
        payload = dict(payload)
        payload["name"] = name
        payload["last_day"] = last_day
        payload["reason"] = reason
        payload["handover"] = handover
        return True, title, body, json_dumps(payload)

    if request_type == "job_transfer":
        name = str(payload.get("name", "")).strip()
        from_dept = str(payload.get("from_dept", "")).strip()
        to_dept = str(payload.get("to_dept", "")).strip()
        effective_date = str(payload.get("effective_date", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        if not name or not from_dept or not to_dept or not effective_date:
            raise ValueError("invalid_payload")
        if not is_iso_date(effective_date):
            raise ValueError("invalid_payload")
        if not title:
            title = f"调岗：{name} {from_dept}→{to_dept}（{effective_date}）"
        if not body:
            body = f"原因：{reason}" if reason else "原因：调岗"
        payload = dict(payload)
        payload["name"] = name
        payload["from_dept"] = from_dept
        payload["to_dept"] = to_dept
        payload["effective_date"] = effective_date
        payload["reason"] = reason
        return True, title, body, json_dumps(payload)

    if request_type == "salary_adjustment":
        name = str(payload.get("name", "")).strip()
        effective_date = str(payload.get("effective_date", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        from_salary_raw = payload.get("from_salary", None)
        to_salary_raw = payload.get("to_salary", None)
        try:
            from_salary = float(from_salary_raw)
        except Exception:
            from_salary = 0.0
        try:
            to_salary = float(to_salary_raw)
        except Exception:
            to_salary = 0.0
        if not name or not effective_date or from_salary <= 0 or to_salary <= 0:
            raise ValueError("invalid_payload")
        if not is_iso_date(effective_date):
            raise ValueError("invalid_payload")
        if not title:
            title = f"调薪：{name} {from_salary:g}→{to_salary:g}（{effective_date}）"
        if not body:
            body = f"原因：{reason}" if reason else "原因：调薪"
        payload = dict(payload)
        payload["name"] = name
        payload["effective_date"] = effective_date
        payload["from_salary"] = from_salary
        payload["to_salary"] = to_salary
        payload["reason"] = reason
        return True, title, body, json_dumps(payload)

    return False, title, body, None

