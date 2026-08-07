"""Shared infrastructure for the EIA API v2 MCP server.

Responsibilities:
- Load and validate the EIA API key (from the EIA_API_KEY environment variable).
- Build EIA API v2 URLs from a dataset "route" path.
- Serialize query parameters in the exact form the EIA API expects
  (``data[0]=``, ``facets[stateid][]=``, ``sort[0][column]=``, ...).
- Perform authenticated GET requests with TLS verification, a timeout, and a
  single retry on transient network errors.
- Normalize errors into actionable, structured dicts (never raw stack traces).

All calls are read-only against a public government API.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

EIA_API_BASE = "https://api.eia.gov/v2"
DEFAULT_TIMEOUT = 30.0
MAX_LENGTH = 5000  # EIA API hard cap on the `length` (page size) parameter.


class EIAConfigError(RuntimeError):
    """Raised when required configuration (e.g. the API key) is missing."""


def get_api_key() -> str:
    """Return the EIA API key from the environment.

    Raises:
        EIAConfigError: if EIA_API_KEY is unset or empty, with guidance on how
            to fix it.
    """
    key = os.getenv("EIA_API_KEY", "").strip()
    if not key:
        raise EIAConfigError(
            "EIA_API_KEY is not set. Add EIA_API_KEY=<your key> to a .env file "
            "in the project root, or export it in the environment. Request a "
            "free key at https://www.eia.gov/opendata/register.php"
        )
    return key


def normalize_route(route: str | None) -> str:
    """Normalize a dataset route path.

    Accepts values like ``"electricity/retail-sales"``, ``"/electricity/"``,
    ``"v2/electricity"`` or an empty string (the API root). Returns a clean
    slash-joined path with no leading/trailing slashes and no ``v2`` prefix.
    """
    if not route:
        return ""
    r = route.strip().strip("/")
    if r.startswith("v2/"):
        r = r[len("v2/"):]
    elif r == "v2":
        r = ""
    return r


def build_url(route: str | None, suffix: str = "") -> str:
    """Build a full EIA API v2 URL from a route path and optional suffix.

    Args:
        route: Dataset route, e.g. ``"electricity/retail-sales"`` ("" = root).
        suffix: Optional trailing segment such as ``"data"``, ``"facet"``, or
            ``"facet/stateid"``.
    """
    r = normalize_route(route)
    parts = [EIA_API_BASE]
    if r:
        parts.append(r)
    if suffix:
        parts.append(suffix.strip("/"))
    return "/".join(parts)


def encode_params(
    api_key: str,
    *,
    data: list[str] | None = None,
    facets: dict[str, list[str]] | None = None,
    frequency: str | None = None,
    start: str | None = None,
    end: str | None = None,
    sort: list[dict[str, str]] | None = None,
    length: int | None = None,
    offset: int | None = None,
) -> list[tuple[str, str]]:
    """Serialize data-query parameters into EIA's bracketed query-string form.

    The EIA API uses PHP-style bracketed array/object parameters. httpx encodes
    a list of ``(key, value)`` tuples faithfully, so we build that list here.

    Returns:
        A list of ``(key, value)`` string tuples suitable for httpx ``params=``.
    """
    params: list[tuple[str, str]] = [("api_key", api_key)]

    for i, col in enumerate(data or []):
        params.append((f"data[{i}]", str(col)))

    for facet_id, values in (facets or {}).items():
        # Allow a bare string value as a convenience for single-value filters.
        if isinstance(values, str):
            values = [values]
        for v in values:
            params.append((f"facets[{facet_id}][]", str(v)))

    if frequency:
        params.append(("frequency", str(frequency)))
    if start:
        params.append(("start", str(start)))
    if end:
        params.append(("end", str(end)))

    for i, s in enumerate(sort or []):
        col = s.get("column")
        direction = s.get("direction", "asc")
        if col:
            params.append((f"sort[{i}][column]", str(col)))
            params.append((f"sort[{i}][direction]", str(direction)))

    if length is not None:
        params.append(("length", str(length)))
    if offset is not None:
        params.append(("offset", str(offset)))

    return params


def _error(message: str, *, status: int | None = None, suggestion: str | None = None,
           detail: Any = None) -> dict[str, Any]:
    """Build a structured, LLM-friendly error payload (no stack traces)."""
    err: dict[str, Any] = {"error": message}
    if status is not None:
        err["status"] = status
    if suggestion:
        err["suggestion"] = suggestion
    if detail is not None:
        err["detail"] = detail
    return err


async def eia_get(url: str, params: list[tuple[str, str]]) -> dict[str, Any]:
    """Perform an authenticated GET against the EIA API with one retry.

    Args:
        url: Full request URL (see :func:`build_url`).
        params: Encoded query params (see :func:`encode_params`); must already
            include the ``api_key`` entry.

    Returns:
        On success: the parsed JSON body as a dict.
        On failure: a structured error dict with ``error`` and, where relevant,
        ``status``, ``suggestion``, and ``detail`` keys. Errors are returned
        (not raised) so tools can surface them directly to the caller.
    """
    last_exc: Exception | None = None
    for attempt in range(2):  # one initial try + one retry
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=True) as client:
                resp = await client.get(url, params=params)
        except httpx.TimeoutException as exc:
            last_exc = exc
            continue
        except httpx.TransportError as exc:
            last_exc = exc
            continue

        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                return _error(
                    "EIA API returned a non-JSON response.",
                    status=resp.status_code,
                    detail=resp.text[:500],
                )

        # Map common EIA/HTTP errors to actionable guidance.
        detail: Any
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text[:500]

        if resp.status_code in (401, 403):
            return _error(
                "Authentication failed with the EIA API.",
                status=resp.status_code,
                suggestion="Verify EIA_API_KEY is correct and active.",
                detail=detail,
            )
        if resp.status_code == 404:
            return _error(
                "Route not found on the EIA API.",
                status=resp.status_code,
                suggestion=(
                    "Use eia_browse_routes to discover valid child routes for "
                    "this path."
                ),
                detail=detail,
            )
        if resp.status_code == 429:
            return _error(
                "Rate limited by the EIA API.",
                status=resp.status_code,
                suggestion="Wait and retry with a smaller `length` or fewer requests.",
                detail=detail,
            )
        return _error(
            f"EIA API request failed with HTTP {resp.status_code}.",
            status=resp.status_code,
            detail=detail,
        )

    return _error(
        "Network error contacting the EIA API after one retry.",
        suggestion="Confirm outbound access to api.eia.gov is permitted.",
        detail=str(last_exc) if last_exc else None,
    )


async def eia_request(route: str | None, suffix: str = "", *,
                      extra_params: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    """Convenience wrapper: resolve key, build URL, attach api_key, GET.

    Used by the metadata/facet tools that only need the api_key plus an optional
    set of pre-encoded params. Returns a structured error dict if the API key is
    missing.
    """
    try:
        api_key = get_api_key()
    except EIAConfigError as exc:
        return _error(str(exc), suggestion="Set the EIA_API_KEY environment variable.")

    url = build_url(route, suffix)
    params: list[tuple[str, str]] = [("api_key", api_key)]
    if extra_params:
        params.extend(extra_params)
    return await eia_get(url, params)
