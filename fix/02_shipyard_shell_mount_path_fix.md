# Shipyard Shell Mount Path Fix

## 背景

2026-03-21 在 QQ 官方机器人会话里触发 `astrbot_execute_shell` 后，shell 工具没有进入命令执行阶段，而是在 Shipyard 创建 sandbox 时直接失败。最新容器日志里的关键报错是：

- 时间：`2026-03-21 14:46:28`
- 现象：`Failed to create ship: 500`
- 细节：Docker 报 `app/shipyard/ship_mnt_data/.../home includes invalid characters for a local volume name`

这说明失败点不在 shell 命令本身，而在 sandbox 挂载路径构造。

## 根因

`compose-with-shipyard.yml` 里 `shipyard` 服务的 `SHIP_DATA_DIR` 被写成了相对路径：

- 错误值：`app/shipyard/ship_mnt_data`

Shipyard 会把这个值继续传给 Docker 作为 bind mount 源路径。因为它不是绝对路径，Docker 将其按 volume name 处理，最终在创建 `.../home` 挂载时因包含 `/` 而报错。

## 改动文件

- `compose-with-shipyard.yml`

## 关键实现

将 `SHIP_DATA_DIR` 改回宿主机绝对路径形式：

- 新值：`${PWD}/data/shipyard/ship_mnt_data`

同时在配置旁补充说明，明确该值必须保持为宿主机绝对路径，因为 Shipyard 会把它直接转发给 Docker。

## 验证方法

1. 查看运行日志，确认失败栈位于 `computer_client.py -> shipyard.py -> create_ship()`，且报错文本包含相对路径 `app/shipyard/ship_mnt_data/.../home`。
2. 检查运行中的 `astrbot_shipyard` 容器环境，确认修复前 `SHIP_DATA_DIR=app/shipyard/ship_mnt_data`。
3. 修改 compose 文件后，重建 `shipyard` 服务，使容器读取新的环境变量。
4. 再次检查 `astrbot_shipyard` 容器环境，确认 `SHIP_DATA_DIR` 已变为宿主机绝对路径。
5. 重新执行最小化 sandbox 创建或再次触发 QQ 会话中的 shell 工具，确认不再报 volume name 非法错误。

## 兼容与升级注意

