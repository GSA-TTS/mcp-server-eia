"""eia_get_data: query time-series data from any EIA API v2 dataset.

This is the workhorse tool. Point it at a leaf dataset route (discover valid
routes, columns, facets, and frequency with eia_browse_routes /
eia_list_facets / eia_get_facet_options) and it returns structured rows plus
pagination metadata so the caller can page through large result sets.
"""

from typing import Annotated, Any

from pydantic import Field

from eia_mcp.utils import (
    MAX_LENGTH,
    EIAConfigError,
    build_url,
    eia_get,
    encode_params,
    get_api_key,
)


def register(mcp):
    @mcp.tool(
        annotations={
            "title": "Query EIA dataset data",
            "readOnlyHint": True,
            "openWorldHint": True,
        }
    )
    async def eia_get_data(
        route: Annotated[
            str,
            Field(
                description=(
                    "Leaf dataset route to query, e.g. "
                    "'electricity/retail-sales'. Discover with eia_browse_routes."
                ),
                min_length=1,
            ),
        ],
        data: Annotated[
            list[str],
            Field(
                description=(
                    "Data columns to return, e.g. ['revenue', 'sales', 'price']. "
                    "Valid columns are listed in the dataset metadata from "
                    "eia_browse_routes (the 'data_columns' field). At least one "
                    "column is usually required for the API to return values."
                ),
            ),
        ],
        facets: Annotated[
            dict[str, list[str]] | None,
            Field(
                default=None,
                description=(
                    "Facet filters as {facet_id: [values]}, e.g. "
                    "{'stateid': ['CA'], 'sectorid': ['RES']}. Discover facet "
                    "ids with eia_list_facets and valid values with "
                    "eia_get_facet_options."
                ),
            ),
        ] = None,
        frequency: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Data frequency id, e.g. 'monthly', 'annual', 'hourly'. "
                    "Valid values are in the dataset 'frequencies' metadata."
                ),
            ),
        ] = None,
        start: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Inclusive start period. Format must match the dataset "
                    "frequency, e.g. '2020' (annual), '2020-01' (monthly), "
                    "'2020-01-01' (daily), '2020-01-01T00' (hourly)."
                ),
            ),
        ] = None,
        end: Annotated[
            str | None,
            Field(
                default=None,
                description="Inclusive end period, same format as `start`.",
            ),
        ] = None,
        sort: Annotated[
            list[dict[str, str]] | None,
            Field(
                default=None,
                description=(
                    "Sort spec, e.g. [{'column': 'period', 'direction': 'desc'}]. "
                    "'direction' is 'asc' or 'desc'."
                ),
            ),
        ] = None,
        length: Annotated[
            int,
            Field(
                default=100,
                ge=1,
                le=MAX_LENGTH,
                description=(
                    f"Max rows to return (page size). 1..{MAX_LENGTH}. Keep small "
                    "for exploration; increase to page through data."
                ),
            ),
        ] = 100,
        offset: Annotated[
            int,
            Field(
                default=0,
                ge=0,
                description="Row offset for pagination. Use `next_offset` from a prior call.",
            ),
        ] = 0,
    ) -> dict[str, Any]:
        """Query rows from an EIA dataset with filtering, sorting, and paging.

        Returns a structured payload:
        {
          "route", "frequency", "description",
          "total": <total rows matching the query on the server>,
          "offset", "length", "returned": <rows in this page>,
          "has_more": <bool>, "next_offset": <int | None>,
          "data": [ {row}, ... ],
          "warnings": [ ... ]  # present only when relevant
        }

        Workflow: use eia_browse_routes to find the route, its valid
        `data_columns`, `frequencies`, and facet ids; use eia_get_facet_options
        for valid facet values; then call this tool. If `data` columns are wrong
        the API may return empty rows, so verify columns against the metadata.
        """
        try:
            api_key = get_api_key()
        except EIAConfigError as exc:
            return {"error": str(exc),
                    "suggestion": "Set the EIA_API_KEY environment variable."}

        params = encode_params(
            api_key,
            data=data,
            facets=facets,
            frequency=frequency,
            start=start,
            end=end,
            sort=sort,
            length=length,
            offset=offset,
        )
        url = build_url(route, "data")
        body = await eia_get(url, params)
        if "error" in body:
            return body

        resp = body.get("response", {})
        rows = resp.get("data", []) or []
        total_raw = resp.get("total")
        try:
            total = int(total_raw) if total_raw is not None else None
        except (TypeError, ValueError):
            total = None

        returned = len(rows)
        has_more = total is not None and (offset + returned) < total
        next_offset = (offset + returned) if has_more else None

        warnings: list[str] = []
        if returned == 0:
            warnings.append(
                "No rows returned. Verify `data` columns, `facets`, `frequency`, "
                "and the date range against eia_browse_routes metadata."
            )

        result: dict[str, Any] = {
            "route": route,
            "frequency": resp.get("frequency") or frequency,
            "description": resp.get("description"),
            "total": total,
            "offset": offset,
            "length": length,
            "returned": returned,
            "has_more": has_more,
            "next_offset": next_offset,
            "data": rows,
        }
        if warnings:
            result["warnings"] = warnings
        return result
