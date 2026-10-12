"""Per-repo label profiles.

A profile declares which labels a draft for that repo is allowed to carry.
`resolve` turns a parser hint like ("area", "ontology") into the canonical
label from the profile, or raises UnknownLabel if the hint doesn't match.
Unknown-repo lookups raise UnknownRepo with a clean message for the CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class UnknownRepo(Exception):
    pass


class UnknownLabel(Exception):
    pass


@dataclass
class Profile:
    repo: str
    slug_prefix: str
    scheme: dict[str, list[str]]
    defaults: list[str]

    def resolve(self, namespace: str, value: str) -> str:
        """Map a hint like ('area', 'ontology') → 'area:ontology' if in-profile.

        For a flat-label repo, namespace is 'flat' and value is the bare label.
        For a sized hint, namespace is 'size' and value is 'S'/'M'/'L'/'XL'.
        """
        if namespace not in self.scheme:
            raise UnknownLabel(
                f"profile {self.repo!r} has no namespace {namespace!r}; "
                f"known: {sorted(self.scheme)}"
            )
        candidate = value if namespace == "flat" else f"{namespace}:{value}"
        if candidate not in self.scheme[namespace]:
            raise UnknownLabel(
                f"label {candidate!r} not in profile {self.repo!r} "
                f"namespace {namespace!r}; known: {self.scheme[namespace]}"
            )
        return candidate


def load(profiles_path: Path, repo: str) -> Profile:
    data = yaml.safe_load(profiles_path.read_text())
    if repo not in data:
        raise UnknownRepo(
            f"unknown repo profile {repo!r}; known: {sorted(data)}"
        )
    entry = data[repo]
    return Profile(
        repo=repo,
        slug_prefix=entry["slug_prefix"],
        scheme=entry["scheme"],
        defaults=entry.get("defaults", []),
    )
