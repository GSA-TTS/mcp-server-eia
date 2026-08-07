#!/usr/bin/env sh
# Build and push the EIA MCP server image to a public registry so the Obot MCP
# gateway can pull it (the Docker runtime backend pulls WITHOUT auth, so the
# image MUST be public).
#
# Usage:
#   ./build-and-push.sh [VERSION]
#
# VERSION defaults to the version in pyproject.toml. Requires that you are
# already logged in to GHCR (docker login ghcr.io) with push rights to
# GSA-TTS, and that the package visibility is set to PUBLIC after the first push.
#
# This script does NOT handle credentials and does NOT bake any secret into the
# image (the per-user EIA_API_KEY is injected at runtime by the gateway).
set -eu

# Run from the repo root regardless of where the script is invoked from, so the
# build context (.) and pyproject.toml resolve correctly.
cd "$(dirname "$0")/.."

IMAGE="ghcr.io/gsa-tts/mcp-server-eia"

# Resolve version from arg or pyproject.toml.
VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  VERSION="$(grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)".*/\1/')"
fi
if [ -z "$VERSION" ]; then
  echo "ERROR: could not determine version; pass it explicitly." >&2
  exit 1
fi

echo "Building ${IMAGE}:${VERSION} (and :latest)"
docker build -t "${IMAGE}:${VERSION}" -t "${IMAGE}:latest" .

echo "Pushing ${IMAGE}:${VERSION}"
docker push "${IMAGE}:${VERSION}"
echo "Pushing ${IMAGE}:latest"
docker push "${IMAGE}:latest"

cat <<EOF

Done. Next steps (human):
  1. Ensure the GHCR package visibility is PUBLIC:
     https://github.com/orgs/GSA-TTS/packages/container/mcp-server-eia/settings
  2. Verify it is publicly pullable (no auth):
     docker manifest inspect ${IMAGE}:${VERSION}
  3. The catalog entry pins ${IMAGE}:${VERSION}.
EOF
