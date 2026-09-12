#!/usr/bin/env bash
# End-to-end smoke test: builds a minimal image from the Go template and a
# deliberately bloated one, then checks lint_dockerfile.py and inspect_image.sh
# report what we expect. Requires Docker with BuildKit.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
good="minimal-docker-smoke:good"
bad="minimal-docker-smoke:bad"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"; docker rmi -f "$good" "$bad" >/dev/null 2>&1 || true' EXIT

pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }
expect() {
  if grep -Eq "$2" <<<"$1"; then pass "$3"; else echo "$1" >&2; fail "$3"; fi
}
refute() {
  if grep -Eq "$2" <<<"$1"; then echo "$1" >&2; fail "$3"; else pass "$3"; fi
}

echo "== Lint the template"
python3 "$root/scripts/lint_dockerfile.py" "$here/go-hello/Dockerfile" \
  || fail "template has lint errors"
pass "template lints clean"

echo "== Build and run the minimal image"
docker build -q -t "$good" "$here/go-hello" >/dev/null
out="$(docker run --rm --read-only "$good")"
expect "$out" "^hello uid=65532 certs=true$" "runs as 65532 with CA certs on a read-only rootfs"

report="$(bash "$root/scripts/inspect_image.sh" "$good")"
echo "$report"
expect "$report" "Tools present: none" "inspect finds no shell/package manager"
refute "$report" "WARNING: image runs as root" "inspect does not warn about root"
size="$(docker image inspect -f '{{.Size}}' "$good")"
if [ "$size" -lt $((25 * 1024 * 1024)) ]; then
  pass "image under 25 MB ($size bytes)"
else
  fail "image unexpectedly large: $size bytes"
fi

echo "== Build a bloated image and check inspect flags it"
cat > "$tmp/Dockerfile" <<'DOCKERFILE'
FROM alpine:3.20
RUN apk add --no-cache curl
CMD ["sh"]
DOCKERFILE
docker build -q -t "$bad" "$tmp" >/dev/null
report="$(bash "$root/scripts/inspect_image.sh" "$bad")"
expect "$report" "Tools present:.* sh" "inspect detects a shell"
expect "$report" "Tools present:.* apk" "inspect detects a package manager"
expect "$report" "Tools present:.* curl" "inspect detects curl"
expect "$report" "WARNING: image runs as root" "inspect warns about root"

echo
echo "All smoke tests passed."
