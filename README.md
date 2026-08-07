# mcp-server-eia

An [MCP](https://modelcontextprotocol.io) server that exposes the U.S. Energy
Information Administration (EIA) [Open Data API v2](https://www.eia.gov/opendata/)
to LLM clients. It provides a small set of **generic, composable tools** that
mirror the API's uniform tree structure (browse → discover facets → query data),
giving agents full coverage of all 17 EIA datasets — electricity, natural gas,
petroleum, coal, nuclear outages, CO2 emissions, renewables, and the energy
outlooks (AEO/IEO/STEO) — without hard-coding hundreds of endpoints.

## Tools

| Tool | Purpose |
|------|---------|
| `eia_browse_routes` | Explore the dataset tree from any path (empty = the 17 top-level datasets). At a leaf, returns dataset metadata: available frequencies, facet ids, valid data columns, and the covered date range. Primary discovery tool. |
| `eia_list_facets` | List the facet ids a dataset can be filtered by (e.g. `stateid`, `sectorid`, `fueltypeid`). |
| `eia_get_facet_options` | List the valid option values for a single facet, so filters use real ids. |
| `eia_get_data` | Query dataset rows with column selection, facet filters, frequency, date range, sorting, and pagination. Returns structured JSON with pagination metadata. |

## How the EIA API is shaped

The API is a recursive tree. A `GET` on a route path returns **either** child
routes (an intermediate node) **or** leaf metadata (a queryable dataset). The
typical workflow is:

1. `eia_browse_routes(route="")` — list top-level datasets.
2. Drill down, e.g. `eia_browse_routes(route="electricity/retail-sales")` — read
   the valid `data_columns`, `frequencies`, and facet ids.
3. `eia_list_facets` / `eia_get_facet_options` — find valid filter values.
4. `eia_get_data(...)` — retrieve the numbers.

### Conventions

- **Routes** are slash paths without a `v2/` prefix, e.g.
  `electricity/retail-sales`.
- **Date formats** depend on frequency: `2020` (annual), `2020-01` (monthly),
  `2020-01-01` (daily), `2020-01-01T00` (hourly).
- **Facets** are passed as `{facet_id: [values]}`; **sort** as
  `[{"column": ..., "direction": "asc"|"desc"}]`.
- **Pagination**: `length` (page size, max 5000) and `offset`. Reuse the
  `next_offset` returned by the previous `eia_get_data` response.

## Requirements

- Python `>=3.14`
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- A free EIA API key: https://www.eia.gov/opendata/register.php

## Setup

```sh
uv sync
```

### Authentication

Set the `EIA_API_KEY` environment variable, or create a `.env` file in the
project root (loaded automatically at startup; `.env` is gitignored):

```
EIA_API_KEY=your_key_here
```

## Running

```sh
uv run python -m eia_mcp.app
```

- With no port env var set, the server runs over **stdio** (for Claude Desktop,
  Claude Code, and other local MCP clients).
- If `PORT` or `DATABRICKS_APP_PORT` is set, it runs over **streamable HTTP** on
  that port, serving MCP at the fixed path **`/mcp`** and a **`GET /health`**
  readiness endpoint. This is the mode the container image uses.

### Container / gateway-hosted deployment

The included `Dockerfile` builds an image that serves MCP over streamable HTTP
at **`:8080/mcp`** (health at `/health`) — the contract the GSA Obot MCP gateway
expects for a `containerized` server.

```sh
docker build -t mcp-server-eia .
docker run --rm -p 8080:8080 -e EIA_API_KEY=your_key_here mcp-server-eia
curl -s localhost:8080/health   # {"status":"healthy","service":"mcp-server-eia"}
```

Publish a public, version-pinned image for the gateway to pull:

```sh
./scripts/build-and-push.sh          # tags ghcr.io/gsa-tts/mcp-server-eia:<version>
```

> The gateway's Docker runtime pulls **without** registry auth, so the image
> must be **publicly pullable**. Set the GHCR package visibility to public after
> the first push.

### Authentication model

This server deals with **two distinct credentials on two different hops** — do
not conflate them:

| Credential | Hop | Who supplies / enforces it |
|------------|-----|----------------------------|
| Gateway/transport auth (e.g. Obot API key) | client → gateway → this server | The **Obot gateway**. In the `containerized` deployment the container has **no public route**, so the gateway is the only caller and it enforces access. |
| `EIA_API_KEY` | this server → `api.eia.gov` | Read from the **environment** at call time (`utils.get_api_key`). In a `singleUser` gateway deployment, each user gets their own container instance with **their own** key injected as an env var. |

Because the gateway owns transport auth and each user's key is isolated per
instance, the server intentionally sets **no FastMCP `auth` provider** — it
assumes zero transport-authentication responsibility.

> **If this server is ever deployed as a `remote` server** (a public URL
> reachable independently of the gateway), the MCP endpoint would be
> unauthenticated. In that case add a FastMCP server-side `JWTVerifier`
> validating the gateway/SSO issuer (contingent on that issuer exposing a JWKS
> endpoint) — **not** `OAuthProxy`/`OAuthProvider`. Keeping the server
> `containerized` (gateway-guarded) avoids this.

### Example MCP client config (stdio)

```json
{
  "mcpServers": {
    "eia": {
      "command": "uv",
      "args": ["run", "python", "-m", "eia_mcp.app"],
      "cwd": "/path/to/mcp-server-eia",
      "env": { "EIA_API_KEY": "your_key_here" }
    }
  }
}
```

## Project layout

```
src/eia_mcp/
├── app.py                    # FastMCP init, instructions, transport selection
├── routes.py                 # HTTP health-check route
├── utils.py                  # API key, URL building, param encoding, HTTP client, errors
└── tools/
    ├── __init__.py           # register_tools(mcp): wires up all tools
    ├── browse_routes.py      # eia_browse_routes
    ├── list_facets.py        # eia_list_facets
    ├── get_facet_options.py  # eia_get_facet_options
    └── get_data.py           # eia_get_data
Dockerfile                    # containerized deployment (:8080/mcp, /health)
scripts/build-and-push.sh     # build + push public GHCR image for the gateway
docs/eia-api-swagger/         # EIA API v2 OpenAPI/Swagger reference
```

Each tool lives in its own file and exposes a `register(mcp)` function; new tools
are added by dropping a file in `tools/` and registering it in
`tools/__init__.py`.

## Data source & attribution

Data is retrieved live from the U.S. Energy Information Administration Open Data
API. See the [EIA API terms of service](https://www.eia.gov/opendata/) for usage
and attribution requirements.
