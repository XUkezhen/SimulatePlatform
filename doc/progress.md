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

## 2026-04-16

- **场景表添加信道配置**
  - Scene 模型新增 `channelCount`（信道数量）和 `channelConfigs`（信道配置列表，JSONField）字段
  - 场景 API 支持：创建、编辑、查询场景时传递信道配置参数
  - 新增接口：`GET /api/getChannelNames?sceneId=xxx` 获取场景下所有信道名称
  - `exata_config.template` 的 Channel Properties 改为按 `channelConfigs` 动态输出，`PHY-LISTENABLE-CHANNELS` / `PHY-LISTENING-CHANNELS` 跟随首个信道名

- **节点故障添加接口选择**
  - Error 模型新增 `interfaceId` 字段（可选外键，关联 Interface）
  - 节点故障 API 改用 `interfaceIndex`（接口序号）而非接口ID
  - 创建/编辑节点故障时，可指定具体接口序号；不指定则表示整个节点故障
  - 故障文件生成逻辑适配：指定接口只写该接口故障，不指定写所有接口故障

- **文件改动**
  - `api/models.py`: Scene 和 Error 模型新增字段
  - `api/forms.py`: SceneForm 和 ErrorForm 添加字段验证
  - `api/views.py`: 场景/故障视图函数、故障文件生成函数、新增 get_channel_names
  - `api/urls.py`: 新增路由

- **数据库迁移**
  - 新增迁移文件：`0017_error_interfaceid_scene_channelconfigs_and_more.py`

- 本地提交：`f388bf9` (主要功能), `8db5bb6` (文档更新)

- **新增业务类型与 `.app` 导出**
  - `Configuration` 新增 3 类业务：`泊松分布`、`广播业务`、`组播业务`
  - 新增对应配置字段、列表返回字段、创建校验与编辑分支
  - `.app` 生成逻辑已支持导出以下 EXATA 格式：
    - `泊松分布` -> `VBR <src> <dest> <packet_size> <mean_interval> <start_time> <end_time>`
    - `广播业务` -> `MESSENGER-APP <src> <dest> <transport_type> <app_type> <life_time> <start_time> <interval> <fragment_size> <fragment_num>`
    - `组播业务` -> `MCBR <src> <multicast-destination> <items-to-send> <item-size> <interval> <start-time> <end-time>`
  - 新增文档：`doc/configuration_api.md`
