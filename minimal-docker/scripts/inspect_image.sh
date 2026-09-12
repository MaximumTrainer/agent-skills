#!/usr/bin/env bash
# Inspect a built image for size, layers, runtime config, and leftover tooling.
# Usage: bash inspect_image.sh IMAGE[:TAG]
set -euo pipefail

IMG="${1:?usage: inspect_image.sh IMAGE[:TAG]}"
command -v docker >/dev/null || { echo "docker not found in PATH" >&2; exit 2; }
docker image inspect "$IMG" >/dev/null 2>&1 || { echo "image not found: $IMG" >&2; exit 2; }

human() { awk -v b="$1" 'BEGIN{split("B KB MB GB",u," ");i=1;while(b>=1024&&i<4){b/=1024;i++}printf "%.1f %s",b,u[i]}'; }
field() { docker image inspect -f "$1" "$IMG"; }

size=$(field '{{.Size}}')
user=$(field '{{.Config.User}}')

echo "== $IMG ($(field '{{.Os}}/{{.Architecture}}'))"
echo "Size:        $(human "$size")"
echo "User:        ${user:-root (no USER set)}"
echo "Entrypoint:  $(field '{{json .Config.Entrypoint}}')"
echo "Cmd:         $(field '{{json .Config.Cmd}}')"
echo "Ports:       $(field '{{json .Config.ExposedPorts}}')"
echo

echo "== Layers (largest first, non-empty only)"
docker history --no-trunc --format '{{.Size}}	{{.CreatedBy}}' "$IMG" \
  | awk -F'\t' '$1!="0B"{c=$2; gsub(/[ \t]+/," ",c); if(length(c)>100)c=substr(c,1,97)"..."; printf "%8s  %s\n",$1,c}' \
  | sort -h -r | head -15
echo

# Export the filesystem without running anything (works for shell-less images).
tmp=$(mktemp -d)
cid=$(docker create "$IMG" /nonexistent-noop)
trap 'docker rm -f "$cid" >/dev/null 2>&1 || true; rm -rf "$tmp"' EXIT
docker export "$cid" -o "$tmp/fs.tar"
tar -tf "$tmp/fs.tar" | sed 's#^\./##' > "$tmp/names"

echo "== Filesystem"
echo "Entries: $(wc -l < "$tmp/names" | tr -d ' ')"

found=""
for tool in sh bash ash busybox apt apt-get dpkg apk dnf yum microdnf pip pip3 npm yarn curl wget gcc cc make git ssh; do
  if grep -Eq "^(usr/)?(local/)?s?bin/${tool}$" "$tmp/names"; then found="$found $tool"; fi
done
echo "Tools present:${found:- none (no shell, package manager, compiler, curl/wget)}"

suid=$(tar -tvf "$tmp/fs.tar" | awk '$1 ~ /^-..[sS]|^-.....[sS]/ {f=$NF; sub(/^\.\//,"",f); print f}')
if [ -n "$suid" ]; then
  echo "setuid/setgid files:"
  printf '%s\n' "$suid" | sed "s/^/  /"
fi

if [ -z "$user" ] || [ "$user" = "root" ] || [ "${user%%:*}" = "0" ]; then
  echo
  echo "WARNING: image runs as root"
fi
