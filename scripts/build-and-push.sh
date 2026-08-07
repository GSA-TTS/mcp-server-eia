#!/usr/bin/env sh
# Build and push the EIA MCP server image to a public registry so the Obot MCP
# gateway can pull it (the Docker runtime backend pulls WITHOUT auth, so the
# image MUST be public).
#
# The image is built MULTI-ARCH (linux/amd64 + linux/arm64). This is required:
# the gateway host is linux/amd64, so an arm64-only image (what a plain
# `docker build` produces on Apple Silicon) makes the gateway fail with
# "No such image ..." — it means "no manifest for my architecture".
#
# Usage:
#   ./build-and-push.sh [VERSION]
#
# VERSION defaults to the version in pyproject.toml. Requires that you are
# already logged in to GHCR (docker login ghcr.io) with push rights to
# GSA-TTS, and that the package visibility is set to PUBLIC after the first push.
#
# Cross-arch builds need emulation for the non-native platform. On Docker
# Desktop this is built in; otherwise run once:
#   docker run --privileged --rm tonistiigi/binfmt --install all
#
# This script does NOT handle credentials and does NOT bake any secret into the
# image (the per-user EIA_API_KEY is injected at runtime by the gateway).
set -eu

# Run from the repo root regardless of where the script is invoked from, so the
# build context (.) and pyproject.toml resolve correctly.
cd "$(dirname "$0")/.."

IMAGE="ghcr.io/gsa-tts/mcp-server-eia"
PLATFORMS="linux/amd64,linux/arm64"

# Resolve version from arg or pyproject.toml.
VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  VERSION="$(grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)".*/\1/')"
fi
if [ -z "$VERSION" ]; then
  echo "ERROR: could not determine version; pass it explicitly." >&2
  exit 1
fi

# buildx needs a container-driver builder to emit a multi-arch manifest and push
# it in one step. Create a dedicated one if it does not already exist.
BUILDER="eia-multiarch"
if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
  echo "Creating buildx builder '$BUILDER' (docker-container driver)"
  docker buildx create --name "$BUILDER" --driver docker-container --bootstrap >/dev/null
fi

echo "Building + pushing ${IMAGE}:${VERSION} (and :latest) for ${PLATFORMS}"
docker buildx build \
  --builder "$BUILDER" \
  --platform "$PLATFORMS" \
  -t "${IMAGE}:${VERSION}" \
  -t "${IMAGE}:latest" \
  --push \
  .

cat <<EOF

Done. Next steps (human):
  1. Ensure the GHCR package visibility is PUBLIC:
     https://github.com/orgs/GSA-TTS/packages/container/mcp-server-eia/settings
  2. Verify it is publicly pullable AND multi-arch (expect amd64 + arm64):
     docker manifest inspect ${IMAGE}:${VERSION} | grep architecture
  3. The catalog entry pins ${IMAGE}:${VERSION}.
EOF
