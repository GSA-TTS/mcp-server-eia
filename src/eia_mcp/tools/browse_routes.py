"""eia_browse_routes: explore the EIA API v2 dataset tree and leaf metadata.

The EIA API is a recursive tree. A GET on a route path returns EITHER:
- child routes (an intermediate node), OR
- leaf metadata: available frequencies, facet ids, valid data columns, and the
  covered date range (a queryable dataset).

This single tool covers both cases, so it doubles as the dataset-metadata tool.
"""

from typing import Annotated, Any

from pydantic import Field

from eia_mcp.utils import eia_request


def register(mcp):
    @mcp.tool(
        annotations={
            "title": "Browse EIA routes / dataset metadata",
            "readOnlyHint": True,
            "openWorldHint": True,
        }
    )
    async def eia_browse_routes(
        route: Annotated[
            str,
            Field(
                default="",
                description=(
                    "Dataset route path to inspect. Use an empty string to list "
                    "the top-level datasets (e.g. electricity, natural-gas, "
                    "petroleum, coal, total-energy). Drill down by appending "
                    "child ids, e.g. 'electricity' then 'electricity/retail-sales'. "
                    "Leading/trailing slashes and a 'v2/' prefix are tolerated."
                ),
            ),
        ] = "",
    ) -> dict[str, Any]:
        """Explore the EIA dataset tree, or fetch a leaf dataset's metadata.

        Behavior depends on the node type at `route`:
        - Intermediate node -> returns `{"type": "routes", "routes": [...]}`,
          each item being a selectable child route id + name/description.
        - Leaf dataset -> returns `{"type": "dataset", ...}` with the available
          `frequencies`, `facets` (facet ids to filter on), valid `data` columns,
          and the `startPeriod`/`endPeriod` date coverage. Feed these into
          eia_get_data.

        Start with route="" to discover datasets, then drill down. This is the
        primary discovery tool; call it before eia_get_data to learn the valid
        columns, facet ids, and frequency for a dataset.
        """
        body = await eia_request(route)
        if "error" in body:
            return body

        resp = body.get("response", {})

        # Leaf datasets expose frequency/facets metadata; intermediate nodes
        # expose a `routes` list.
        if "routes" in resp and resp.get("routes"):
            routes = resp.get("routes")
            # Normalize dict-of-routes or list-of-routes into a clean list.
            if isinstance(routes, dict):
                routes = list(routes.values())
            return {
                "type": "routes",
                "route": route,
                "id": resp.get("id"),
                "name": resp.get("name"),
                "description": resp.get("description"),
                "routes": routes,
            }

        return {
            "type": "dataset",
            "route": route,
            "id": resp.get("id"),
            "name": resp.get("name"),
            "description": resp.get("description"),
            "frequencies": resp.get("frequency"),
            "facets": resp.get("facets"),
            "data_columns": resp.get("data"),
            "startPeriod": resp.get("startPeriod"),
            "endPeriod": resp.get("endPeriod"),
            "defaultFrequency": resp.get("defaultFrequency"),
            "defaultDateFormat": resp.get("defaultDateFormat"),
        }
