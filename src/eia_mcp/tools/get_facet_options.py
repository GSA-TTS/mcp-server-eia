"""eia_get_facet_options: list valid values for a single facet of a dataset.

After finding a facet id with eia_list_facets, use this to enumerate the exact
option values (ids) accepted for that facet, so filters in eia_get_data use real
values rather than guesses.
"""

from typing import Annotated, Any

from pydantic import Field

from eia_mcp.utils import eia_request


def register(mcp):
    @mcp.tool(
        annotations={
            "title": "Get EIA facet option values",
            "readOnlyHint": True,
            "openWorldHint": True,
        }
    )
    async def eia_get_facet_options(
        route: Annotated[
            str,
            Field(
                description=(
                    "Leaf dataset route, e.g. 'electricity/retail-sales'."
                ),
                min_length=1,
            ),
        ],
        facet_id: Annotated[
            str,
            Field(
                description=(
                    "Facet id whose values to list, e.g. 'stateid' or "
                    "'sectorid'. Discover facet ids with eia_list_facets."
                ),
                min_length=1,
            ),
        ],
    ) -> dict[str, Any]:
        """List the valid option values (ids) for one facet of a dataset.

        Returns `{"route", "facet_id", "total", "options": [...]}`. Use the
        returned ids as values in the `facets` argument of eia_get_data, e.g.
        facets={"stateid": ["CA", "NY"]}.
        """
        body = await eia_request(route, f"facet/{facet_id}")
        if "error" in body:
            return body

        resp = body.get("response", {})
        return {
            "route": route,
            "facet_id": facet_id,
            "total": resp.get("totalFacetOptions") or resp.get("totalFacets"),
            "options": resp.get("facets") or resp.get("facetOptions") or resp,
        }
