# Custom AstrBot Image Deployment

## 背景

当前 AstrBot 部署原先直接使用 `soulter/astrbot:latest`。这种方式下，本地仓库 `/home/snight/AstrBot` 里的源码修改不会自动进入容器，导致“本地代码已修复，但容器仍运行旧代码”的分裂状态。

## 根因

`compose-with-shipyard.yml` 中 `astrbot` 服务只声明了官方镜像，并且仅挂载 `data/` 目录，没有把主机源码目录挂入容器。因此容器代码始终来自镜像内部 `/AstrBot`，而不是本地仓库。

## 改动文件

- `compose-with-shipyard.yml`

## 关键实现

- 将 `astrbot` 服务从 `image: soulter/astrbot:latest` 改为：
  - `image: alexchx012/astrbot:local`
  - `build.context: .`
  - `build.dockerfile: Dockerfile`
- 使用 `docker compose up -d --build astrbot` 直接基于 `/home/snight/AstrBot` 构建并重建容器。
- 重建后验证运行中的 `astrbot` 容器镜像名已经变为 `alexchx012/astrbot:local`，且容器内源码包含本地仓库中的修复代码。

## 验证方法

1. 构建并重建服务：
   - `docker compose -f compose-with-shipyard.yml up -d --build astrbot`
2. 检查运行容器镜像名：
   - `docker inspect astrbot --format '{{.Config.Image}}'`
3. 检查容器内关键源码是否包含本地修复。
4. 预期结果：
   - 容器镜像为 `alexchx012/astrbot:local`
   - 容器内 `/AstrBot/astrbot/...` 源码与本地仓库构建时内容一致

## 兼容与升级注意

- 以后仅 `docker restart astrbot` 不会重新打包新代码；本地源码有变更后，需要重新执行 `docker compose up -d --build astrbot`。
- 如果要吸收官方更新，优先做源码级同步：`git fetch upstream` -> 合并上游 -> 重新 build 本地镜像。
- 如果未来要在别的机器部署，需要先同步源码仓库，再构建 `alexchx012/astrbot:local`，不能假定这个 tag 在远端仓库已存在。
- TDD skipped — reason: deployment wiring change. Verification used real Docker build/recreate plus container code inspection.
