"""
Jaeger query helpers for the observability integration tests.

They use Jaeger's v3 query API (/api/v3/...), which every Jaeger 2.x serves.
Jaeger 2.22 removed the older /api/services and /api/traces endpoints, so
tests written against those returned 404 on a current image.

Traces come back in the shape the older API used, which the tests assert on:
    [{"traceID": ..., "spans": [{"operationName": ..., "tags": [{"key": ..., "value": ...}]}]}]
newest trace first, spans in start order (a trace's root first).
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests


def services(jaeger_url: str) -> List[str]:
    """Names of the services Jaeger has traces for."""
    resp = requests.get(f"{jaeger_url}/api/v3/services", timeout=5)
    assert resp.status_code == 200, f"Jaeger API error: {resp.status_code} {resp.text[:200]}"
    return resp.json().get("services", [])


def operations(jaeger_url: str, service: str) -> List[str]:
    """Operation (span) names Jaeger has recorded for a service."""
    resp = requests.get(f"{jaeger_url}/api/v3/operations", params={"service": service}, timeout=5)
    assert resp.status_code == 200, f"Jaeger API error: {resp.status_code} {resp.text[:200]}"
    return [op["name"] for op in resp.json().get("operations", [])]


def find_traces(
    jaeger_url: str,
    service: str,
    operation: Optional[str] = None,
    limit: int = 20,
    lookback: timedelta = timedelta(hours=1),
) -> List[Dict[str, Any]]:
    """Traces of a service (optionally containing an operation) from the last hour.

    Returns [] when there are none; any other API failure is an assertion error.
    """
    now = datetime.now(timezone.utc)
    params = {
        "query.service_name": service,
        "query.start_time_min": _rfc3339(now - lookback),
        # A little ahead of now, in case the test host's clock trails Jaeger's.
        "query.start_time_max": _rfc3339(now + timedelta(minutes=1)),
        "query.search_depth": limit,
    }
    if operation:
        params["query.operation_name"] = operation

    resp = requests.get(f"{jaeger_url}/api/v3/traces", params=params, timeout=10)
    if resp.status_code == 404 and _is_no_traces(resp):
        return []
    assert resp.status_code == 200, f"Jaeger API error: {resp.status_code} {resp.text[:200]}"
    return _group_by_trace(resp.json().get("result", {}).get("resourceSpans", []))


def _rfc3339(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def _is_no_traces(resp: requests.Response) -> bool:
    """Jaeger answers a search with no results as a JSON 404; a missing
    endpoint is a plain-text 404, which must still fail the test."""
    try:
        return resp.json().get("error", {}).get("message") == "No traces found"
    except ValueError:
        return False


def _group_by_trace(resource_spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    traces: Dict[str, List[Dict[str, Any]]] = {}
    for resource in resource_spans:
        for scope in resource.get("scopeSpans", []):
            for span in scope.get("spans", []):
                traces.setdefault(span["traceId"], []).append({
                    "traceID": span["traceId"],
                    "spanID": span["spanId"],
                    "operationName": span["name"],
                    "startTime": int(span.get("startTimeUnixNano", 0)),
                    "tags": [
                        {"key": attr["key"], "value": _attribute_value(attr.get("value", {}))}
                        for attr in span.get("attributes", [])
                    ],
                })

    result = []
    for trace_id, spans in traces.items():
        spans.sort(key=lambda s: s["startTime"])
        result.append({"traceID": trace_id, "spans": spans})
    result.sort(key=lambda t: t["spans"][0]["startTime"], reverse=True)
    return result


def _attribute_value(value: Dict[str, Any]) -> Any:
    """An OTLP JSON AnyValue as a plain Python value."""
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        return int(value["intValue"])  # int64 arrives as a JSON string
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "boolValue" in value:
        return value["boolValue"]
    if "arrayValue" in value:
        return [_attribute_value(v) for v in value["arrayValue"].get("values", [])]
    return None
