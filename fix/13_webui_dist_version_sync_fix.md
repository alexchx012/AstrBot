# WebUI Dist Version Sync Fix

## Background

On 2026-03-26 AstrBot backend had already been updated to `4.22.1`, but the mounted WebUI assets under `data/dist` still reported `v4.22.0`.

This caused startup to emit:

`检测到 WebUI 版本 (v4.22.0) 与当前 AstrBot 版本 (v4.22.1) 不符。`

## Root Cause

The running container reads WebUI version from `data/dist/assets/version`, not from `dashboard/package.json`.

The backend version had been updated, but the deployed static bundle in `data/dist` had not been rebuilt or replaced, so the backend and WebUI asset versions diverged.

The release workflow shows the intended stamping behavior:

- `.github/workflows/release.yml` writes the tag into `dashboard/dist/assets/version`
- `.github/workflows/dashboard_ci.yml` writes a commit SHA into the same file for CI artifacts

## Changed Files

- `dashboard/dist/**` rebuilt locally from current source
- `dashboard/dist/assets/version` added with `v4.22.1`
- `data/dist/**` replaced with the rebuilt bundle
- `data/dist.backup.v4.22.0.20260326194149/**` preserved as rollback backup

## Key Implementation

1. Installed dashboard dependencies with `pnpm`.
2. Ran local production build in `dashboard/`.
3. Added `dashboard/dist/assets/version` with `v4.22.1`.
4. Replaced mounted runtime assets in `data/dist` with the rebuilt bundle.
5. Restarted `astrbot` so startup logs could verify the mismatch warning was gone.

## Verification

Verified after replacement:

- `dashboard/dist/assets/version` is `v4.22.1`
- `data/dist/assets/version` is `v4.22.1`
- container sees `/AstrBot/data/dist/assets/version = v4.22.1`
- container backend version remains `4.22.1`
- restart log shows `WebUI 版本已是最新。`

## Compatibility Notes

- The local Vite build completed successfully, but `vite-plugin-webfont-dl` could not resolve `fonts.googleapis.com` during build. The build still finished and produced usable assets.
- Future WebUI upgrades should continue following the release workflow convention: always stamp `dashboard/dist/assets/version` before packaging or copying to `data/dist`.
