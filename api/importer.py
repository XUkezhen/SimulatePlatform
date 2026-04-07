# api/importer.py
import os
import re
from django.utils import timezone
from django.conf import settings
from api.models import Scene, Node, Subnet, Link, Interface


def import_scene_from_config(file_path: str):
    """
    读取 EXata .config 文件，反向入库：
      - Scene
      - Node（lon/lat/alt 先填 0）
      - Subnet（subnetType='link'）
      - Link
      - Interface（interfaceType='link'）
    可重复执行，不会重复插入。
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 1. 场景基本信息
    sim_time = 120
    for line in lines:
        if line.strip().startswith('SIMULATION-TIME'):
            raw = line.split()[1]
            sim_time = int(float(raw.replace('M', '').replace('S', '')))
            break

    scene_name = os.path.splitext(os.path.basename(file_path))[0]
    scene, _ = Scene.objects.get_or_create(
        sceneName=scene_name,
        defaults={
            'startTime': timezone.now(),
            'endTime':  timezone.now() + timezone.timedelta(seconds=sim_time),
            'simulationStep': 1,
        }
    )

    # 2. 节点（HOSTNAME 行）
    node_map = {}  # config_id -> Node
    for line in lines:
        m = re.match(r'\[(\d+)\]\s+HOSTNAME\s+(.+)', line.strip())
        if m:
            cfg_id, hostname = m.groups()
            node, _ = Node.objects.get_or_create(
                sceneId=scene,
                nodeName=hostname,
                defaults={
                    'nodeType': 'normalNode',
                    'lon': 0.0,
                    'lat': 0.0,
                    'alt': 0.0,
                    'startTime': scene.startTime,
                }
            )
            node_map[int(cfg_id)] = node

    # 3. 预创建链路用到的子网（subnetType='link'）
    # 预创建子网：只要出现 LINK N8-<ip> 就建
    subnet_map = {}
    for line in lines:
        m = re.search(r'LINK\s+N8-([\d\.]+)\s+{[^}]*}', line)
        if m:
            subnet_ip = m.group(1)
            if subnet_ip not in subnet_map:
                subnet, _ = Subnet.objects.get_or_create(
                    sceneId=scene,
                    subnetName=f"LinkSubnet-{subnet_ip}",
                    defaults={
                        'subnetIp': subnet_ip,
                        'subnetMask': '255.255.255.0',
                        'subnetType': 'link',
                    }
                )
                subnet_map[subnet_ip] = subnet

    # 4. 提取链路 & 创建接口
    for line in lines:
        m = re.search(r'LINK\s+N8-([\d\.]+)\s+{ (\d+), (\d+) }\s+LINK-UUID\s+LINK(\w+)', line)
        if m:
            subnet_ip, src_cfg, dst_cfg, link_uuid = m.groups()
            link, _ = Link.objects.get_or_create(
                sceneId=scene,
                linkName=f"LINK{link_uuid}",
                defaults={
                    'sourceNodeId':  node_map[int(src_cfg)],
                    'destinationNodeId': node_map[int(dst_cfg)],
                    'linkType': '无线',
                    'bandwidth': 10.0,
                    'packetHeaderSize': 224,
                    'subnetIp': subnet_ip,
                    'subnetMask': '255.255.255.0',
                }
            )

            # 创建两端接口（index 0 给源、index 1 给目）
            for suffix, cfg_id, idx in [('1', src_cfg, 0), ('2', dst_cfg, 1)]:
                iface, _ = Interface.objects.get_or_create(
                    node=node_map[int(cfg_id)],
                    interfaceIndex=idx,
                    defaults={
                        'interfaceType': 'link',
                        'interfaceIp': f"{subnet_ip.rsplit('.', 1)[0]}.{suffix}",
                        'subnetMask': '255.255.255.0',
                        'subnet': subnet_map[subnet_ip],
                    }
                )

            link.sourceInterface = Interface.objects.get(
                node=node_map[int(src_cfg)], interfaceIndex=0
            )
            link.destinationInterface = Interface.objects.get(
                node=node_map[int(dst_cfg)], interfaceIndex=1
            )
            link.save(update_fields=['sourceInterface', 'destinationInterface'])

    print(f"✅ 场景 {scene_name} 已导入："
          f"{len(node_map)} 节点，{len(subnet_map)} 子网，"
          f"{Link.objects.filter(sceneId=scene).count()} 链路")