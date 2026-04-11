# Mixed Compose Runtime Version And Network Fix

## Background

On 2026-03-26 the deployed AstrBot instance reported three related symptoms:

1. Backend logs showed `AstrBot v4.20.1`, while the mounted WebUI assets reported `v4.22.0`.
2. `astrbot_plugin_mnemosyne` failed to connect to Milvus at `milvus-standalone:19530`.
3. sandbox boot failed with `Cannot connect to host shipyard:8156 [Name or service not known]`.

## Root Cause

The runtime was split across two different Compose definitions:

- `compose.yml` had started the `astrbot` container from `soulter/astrbot:latest`.
- `compose-with-shipyard.yml` had started `shipyard`, `milvus-etcd`, `milvus-minio`, and `milvus-standalone`.

Because of that split:

- `astrbot` was attached to Docker network `astrbot_default`.
- `shipyard` and Milvus were attached to Docker network `astrbot_network`.
- The `astrbot` container therefore could not resolve `shipyard` or `milvus-standalone`.

The old `soulter/astrbot:latest` image itself contained AstrBot `4.20.1`, so it also lagged behind the local source tree (`4.22.1`).

## Changed Files / Runtime Actions

No AstrBot source files were modified for the runtime fix.

Runtime actions performed:

1. Rebuilt and redeployed `astrbot` with:

   `docker compose -f /home/snight/AstrBot/compose-with-shipyard.yml up -d --build astrbot`

2. Verified the recreated `astrbot` container now uses:

   - image `alexchx012/astrbot:local`
   - AstrBot version `4.22.1`
   - Docker network `astrbot_network`

## Key Implementation Notes

- `data/cmd_config.json` keeps sandbox endpoint as `http://shipyard:8156`.
- `data/config/astrbot_plugin_mnemosyne_config.json` keeps Milvus address as `milvus-standalone:19530`.
- Those hostnames are correct only when `astrbot` joins the same Compose network as Shipyard and Milvus.
- After redeploy, `astrbot_plugin_mnemosyne` automatically reinstalled its missing dependencies (`pymilvus`, `milvus-lite`, `pypinyin`, `fastapi`) inside the new container and then connected successfully.

## Verification

Verified after redeploy:

- Container source version inside `/AstrBot/pyproject.toml` and `astrbot/core/config/default.py` is `4.22.1`.
- `astrbot` resolves both `shipyard` and `milvus-standalone` via container DNS.
- `curl http://shipyard:8156/health` from inside `astrbot` succeeds.
- Raw TCP connection from `astrbot` to `milvus-standalone:19530` succeeds.
- `pymilvus` connects successfully and lists collection `default`.
- Shipyard SDK can create a temporary ship and execute `echo ok` successfully.
- Startup logs show `成功连接到 Standard Milvus` and `Milvus 集合初始化完成`.

## Remaining Compatibility Note

`data/dist/assets/version` is still `v4.22.0`, so startup still warns:

`检测到 WebUI 版本 (v4.22.0) 与当前 AstrBot 版本 (v4.22.1) 不符。`

This warning is no longer caused by an old backend image. It is now a separate static asset version mismatch in the mounted `data/dist` directory. If later upgrades replace or rebuild WebUI assets, re-check `data/dist/assets/version` against backend `VERSION`.

## Upgrade Guidance

When upgrading AstrBot later, do not mix `compose.yml` and `compose-with-shipyard.yml` for the same deployment.

Use a single Compose definition for all interdependent services, otherwise service-name DNS such as `shipyard` and `milvus-standalone` will break again.
