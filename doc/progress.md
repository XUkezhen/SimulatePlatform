# Progress

## 2026-04-07
- 建立本地 Git checkpoint。
- 切换并使用本地 `main` 分支做后续开发记录。
- 本地提交：`38ea382`
- 提交说明：`chore: save local checkpoint`

## 2026-04-09
- 接入 `viaPoints` 到 `.nodes` 生成逻辑。
- 接入 `viaPoints` 到 `node.txt` 生成逻辑。
- `download_all_files` 生成的 `node.txt` 已同步支持多时间点。
- `generate_node_file` 接口生成的 `node.txt` 已同步支持多时间点。
- `bulk.py` 反向导入 `.nodes` 时，已兼容同一节点多行并回填为 `viaPoints`。
- 当前约定：
  `.nodes` 每行格式为：`节点ID 时间(秒) (纬度 经度 高度) 0 0 0`
  `node.txt` 每行格式为：`节点ID 时间(秒) 纬度 经度 高度 nodeImage nodeName`

## 2026-04-13

- 优化 `exata_config.template` 中 Routing 配置的写入逻辑。
- 改动：只写入 `ROUTING-PROTOCOL-IPv4` 参数，过滤默认值 `BellmanFord`。
- 位置：模板第469-472行、第478-481行、第486-489行（sub/link 类型接口）。
- 提交说明：`refactor: simplify routing config in exata template`

## 模板

- 日期：
- 改动：
- 本地提交：
- 备注：
