"""
EIA MCP Tools

Generic, path-driven tools that cover the entire EIA API v2 surface:
- eia_browse_routes    : explore the dataset tree and fetch leaf metadata
- eia_list_facets      : list a dataset's filterable facet ids
- eia_get_facet_options: list valid values for a single facet
- eia_get_data         : query dataset rows with filtering, sorting, paging
"""

from . import (
    browse_routes,
    get_data,
    get_facet_options,
    list_facets,
)


def register_tools(mcp):
    """Register all tools with the MCP server."""
    browse_routes.register(mcp)
    list_facets.register(mcp)
    get_facet_options.register(mcp)
    get_data.register(mcp)
