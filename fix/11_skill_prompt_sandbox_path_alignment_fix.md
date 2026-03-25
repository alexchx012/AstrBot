# Skill Prompt Sandbox Path Alignment Fix

## Background

After syncing `upstream/master`, local verification showed two official tests failing:

- `tests/test_skill_metadata_enrichment.py::test_build_skills_prompt_sanitizes_sandbox_skill_metadata_in_inventory`
- `tests/test_skill_metadata_enrichment.py::test_build_skills_prompt_sanitizes_invalid_sandbox_skill_name_in_path`

The upstream CI was green, so the mismatch came from the local branch state after combining upstream updates with local patches.

## Root Cause

`build_skills_prompt()` had local logic that rewrote `sandbox_only` skill paths through `_build_sandbox_prompt_path(...)`, even after the input path had already been sanitized for prompt display.

That changed the prompt-visible path from:

- sanitized original sandbox cache path

to:

- rebuilt default path based on display name

which broke the official tests that intentionally assert the prompt preserves the sanitized original sandbox path.

## Changed Files

- `astrbot/core/skills/skill_manager.py`
- `project_index/04_integrations_and_extensions.md`

## Key Implementation

- In `build_skills_prompt()`, keep using the sanitized incoming `skill.path` for `sandbox_only` skills.
- Only fall back to the default sandbox path when the sanitized path is empty.
- Kept `_build_sandbox_prompt_path(...)` intact for other sandbox path normalization use cases outside this prompt-rendering path.

## Verification

1. Red:
   `env TESTING=true uv run pytest tests/test_skill_metadata_enrichment.py -q`
   Result before fix: `2 failed, 28 passed`
2. Green:
   `env TESTING=true uv run pytest tests/test_skill_metadata_enrichment.py -q`
   Result after fix: `30 passed`
3. Related sandbox cache tests:
   `env TESTING=true uv run pytest tests/test_skill_manager_sandbox_cache.py -q`
   Result: `4 passed`
4. Related local `/setid` regression bundle after upstream sync:
   `env ASTRBOT_ROOT=/tmp/astrbot-sync-verify-b uv run pytest tests/unit/test_setid_command.py tests/unit/test_qqofficial_message_event.py tests/unit/test_qqofficial_platform_adapter.py tests/unit/test_qqofficial_workspace_registry.py -q`
   Result: `31 passed`

## Compatibility Notes

- This change only affects how sandbox-only skill paths are rendered into the LLM skills prompt.
- It does not change the underlying sandbox skill sync mechanism or file layout inside the sandbox.
