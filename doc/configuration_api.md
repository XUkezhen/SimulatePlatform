# Business Configuration API

## Endpoints

### Create configuration

- Method: `POST`
- Path: `/api/addConfigurationList`
- Content-Type: `application/json`

### Query configuration list

- Method: `GET`
- Path: `/api/getConfigurationList`

Supported query params:

- `page`
- `size`
- `sceneId`
- `businessName`
- `businessType`
- `sourceNodeName`
- `destinationNodeName`

### Edit configuration

- Method: `PUT` or `PATCH`
- Path: `/api/editConfigurationList/<configuration_id>`

### Delete configuration

- Method: `DELETE`
- Path: `/api/deleteConfigurationList/<configuration_id>`

### Export EXATA files

- Method: `GET`
- Path: `/api/download_all_files?sceneId=<scene_id>`

If the scene has configuration data, the backend generates `<sceneName>.app` automatically.

## Common fields

Common request fields:

- `sceneId`: scene ID
- `businessType`: business type
- `businessName`: unique business name
- `sourceNodeId`: source node ID
- `destinationNodeId`: destination node ID, required for unicast traffic such as `POISSON`

For the new traffic types, time and interval fields should be sent as EXATA-style strings such as `1S`, `5S`, `20S`.

## Business types

### 1. POISSON

Required fields:

- `sceneId`
- `businessType`
- `businessName`
- `sourceNodeId`
- `destinationNodeId`
- `poissonStartTime`
- `poissonEndTime`
- `poissonMeanInterval`
- `poissonPacketSize`

Example request:

```json
{
  "sceneId": 1,
  "businessType": "POISSON",
  "businessName": "poisson-demo",
  "sourceNodeId": 1,
  "destinationNodeId": 2,
  "poissonStartTime": "1S",
  "poissonEndTime": "10S",
  "poissonMeanInterval": "20S",
  "poissonPacketSize": 512
}
```

Generated `.app` line:

```text
VBR 1 2 512 20S 1S 10S
```

Mapping:

- `VBR`
- `<src>` -> `sourceNodeId`
- `<dest>` -> `destinationNodeId`
- `<packet_size>` -> `poissonPacketSize`
- `<mean_interval>` -> `poissonMeanInterval`
- `<start_time>` -> `poissonStartTime`
- `<end_time>` -> `poissonEndTime`

### 2. BROADCAST

Required fields:

- `sceneId`
- `businessType`
- `businessName`
- `sourceNodeId`
- `broadcastDest`
- `broadcastTransportType`
- `broadcastAppType`
- `broadcastLifeTime`
- `broadcastStartTime`
- `broadcastInterval`
- `broadcastFragmentSize`
- `broadcastFragmentNum`

Example request:

```json
{
  "sceneId": 1,
  "businessType": "BROADCAST",
  "businessName": "broadcast-demo",
  "sourceNodeId": 1,
  "broadcastDest": "255.255.255.255",
  "broadcastTransportType": "UNRELIABLE",
  "broadcastAppType": "GENERAL",
  "broadcastLifeTime": "20S",
  "broadcastStartTime": "5S",
  "broadcastInterval": "1S",
  "broadcastFragmentSize": 256,
  "broadcastFragmentNum": 4
}
```

Generated `.app` line:

```text
MESSENGER-APP 1 255.255.255.255 UNRELIABLE GENERAL 20S 5S 1S 256 4
```

Mapping:

- `<src>` -> `sourceNodeId`
- `<dest>` -> `broadcastDest`
- `<transport_type>` -> `broadcastTransportType`
- `<app_type>` -> `broadcastAppType`
- `<life_time>` -> `broadcastLifeTime`
- `<start_time>` -> `broadcastStartTime`
- `<interval>` -> `broadcastInterval`
- `<fragment_size>` -> `broadcastFragmentSize`
- `<fragment_num>` -> `broadcastFragmentNum`

### 3. MULTICAST

Required fields:

- `sceneId`
- `businessType`
- `businessName`
- `sourceNodeId`
- `multicastDestination`
- `multicastItemsToSend`
- `multicastItemSize`
- `multicastInterval`
- `multicastStartTime`
- `multicastEndTime`

Example request:

```json
{
  "sceneId": 1,
  "businessType": "MULTICAST",
  "businessName": "multicast-demo",
  "sourceNodeId": 1,
  "multicastDestination": "224.0.1.0",
  "multicastItemsToSend": 100,
  "multicastItemSize": 512,
  "multicastInterval": "1S",
  "multicastStartTime": "1S",
  "multicastEndTime": "25S"
}
```

Generated `.app` line:

```text
MCBR 1 224.0.1.0 100 512 1S 1S 25S
```

Mapping:

- `<src>` -> `sourceNodeId`
- `<multicast-destination>` -> `multicastDestination`
- `<items-to-send>` -> `multicastItemsToSend`
- `<item-size>` -> `multicastItemSize`
- `<interval>` -> `multicastInterval`
- `<start-time>` -> `multicastStartTime`
- `<end-time>` -> `multicastEndTime`

## Response notes

### Create success

```json
{
  "message": "创建成功",
  "data": {
    "id": 12,
    "sceneId": 1,
    "businessType": "POISSON",
    "businessName": "poisson-demo"
  }
}
```

### Query success

The response contains:

- `configurationList`
- `page`
- `has_next`
- `has_previous`
- `totalPages`
- `total_count`

### Edit success

```json
{
  "status": "success"
}
```

### Delete success

```json
{
  "status": "success"
}
```
