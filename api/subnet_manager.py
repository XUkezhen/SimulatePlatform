from ipaddress import IPv4Network, IPv4Address
from collections import defaultdict
from django.db import transaction

from .models import Interface

class SubnetAllocationError(Exception):
    """自定义子网分配异常"""
    pass

class SubnetManager:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            # 存储各场景的链路子网池
            cls._instance.link_pools = defaultdict(cls.create_link_pool)
            # 默认接口IP分配器
            cls._instance.default_ip_manager = DefaultIPManager()
        return cls._instance

    @staticmethod
    def create_link_pool():
        """创建新的链路子网池（每个场景独立）"""
        return SubnetPool(base_subnet="190.0.0.0/16", alloc_prefix=24)

    def allocate_link_subnet(self, scene_id):
        try:
            # 从场景对应的池中获取子网
            pool = self.link_pools[scene_id]
            subnet_ip, subnet_mask = pool.get_next_available_subnet()
            return subnet_ip, subnet_mask  # 明确返回二元组
        except ValueError as e:
            # 改为抛出异常而不是返回错误信息
            raise SubnetAllocationError(f"子网分配失败: {str(e)}")


    def allocate_default_ip(self):
        """分配默认接口IP（全局共享196.168.0.0/24）"""
        return self.default_ip_manager.get_next_ip()


class DefaultIPManager:
    """
    默认IP分配管理器
    功能：为每个场景独立分配196.168.0.0/24子网内的IP地址
    特点：
       - 每个场景独立维护IP分配序列
       - 所有场景使用相同子网结构
       - 自动跳过已用IP地址
       - 支持并发安全分配
    """
    BASE_SUBNET = IPv4Network("196.168.0.0/24")
    SUBNET_MASK = "255.255.255.0"

    @classmethod
    @transaction.atomic
    def get_next_ip(cls, scene_id: int) -> str:
        """获取指定场景的下一个可用IP（从196.168.0.1开始）"""
        # 获取已分配的IP（使用行级锁保证并发安全）
        used_ips = set(
            Interface.objects.select_for_update().filter(
                node__sceneId=scene_id,
                is_default=True,
                subnet_mask=cls.SUBNET_MASK
            ).values_list('interface_ip', flat=True)
        )

        # 遍历可用IP范围（1-254）
        for host in range(1, 255):
            candidate_ip = f"196.168.0.{host}"
            if candidate_ip not in used_ips:
                return candidate_ip

        raise ValueError(f"场景 {scene_id} 的默认子网IP已耗尽")

    @classmethod
    def validate_ip(cls, ip: str) -> bool:
        """验证IP是否属于默认子网"""
        return IPv4Address(ip) in cls.BASE_SUBNET


class SubnetPool:
    """链路子网分配池（每个场景独立）"""

    def __init__(self, base_subnet, alloc_prefix):
        self.base_subnet = IPv4Network(base_subnet)
        self.alloc_prefix = alloc_prefix
        self.counter = 0  # 分配计数器
        self.allocated = set()  # 已分配子网

    def get_next_available_subnet(self):
        """获取下一个可用子网"""
        while True:
            # 生成子网地址：190.0.(counter).0/24
            third_octet = self.counter % 256
            fourth_octet = (self.counter // 256) % 256
            subnet = IPv4Network(
                f"190.0.{fourth_octet}.{third_octet}/{self.alloc_prefix}",
                strict=False
            )

            if str(subnet.network_address) not in self.allocated:
                self.allocated.add(str(subnet.network_address))
                self.counter += 1
                return str(subnet.network_address), str(subnet.netmask)

            self.counter += 1
            if self.counter > 65535:
                raise ValueError("子网池耗尽")