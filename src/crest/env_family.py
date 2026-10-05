"""Environment families: the sampling population for generalized evidence.

A family definition is deliberately small for V0.3: filesystem.single_file,
filesystem.directory_tree, git.repository. Scope semantics etc. live in the
family rather than hard-coded policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EnvironmentFamily:
    family_id: str
    description: str
    supported_actions: tuple[str, ...] = ()
    required_invariants: tuple[str, ...] = ()


FAMILIES: dict[str, EnvironmentFamily] = {
    "filesystem.single_file": EnvironmentFamily(
        family_id="filesystem.single_file",
        description="One target file inside a small flat workspace",
        supported_actions=("create_file", "modify_file", "delete_file", "move_file"),
        required_invariants=("workspace_contained", "no_symlinks"),
    ),
    "filesystem.directory_tree": EnvironmentFamily(
        family_id="filesystem.directory_tree",
        description="Nested directories with distractors",
        supported_actions=("create_file", "modify_file", "delete_file", "move_file", "delete_directory"),
        required_invariants=("workspace_contained",),
    ),
    "git.repository": EnvironmentFamily(
        family_id="git.repository",
        description="A git repo with commits",
        supported_actions=("git_create_branch", "git_modify_file", "git_commit"),
        required_invariants=("repo_contained",),
    ),
}
