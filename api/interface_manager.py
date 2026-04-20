import ipaddress

from django.db.models import Max
from django.db import transaction

from .models import Interface,Subnet


def get_next_default_interface_ip():
    # 获取已有的默认接口 IP
    default_interfaces = Interface.objects.filter(is_default=True)
    if not default_interfaces.exists():
        return '196.168.0.1'  # 第一个默认接口 IP

    # 找到最大的 IP 地址
    max_ip = max(default_interfaces, key=lambda x: ipaddress.IPv4Address(x.interface_ip))
    max_ip_int = int(ipaddress.IPv4Address(max_ip.interface_ip))

    # 计算下一个 IP 地址
    next_ip_int = max_ip_int + 1
    next_ip = str(ipaddress.IPv4Address(next_ip_int))

    return next_ip
def create_default_interface(node):
    # 检查是否已经有默认接口
    if not Interface.objects.filter(node=node, is_default=True).exists():
        # 获取下一个可用的默认接口 IP
        next_ip = get_next_default_interface_ip()
        # 创建默认接口
        default_interface = Interface(
            node=node,
            interface_ip=next_ip,
            interface_index=0,
            subnet_mask='255.255.255.0',
            is_default=True
        )
        default_interface.save()
        return default_interface
    return None

def get_available_interface(node):
    # 获取未被分配的默认接口
    default_interface = Interface.objects.filter(node=node, is_default=True, is_allocated=False).first()
    if default_interface:
        return default_interface
    # 如果没有可用的默认接口，返回 None
    return None

def create_new_interface(node):
    # 获取当前节点的最大接口序号
    max_index = Interface.objects.filter(node=node).aggregate(Max('interface_index'))['interface_index__max'] or -1
    new_index = max_index + 1

    # 创建新的接口
    new_interface = Interface(
        node=node,
        interface_ip=f'196.168.0.{new_index + 1}',  # 默认子网 IP 范围
        interface_index=new_index,
        subnet_mask='255.255.255.0'
    )
    new_interface.save()

    # 将新接口添加到默认子网
    default_subnet, _ = Subnet.objects.get_or_create(
        sceneId=node.sceneId,
        subnetIp="196.168.0.0",
        subnet_mask='255.255.255.0'
    )
    default_subnet.interfaces.add(new_interface)

    return new_interface


@transaction.atomic
def reorder_interfaces_by_scene(scene_id):
    """Keep subnet interfaces before link interfaces for every node in a scene."""
    if scene_id in [None, '']:
        return

    interfaces = list(
        Interface.objects.select_for_update()
        .filter(node__sceneId_id=scene_id)
        .select_related('node')
        .order_by('node_id', 'interfaceType', 'interfaceIndex', 'id')
    )
    if not interfaces:
        return

    interfaces_by_node = {}
    for interface in interfaces:
        interfaces_by_node.setdefault(interface.node_id, []).append(interface)

    priority = {
        Interface.InterfaceTypeChoices.SUB: 0,
        Interface.InterfaceTypeChoices.LINK: 1,
    }

    pending_updates = []
    for node_interfaces in interfaces_by_node.values():
        ordered = sorted(
            node_interfaces,
            key=lambda item: (
                priority.get(item.interfaceType, 99),
                item.interfaceIndex if item.interfaceIndex is not None else 10**9,
                item.id,
            ),
        )

        for next_index, interface in enumerate(ordered):
            if interface.interfaceIndex != next_index:
                pending_updates.append((interface, next_index))

    if not pending_updates:
        return

    # Use temporary negative indexes first to avoid unique_together conflicts.
    for offset, (interface, _) in enumerate(pending_updates, start=1):
        interface.interfaceIndex = -offset
        interface.save(update_fields=['interfaceIndex'])

    for interface, next_index in pending_updates:
        interface.interfaceIndex = next_index
        interface.save(update_fields=['interfaceIndex'])
