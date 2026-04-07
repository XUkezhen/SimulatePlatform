import re
from api.views import add_link_list  # 你之前写的视图函数
from django.test import RequestFactory
import json
def parse_links(content: str, scene_id=23):
    """
    解析EXata的Link配置，返回链路参数列表
    """
    # 按照 [Link] 分块
    blocks = re.split(r"#\*+\s*\[Link\]\s*\*+", content)
    results = []

    for block in blocks:
        if not block.strip():
            continue

        # LINK N8-190.0.5.0 { 2, 3 } LINK-UUID LINK3
        m = re.search(r"LINK N8-(\d+\.\d+\.\d+\.\d+) \{ ([^,}]+),\s*([^}]+) \}", block)
        if not m:
            continue

        subnet_ip = m.group(1)
        source_node = m.group(2).strip()
        dest_node = m.group(3).strip()

        # 带宽（有些配置是 bps，这里先做个缩放）
        bw_match = re.search(r"LINK-BANDWIDTH\s+([\d\.]+)", block)
        bandwidth = float(bw_match.group(1)) / 1000000 if bw_match else 10

        # 报头大小
        header_match = re.search(r"LINK-HEADER-SIZE-IN-BITS\s+(\d+)", block)
        header_size = int(header_match.group(1)) if header_match else 224

        # 链路类型
        link_type = "无线" if "LINK-PHY-TYPE WIRELESS" in block else "有线"

        # 组装数据（模拟前端发过来的格式）
        link_data = {
            "sceneId": scene_id,
            "subnetIp": subnet_ip,
            "subnetMaskyy": "255.255.255.0",
            "transmissionSpeed": 300000000,
            "bandwidth": bandwidth,
            "packetHeaderSize": header_size,
            "sourceNodeName": source_node,
            "destinationNodeName": dest_node,
            "linkType": link_type,
        }
        results.append(link_data)

    return results


factory = RequestFactory()


def bulk_add_links(config_text, scene_id):
    parsed_links = parse_links(config_text, scene_id)  # ✅ 解析链路

    for link in parsed_links:
        print("正在创建链路：", link)
        request = factory.post(
            "/api/add_link_list/",
            data=json.dumps(link),
            content_type="application/json"
        )
        # 调用视图函数
        response = add_link_list(request)
        print("返回状态:", response.status_code)
        try:
            print("返回内容:", response.json())
        except Exception:
            print("返回原始:", response.content)

