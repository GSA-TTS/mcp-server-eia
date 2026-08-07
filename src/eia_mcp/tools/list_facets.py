"""eia_list_facets: list the facet ids available for a leaf dataset.

Facets are the dimensions you can filter a dataset by (e.g. stateid, sectorid,
fueltypeid). Use this to discover which facet ids exist, then
eia_get_facet_options to list valid values for a given facet.
"""

from typing import Annotated, Any

from pydantic import Field

from eia_mcp.utils import eia_request


def register(mcp):
    @mcp.tool(
        annotations={
            "title": "List EIA dataset facets",
            "readOnlyHint": True,
            "openWorldHint": True,
        }
    )
    async def eia_list_facets(
        route: Annotated[
            str,
            Field(
                description=(
                    "Leaf dataset route to list facets for, e.g. "
                    "'electricity/retail-sales'. Discover routes with "
                    "eia_browse_routes."
                ),
                min_length=1,
            ),
        ],
    ) -> dict[str, Any]:
        """List the facet ids you can filter a dataset by.

        Returns `{"route": ..., "facets": [{"id", "description"}, ...]}`. Pass a
        facet id to eia_get_facet_options to enumerate its valid values, then use
        those values in the `facets` argument of eia_get_data.
        """
        body = await eia_request(route, "facet")
        if "error" in body:
            return body

        resp = body.get("response", {})
        facets = resp.get("facets", resp)
        return {"route": route, "facets": facets}
