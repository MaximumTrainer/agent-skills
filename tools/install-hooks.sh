#!/usr/bin/env bash
#
# Point git at the tracked hooks in .githooks/.
#
# Hooks in .git/hooks are not version controlled and are not cloned, so every
# clone has to opt in once:
#
#     bash tools/install-hooks.sh
#
# Undo with:
#
#     git config --unset core.hooksPath

set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true

echo "core.hooksPath -> .githooks"
echo "versioning branch: $(git config --get skills.versionBranch 2>/dev/null || echo 'main (default)')"
echo
echo "Skills touched by a commit on that branch now get a patch version bump."
echo "  SKILL_BUMP=minor git commit ...   bump minor instead"
echo "  git commit --no-verify          skip the hook"
