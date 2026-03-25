# Compose With Shipyard Deploy Rule Fix

## Background

The local AstrBot deployment rules in `AGENTS.md` told the operator to run:

- `docker compose up -d --build astrbot`

In this repository, that default command reads `compose.yml`, which only defines the `astrbot` service and places it on Docker's default project network.

At the same time, the Mnemosyne/Milvus stack was running from `compose-with-shipyard.yml`, where `astrbot`, `shipyard`, and `milvus-standalone` are attached to `astrbot_network`.

## Root Cause

The deployment rule in `AGENTS.md` did not pin the compose file.

As a result, rebuilding `astrbot` with the default `docker compose` command recreated only the `astrbot` container on `astrbot_default`, while `milvus-standalone` remained on `astrbot_network`.

That network split caused Mnemosyne's configured Milvus address `milvus-standalone:19530` to become unreachable from the `astrbot` container.

## Changed Files

- `AGENTS.md`
- `fix/compose_with_shipyard_deploy_rule_fix.md`

## Key Implementation

1. Updated both deployment rules in `AGENTS.md` to explicitly use `docker compose -f compose-with-shipyard.yml up -d --build astrbot`.
2. Kept the rest of the upstream-sync workflow unchanged.
3. Recorded the network mismatch root cause so future local fixes do not recreate the same split-network deployment.

## Verification

TDD skipped — reason: this change only updates local process documentation and deployment instructions, not Python application behavior.

Runtime verification is performed separately by redeploying AstrBot with `compose-with-shipyard.yml` and checking that the `astrbot` container rejoins `astrbot_network`.

## Compatibility Notes For Future AstrBot Upgrades

- If the local deployment topology stops depending on Shipyard/Milvus, re-evaluate whether `compose-with-shipyard.yml` should remain the mandatory local deploy entrypoint.
- If another compose file becomes the canonical local deployment file, update `AGENTS.md` in the same change set.
- When diagnosing Mnemosyne connectivity issues, verify both the plugin Milvus address and the Docker network attachments before changing plugin code.
