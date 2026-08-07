import os

from dotenv import load_dotenv
from fastmcp import FastMCP

from eia_mcp.tools import register_tools
from eia_mcp.routes import register_routes

# Load .env (EIA_API_KEY) before any tool reads configuration.
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP(
    "eia_mcp",
    instructions=(
        "Wraps the U.S. Energy Information Administration (EIA) Open Data API "
        "v2 so an LLM can discover and query official U.S. energy statistics "
        "(electricity, natural gas, petroleum, coal, nuclear, emissions, "
        "renewables, and energy outlooks) across 17 datasets.\n\n"
        "The API is a recursive tree: browse from the root down to a leaf "
        "'dataset', learn its valid columns/facets/frequency, then query rows.\n\n"
        "TOOL SELECTION GUIDE:\n"
        "- 'What datasets/routes exist?' or 'what columns/frequencies does X "
        "have?' -> eia_browse_routes (route='' lists top-level datasets; drill "
        "down; a leaf returns metadata)\n"
        "- 'What can I filter this dataset by?' -> eia_list_facets\n"
        "- 'What are the valid values for facet Y?' -> eia_get_facet_options\n"
        "- 'Get me the actual numbers/time series' -> eia_get_data\n\n"
        "CONVENTIONS:\n"
        "- Routes are slash paths without a 'v2/' prefix, e.g. "
        "'electricity/retail-sales'.\n"
        "- Date formats depend on frequency: '2020' (annual), '2020-01' "
        "(monthly), '2020-01-01' (daily), '2020-01-01T00' (hourly).\n"
        "- Facets are passed as {facet_id: [values]}; sort as "
        "[{'column','direction'}]. Page with length (<=5000) and offset; reuse "
        "next_offset from the previous response.\n"
        "- Always confirm valid `data` columns via eia_browse_routes before "
        "calling eia_get_data, or the API may return empty rows.\n\n"
        "AUTHENTICATION: Requires the EIA_API_KEY environment variable "
        "(free key at https://www.eia.gov/opendata/register.php)."
    ),
)

# Register custom tools
register_tools(mcp)

# Register custom routes
register_routes(mcp)

if __name__ == "__main__":
    # When run directly, check for a platform port env var.
    # If found, start an HTTP server (useful for Databricks local testing).
    # Otherwise fall back to stdio for local MCP clients (Claude Desktop, etc.).
    port_env = os.getenv("DATABRICKS_APP_PORT") or os.getenv("PORT")
    if port_env:
        mcp.run(transport="http", host="0.0.0.0", port=int(port_env))
    else:
        mcp.run(transport="stdio")




