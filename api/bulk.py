# api/bulk.py

#批量导入

import os
import re
import json
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.test import RequestFactory

from api.link_bulk import factory
from api.models import Scene, Node
from api.views import add_node_list
import os
import re
import json
import ipaddress
from django.conf import settings
from django.test import RequestFactory
from api.models import Scene
from api.views import add_link_list ,edit_node_list # 你写的视图函数

# 让 Django 知道当前项目的 settings 文件路径
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mytest.settings")
#
# # 初始化 Django
# django.setup()
_COORD_RE = re.compile(r'\(([^)]+)\)')  # 匹配括号中的坐标

def _parse_level_txt(level_path: str) -> dict:
    """
    解析 level.txt 生成 special_type_map:
    {
        "GEO": [1, 6, 12, 18],
        "PrimaryRegion": [...],
        ...
    }
    允许数字行换行/多空格/逗号。
    """
    special_type_map = {}
    cur_key = None
    with open(level_path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            # 只要含字母就认为是类别名
            if any(c.isalpha() for c in line):
                cur_key = line
                special_type_map.setdefault(cur_key, [])
            else:
                if cur_key is None:
                    continue
                # 允许逗号/多空格
                tokens = re.split(r'[,\s]+', line)
                ids = []
                for t in tokens:
                    if not t:
                        continue
                    # 只取纯数字的 token
                    if re.fullmatch(r'\d+', t):
                        ids.append(int(t))
                special_type_map[cur_key].extend(ids)
    return special_type_map

def _get_special_type(node_id: int, special_type_map: dict) -> str | None:
    for stype, ids in special_type_map.items():
        if node_id in ids:
            return stype
    return None


def _parse_nodes_file(nodes_path: str, scene_start_time):
    grouped_nodes = {}
    with open(nodes_path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue

            first_tok = line.split()[0]
            node_id = int(first_tok)
            time_s = int(line.split()[1])
            m = _COORD_RE.search(line)
            if not m:
                raise ValueError(f'无法在行中找到坐标: {line}')
            parts = [p for p in re.split(r'[,\s]+', m.group(1)) if p]
            if len(parts) < 3:
                raise ValueError(f'坐标不足3个值: {m.group(1)}')
            lat, lon, alt = map(float, parts[:3])

            entry = grouped_nodes.setdefault(
                node_id,
                {
                    'lat': lat,
                    'lon': lon,
                    'alt': alt,
                    'viaPoints': [],
                }
            )

            if time_s == 0:
                entry['lat'] = lat
                entry['lon'] = lon
                entry['alt'] = alt
            else:
                entry['viaPoints'].append(
                    {
                        'lon': lon,
                        'lat': lat,
                        'alt': alt,
                        'time': (scene_start_time + timedelta(seconds=time_s)).isoformat(),
                    }
                )

    return grouped_nodes

def import_nodes_from_file(scene_id: int):
    """
    从 {MEDIA_ROOT}/scene_files/{sceneName}/ 读取：
      - level.txt
      - {sceneName}.nodes  (形如: 1 0 (34.5661 -120.6120 0.0) 0 0 0)
    解析后通过 views.add_node_list 创建节点。
    """
    scene = Scene.objects.get(id=scene_id)
    base_dir = os.path.join(settings.MEDIA_ROOT, 'scene_files', scene.sceneName)
    level_path = os.path.join(base_dir, 'level.txt')
    nodes_path = os.path.join(base_dir, f'{scene.sceneName}.nodes')

    if not os.path.exists(nodes_path):
        raise FileNotFoundError(f'节点文件不存在: {nodes_path}')
    if not os.path.exists(level_path):
        raise FileNotFoundError(f'分层文件不存在: {level_path}')

    special_type_map = _parse_level_txt(level_path)
    factory = RequestFactory()

    total = ok = fail = 0
    errors = []

    parsed_nodes = _parse_nodes_file(nodes_path, scene.startTime)
    for node_id, node_info in parsed_nodes.items():
        total += 1
        try:
            payload = {
                'sceneId': scene_id,
                'nodeName': str(node_id),
                'nodeImage': 'transmitterUnit',
                'nodeType': 'normalNode',
                'lat': node_info['lat'],
                'lon': node_info['lon'],
                'alt': node_info['alt'],
                'startTime': scene.startTime.isoformat(),
                'specialType': _get_special_type(node_id, special_type_map),
                'viaPoints': node_info['viaPoints'],
            }

            req = factory.post(
                '/api/addNodeList/',
                data=json.dumps(payload),
                content_type='application/json'
            )
            resp = add_node_list(req)
            if getattr(resp, 'status_code', 500) == 200:
                ok += 1
            else:
                fail += 1
                errors.append((node_id, resp.content.decode('utf-8', 'ignore')))
        except Exception as e:
            fail += 1
            errors.append((node_id, str(e)))

    print(f'导入完成: 总计 {total}, 成功 {ok}, 失败 {fail}')
    for item, err in errors:
        print(f' - 失败 {item}: {err}')


# api/bulk.py
import os
import re
import json
from django.conf import settings
from django.test import RequestFactory
from django.urls import reverse
from api.models import Scene
from api.views import add_subnet_list   # 直接调用已有视图函数

def parse_node_list(node_list_str):
    nodes = []
    parts = [x.strip() for x in node_list_str.split(",")]
    for part in parts:
        if "thru" in part:
            start, end = map(int, part.split("thru"))
            nodes.extend(range(start, end+1))
        else:
            nodes.append(int(part))
    return nodes

def parse_config_and_add_subnets(scene_id):
    results = []
    factory = RequestFactory()

    scene = Scene.objects.get(id=scene_id)
    base_dir = os.path.join(settings.MEDIA_ROOT, 'scene_files', scene.sceneName)
    config_file = os.path.join(base_dir, f"{scene.sceneName}.config")

    def parse_node_list(node_list_str):
        """解析 {3, 8 thru 11} 样式的节点列表"""
        nodes = []
        for part in node_list_str.split(","):
            part = part.strip()
            if "thru" in part:
                start, end = map(int, part.split("thru"))
                nodes.extend(range(start, end + 1))
            else:
                nodes.append(int(part))
        return nodes

    with open(config_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 匹配子网定义：SUBNET-UUID SUB181 190.0.49.0 255.255.255.0 { 6, 7, 8, 9, 10 } 或 {3, 8 thru 11}
            match = re.match(r"^SUBNET\s+(?:N\d+-)?(\d+\.\d+\.\d+\.\d+)\s+\{([^}]+)\}\s+SUBNET-UUID\s+(\S+)", line)
            if not match:
                continue
            print(match)

            subnet_ip = match.group(1)  # 190.0.2.0
            raw_node_str = match.group(2)  # 3, 8 thru 11
            subnet_name = match.group(3)  # SUB3

            node_names = parse_node_list(raw_node_str)
            node_list = []

            for node_name in node_names:
                try:
                    node = Node.objects.get(sceneId=scene.id, nodeName=str(node_name))
                    node_list.append(node.id)
                except Node.DoesNotExist:
                    print(f"⚠️ 节点 {node_name} 在场景 {scene.sceneName} 中不存在")

            payload = {
                "sceneId": scene.id,
                "subnetIp": subnet_ip,
                "subnetMask": "255.255.255.0",#以后可以变
                "subnetName": subnet_name,
                "nodeList": node_list,
                "detail": {}  # 避免校验失败
            }

            # 模拟前端请求调用 add_subnet_list
            req = factory.post(
                reverse("add_subnet_list"),
                data=json.dumps(payload),
                content_type="application/json",
            )
            resp = add_subnet_list(req)
            results.append(json.loads(resp.content))

    return results



def parse_links(config_text: str, scene_id: int):
    """
    解析 EXata 的 Link 配置，返回链路参数列表
    """
    # 切分 [Link] block
    blocks = re.split(r"#\*+\s*\[Link\]\s*\*+", config_text)
    results = []

    for block in blocks:
        if not block.strip():
            continue

        # -----------------
        # 1. 主定义行
        # -----------------
        main_match = re.search(
            r"LINK N8-(\d+\.\d+\.\d+\.\d+)\s*\{\s*([^,}]+)\s*,\s*([^}]+)\s*\}\s*LINK-UUID\s+(\S+)",
            block
        )
        if not main_match:
            continue
        subnet_ip = main_match.group(1).strip()
        source_node = main_match.group(2).strip()
        dest_node = main_match.group(3).strip()
        link_uuid = main_match.group(4).strip()

        # -----------------
        # 2. 属性匹配
        # -----------------
        # 传播延迟
        delay_match = re.search(rf"\[\s*{link_uuid}/.*\]\s+LINK-PROPAGATION-DELAY\s+([\d\.eE+-]+)", block)
        transmission_delay = float(delay_match.group(1)) if delay_match else None

        # 报头大小
        header_match = re.search(rf"\[\s*{link_uuid}/.*\]\s+LINK-HEADER-SIZE-IN-BITS\s+(\d+)", block)
        header_size = int(header_match.group(1)) if header_match else None

        # 丢包率
        loss_match = re.search(rf"\[\s*{link_uuid}/.*\]\s+LINK-DROP-PROBABILITY\s+([\d\.eE+-]+)", block)
        packet_loss_rate = float(loss_match.group(1)) if loss_match else None

        # 传播速度
        speed_match = re.search(rf"\[\s*{link_uuid}/.*\]\s+LINK-PROPAGATION-SPEED\s+([\d\.eE+-]+)", block)
        transmission_speed = float(speed_match.group(1)) if speed_match else None

        # 带宽（可选）
        bw_match = re.search(rf"\[\s*{link_uuid}/.*\]\s+LINK-BANDWIDTH\s+([\d\.eE+-]+)", block)
        bandwidth = float(bw_match.group(1)) if bw_match else None

        # 链路类型（无线 / 有线）
        link_type = "无线" if re.search(rf"\[\s*{link_uuid}/.*\]\s+LINK-PHY-TYPE\s+WIRELESS", block) else "有线"

        # -----------------
        # 3. 判断 linkConfig
        # -----------------
        # 优先判断 DUMMY-GUI-SYMMETRIC-LINK
        dummy_match = re.search(rf"\[\s*{link_uuid}/.*\]\s+DUMMY-GUI-SYMMETRIC-LINK\s+(\S+)", block)
        link_config = True
        if dummy_match:
            val = dummy_match.group(1).strip().upper()
            print(f"val{val}")
            link_config = True if val == "YES" else False

        # -----------------
        # 4. 组装结果
        # -----------------
        link_data = {
            "sceneId": scene_id,
            "subnetIp": subnet_ip,
            "subnetMask": "255.255.255.0",
            "sourceNodeName": source_node,
            "destinationNodeName": dest_node,
            "linkType": link_type,
            "bandwidth": bandwidth,
            "packetHeaderSize": header_size,
            "transmissionDelay": transmission_delay,
            "packetLossRate": packet_loss_rate,
            "transmissionSpeed": transmission_speed,
            "linkConfig": link_config,
        }
        results.append(link_data)

    return results

def bulk_add_links(scene_id: int):
    """
    根据场景ID读取 config 文件并解析链路，然后通过模拟前端请求批量创建
    """
    scene = Scene.objects.get(id=scene_id)
    base_dir = os.path.join(settings.MEDIA_ROOT, "scene_files", scene.sceneName)
    config_path = os.path.join(base_dir, f"{scene.sceneName}.config")
    print("路径：",config_path)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"找不到配置文件: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config_text = f.read()

    parsed_links = parse_links(config_text, scene_id)

    results = []

    for link in parsed_links:
        print("正在创建链路：", link)
        # 链路
        request = factory.post(
            reverse("add_link_list"),
            data=json.dumps(link),
            content_type="application/json",
        )
        response = add_link_list(request)
        try:
            results.append(response.json())
        except Exception:
            results.append({"status": "error", "raw": response.content.decode("utf-8", errors="ignore")})
    print(parsed_links)
    return results



import os
import re
import json
from collections import defaultdict
from django.conf import settings
from api.models import Scene  # 你的模型路径可能要改

def parse_interface_details_by_scene(scene_id: int):
    """
    输入场景id -> 返回 {nodeId: [details...]} 的字典
    details 结构和前端一致：Physical / MAC / Routing
    """
    # 找到 config 文件路径
    scene = Scene.objects.get(id=scene_id)
    base_dir = os.path.join(settings.MEDIA_ROOT, "scene_files", scene.sceneName)
    config_path = os.path.join(base_dir, f"{scene.sceneName}.config")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config_text = f.read()

    # { nodeId: { interfaceIndex: {Physical, MAC, Routing} } }
    details_map = defaultdict(lambda: defaultdict(lambda: {
        "Physical": {}, "MAC": {}, "Routing": {}
    }))

    for line in config_text.splitlines():
        line = line.strip()
        if not line or not line.startswith("["):
            continue

        # 匹配 [SUB2/1/0 ...] KEY VALUE
        m = re.match(r"^\[([^\]]+)\]\s+(\S+)\s+(.+)$", line)
        if not m:
            continue

        interfaces_str, key, value = m.groups()
        interfaces = interfaces_str.split()

        for iface in interfaces:
            # SUB2/1/0 -> Subnet/Node/Interface
            parts = iface.split("/")
            if len(parts) < 3:
                continue
            node_id = parts[1]  # 节点号
            if_index = int(parts[2])  # 接口号

            # 层分类
            if key.startswith("PHY-") or key.startswith("ANTENNA-"):
                layer = "Physical"
            elif key.startswith("MAC-"):
                layer = "MAC"
            elif  key.startswith("ROUTING-"):
                layer = "Routing"
            # else:#可以根据实际，特定规划为MAC或其他层
            #     layer = "Other"
            else:
                # 如果没有匹配到已知层级，跳过
                continue
            # 去掉数组下标
            key_clean = re.sub(r"\[\d+\]", "", key)
            details_map[node_id][if_index][layer][key_clean] = value

    # 转成 {nodeId: [detail1, detail2, ...]}，接口按 index 排序
    result = {}
    for node_id, iface_dict in details_map.items():
        sorted_ifaces = [iface_dict[i] for i in sorted(iface_dict.keys())]
        result[node_id] = sorted_ifaces

    return result




def edit_details(scene_id):
    # 用法示例
    details_map = parse_interface_details_by_scene(scene_id)

    for node_name, details in details_map.items():
        try:
            node = Node.objects.get(nodeName=node_name, sceneId=scene_id)
        except Node.DoesNotExist:
            print(f"⚠️ 节点 {node_name} 在数据库里找不到")
            continue

        request = factory.put(
            f"/api/editNodeList/{node.id}",
            data=json.dumps({"details": details}),
            content_type="application/json"
        )
        response = edit_node_list(request, node_id=node.id)
        print(node_name, response.status_code, response.content)


import os, re, json
from django.conf import settings
from django.test import RequestFactory
from django.urls import reverse
from .models import Scene, Node
from .views import add_node_list, add_subnet_list, add_link_list

# 假设 _COORD_RE, _parse_level_txt, _get_special_type, parse_links 已定义

def import_scene_from_files(scene_id: int):
    """
    一次性从 {MEDIA_ROOT}/scene_files/{sceneName}/ 导入：
      - 节点（.nodes + level.txt）
      - 子网（.config）
      - 链路（.config）
    """
    scene = Scene.objects.get(id=scene_id)
    base_dir = os.path.join(settings.MEDIA_ROOT, 'scene_files', scene.sceneName)

    factory = RequestFactory()

    # ---------- 1. 导入节点 ----------
    nodes_path = os.path.join(base_dir, f'{scene.sceneName}.nodes')
    level_path = os.path.join(base_dir, 'level.txt')

    if not os.path.exists(nodes_path):
        raise FileNotFoundError(f'节点文件不存在: {nodes_path}')
    if not os.path.exists(level_path):
        raise FileNotFoundError(f'分层文件不存在: {level_path}')

    special_type_map = _parse_level_txt(level_path)

    total = ok = fail = 0
    errors = []

    parsed_nodes = _parse_nodes_file(nodes_path, scene.startTime)
    for node_id, node_info in parsed_nodes.items():
        total += 1
        try:
            payload = {
                'sceneId': scene_id,
                'nodeName': str(node_id),
                'nodeImage': 'transmitterUnit',
                'nodeType': 'normalNode',
                'lat': node_info['lat'],
                'lon': node_info['lon'],
                'alt': node_info['alt'],
                'startTime': scene.startTime.isoformat(),
                'specialType': _get_special_type(node_id, special_type_map),
                'viaPoints': node_info['viaPoints'],
            }
            req = factory.post('/api/addNodeList/', data=json.dumps(payload), content_type='application/json')
            resp = add_node_list(req)
            if getattr(resp, 'status_code', 500) == 200:
                ok += 1
            else:
                fail += 1
                errors.append((node_id, resp.content.decode('utf-8', 'ignore')))
        except Exception as e:
            fail += 1
            errors.append((node_id, str(e)))

    print(f'节点导入完成: 总计 {total}, 成功 {ok}, 失败 {fail}')
    for item, err in errors:
        print(f' - 节点失败 {item}: {err}')

    # ---------- 2. 导入子网 ----------
    def parse_node_list(node_list_str):
        nodes = []
        for part in node_list_str.split(","):
            part = part.strip()
            if "thru" in part:
                start, end = map(int, part.split("thru"))
                nodes.extend(range(start, end + 1))
            else:
                nodes.append(int(part))
        return nodes

    config_file = os.path.join(base_dir, f"{scene.sceneName}.config")
    results_subnets = []
    with open(config_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            match = re.match(r"^SUBNET\s+(?:N\d+-)?(\d+\.\d+\.\d+\.\d+)\s+\{([^}]+)\}\s+SUBNET-UUID\s+(\S+)", line)
            if not match:
                continue
            subnet_ip, raw_node_str, subnet_name = match.groups()

            node_names = parse_node_list(raw_node_str)
            node_list = []
            for node_name in node_names:
                try:
                    node = Node.objects.get(sceneId=scene.id, nodeName=str(node_name))
                    node_list.append(node.id)
                except Node.DoesNotExist:
                    print(f"⚠️ 节点 {node_name} 在场景 {scene.sceneName} 中不存在")

            payload = {
                "sceneId": scene.id,
                "subnetIp": subnet_ip,
                "subnetMask": "255.255.255.0",
                "subnetName": subnet_name,
                "nodeList": node_list,
                "detail": {}
            }
            req = factory.post(reverse("add_subnet_list"), data=json.dumps(payload), content_type="application/json")
            resp = add_subnet_list(req)
            results_subnets.append(json.loads(resp.content))
    print(f"子网导入完成: {len(results_subnets)} 条")

    # ---------- 3. 导入链路 ----------
    with open(config_file, "r", encoding="utf-8") as f:
        config_text = f.read()

    parsed_links = parse_links(config_text, scene_id)
    results_links = []
    for link in parsed_links:
        print("正在创建链路：", link)
        req = factory.post(reverse("add_link_list"), data=json.dumps(link), content_type="application/json")
        resp = add_link_list(req)
        try:
            results_links.append(resp.json())
        except Exception:
            results_links.append({"status": "error", "raw": resp.content.decode("utf-8", errors="ignore")})
    print(f"链路导入完成: {len(results_links)} 条")

    return {
        "nodes": {"total": total, "ok": ok, "fail": fail, "errors": errors},
        "subnets": results_subnets,
        "links": results_links,
    }


def update_nodes_with_chinese_names(scene_id: int):
    """
    根据 level.txt 内容，修改某个场景的节点名称 -> 中文类别 + 数字
    """
    # 英文 -> 中文映射表
    translation_map = {
        "GEO": "地球同步卫星",
        "PrimaryRegion": "一级节点",
        "SecondaryRegion": "二级节点",
        "GuidedMissile": "制导导弹",
        "LEO": "近地卫星",
    }

    special_type_map = {}
    cur_key = None
    scene_name = Scene.objects.get(id=scene_id).sceneName
    level_path = r"D:\wuyuan_project\mytestdjango_five_final\scene_files\102202S\level.txt"#输入路径
    # 先解析 level.txt
    with open(level_path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if any(c.isalpha() for c in line):
                cur_key = line
                special_type_map.setdefault(cur_key, [])
            else:
                if cur_key is None:
                    continue
                tokens = re.split(r'[,\s]+', line)
                ids = [int(t) for t in tokens if t.isdigit()]
                special_type_map[cur_key].extend(ids)

    # 批量修改节点名称
    updated_nodes = []
    with transaction.atomic():
        for key, ids in special_type_map.items():
            zh_name = translation_map.get(key, key)
            for num in ids:
                try:
                    node = Node.objects.get(sceneId=scene_id, nodeName=str(num))
                    node.nodeName = f"{zh_name}-{num}"
                    node.save()
                    updated_nodes.append(node.nodeName)
                except Node.DoesNotExist:
                    print(f"⚠️ 场景 {scene_id} 中未找到节点 {num}")

    print(f"✅ 已修改节点: {updated_nodes}")
    return updated_nodes

if __name__ == "__main__":
    import_scene_from_files(30)#场景id
