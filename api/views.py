
from pathlib import Path
'''
以下是lykcode
'''
import json
import re
import signal
import socket
import os
import struct
import time
import threading
import binascii

import psutil
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from threading import Lock

from .consumers import trigger_push

from django.http import JsonResponse
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# 以下软件包和sgp4相关
from sgp4.api import Satrec, WGS72
from sgp4.functions import jday
import pymap3d as pm
from datetime import datetime, timedelta

from links import StaticDynamicLinkCalculator

from runExata import ExataSimulator
import os
import subprocess
import signal
import psutil  # 需要先安装: pip install psutil


import copy
import ipaddress
import json
import re
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from .models import *
from .forms import *
from django.db.models import Q, Max, Prefetch
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from .serializers import ConfigurationSerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from datetime import datetime
from .subnet_manager import SubnetManager, SubnetAllocationError, DefaultIPManager
from ipaddress import IPv4Network, AddressValueError
from django.shortcuts import get_object_or_404
import os
import shutil
from django.conf import settings
@require_http_methods(["POST"])
@csrf_exempt
def add_scene_list(request):
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Only POST method is allowed'
        }, status=405)

    try:
        # 解析 JSON 数据
        data = json.loads(request.body)
        scene_name = data.get('sceneName')
        start_time_str = data.get('startTime')
        end_time_str = data.get('endTime')
        simulation_step = data.get('simulationStep')
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON format'
        }, status=400)

    # 验证必要参数是否存在
    if not all([scene_name, start_time_str, end_time_str, simulation_step]):
        return JsonResponse({
            'status': 'error',
            'message': 'Missing required fields: sceneName, startTime, endTime, simulationStep'
        }, status=400)

    # 尝试转换时间格式
    try:
        start_time = timezone.datetime.fromisoformat(start_time_str)
        end_time = timezone.datetime.fromisoformat(end_time_str)
    except (ValueError, TypeError):
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid datetime format. Use ISO format: YYYY-MM-DDTHH:MM:SS'
        }, status=400)

    # 验证仿真步长为整数
    try:
        simulation_step = int(simulation_step)
        if simulation_step <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({
            'status': 'error',
            'message': 'simulationStep must be a positive integer'
        }, status=400)

    try:
        # 创建场景对象
        scene = Scene.objects.create(
            sceneName=scene_name,
            startTime=start_time,
            endTime=end_time,
            simulationStep=simulation_step
        )

        # 创建默认子网
        default_subnet = Subnet.objects.create(
            sceneId=scene,
            subnetName=f"{scene_name} (Default)",
            subnetIp="169.0.0.0",
            subnetMask="255.255.255.0",
            subnetType = 'sub'
        )

        # 成功响应
        return JsonResponse({
            'status': 'success',
            'sceneId': scene.id,
            'sceneName': scene.sceneName
        })

    except ValidationError as e:
        # 捕获模型验证错误
        errors = {}
        if hasattr(e, 'message_dict'):
            errors = e.message_dict
        else:
            errors = {'non_field_errors': [str(e)]}

        return JsonResponse({
            'status': 'error',
            'errors': errors
        }, status=400)

    except Exception as e:
        # 捕获其他异常
        return JsonResponse({
            'status': 'error',
            'message': f'Internal server error: {str(e)}'
        }, status=500)

path = ""
absolute_path = Path(path)

@require_http_methods(["DELETE"])
@csrf_exempt
def delete_scene_list(request, scene_id):
    try:
        scene = Scene.objects.get(id=scene_id)
        scene.delete()
        return JsonResponse({'status': 'success'})
    except Scene.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '场景不存在'}, status=404)



@require_http_methods(["PUT"])
@csrf_exempt
def edit_scene_list(request, scene_id):
    try:
        # 获取现有的场景
        scene = Scene.objects.get(id=scene_id)

        # 解析请求体中的 JSON 数据
        data = json.loads(request.body)

        # 更新场景信息
        new_scene_name = data.get('sceneName', scene.sceneName)
        new_start_time = data.get('startTime', scene.startTime)
        new_end_time = data.get('endTime', scene.endTime)
        new_simulation_step = data.get('simulationStep', scene.simulationStep)

        # 验证场景名称是否重复
        if Scene.objects.exclude(id=scene_id).filter(sceneName=new_scene_name).exists():
            return JsonResponse({'status': 'error', 'message': '该场景名称已存在，请使用其他名称'}, status=400)

        # 验证开始时间是否早于结束时间
        if new_start_time >= new_end_time:
            return JsonResponse({'status': 'error', 'message': '开始时间必须早于结束时间'}, status=400)

        # 更新场景信息
        scene.sceneName = new_scene_name
        scene.startTime = new_start_time
        scene.endTime = new_end_time
        scene.simulationStep = new_simulation_step
        scene.save()

        return JsonResponse({'status': 'success'})

    except Scene.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '场景不存在'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_http_methods(["GET"])
@csrf_exempt
def get_scene_list(request):
    page_size = int(request.GET.get('size', 10))
    page_number = int(request.GET.get('page', 1))
    scene_name = request.GET.get('sceneName', '')
    if scene_name:
        # 如果提供了场景名称，进行模糊查询
        scenes = Scene.objects.filter(Q(sceneName__icontains=scene_name))
    else:
        # 如果没有提供场景名称，查询所有场景
        scenes = Scene.objects.all()
    # 使用 Paginator 类进行分页
    paginator = Paginator(scenes, page_size)
    page_obj = paginator.get_page(page_number)
    # 准备要返回的数据
    scene_list = [{
        'id': scene.id,
        'sceneName': scene.sceneName,
        'startTime': scene.startTime.isoformat(),
        'endTime': scene.endTime.isoformat(),
        'simulationStep': scene.simulationStep
    } for scene in page_obj]

    # 返回分页后的场景列表
    return JsonResponse({
        'sceneList': scene_list,
        'page': page_obj.number,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'total_pages': page_obj.paginator.num_pages,
        'total_count': paginator.count
    })

'''
⬇⬇⬇⬇表3,子网
'''


@require_http_methods(["POST"])
@csrf_exempt
def add_subnet_list(request):
    try:
        data = json.loads(request.body)

        # 验证必填字段
        required_fields = ['sceneId', 'subnetIp', 'subnetMask', 'subnetName']
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            return JsonResponse({
                'status': 'error',
                'message': f'缺少必填字段: {", ".join(missing_fields)}'
            }, status=400)

        scene_id = data['sceneId']
        subnet_ip = data['subnetIp']
        subnet_mask = data['subnetMask']
        subnet_name = data['subnetName']
        node_list = data.get('nodeList', [])

        # 验证场景存在
        try:
            scene = Scene.objects.get(id=scene_id)
        except Scene.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'场景ID {scene_id} 不存在'
            }, status=404)

        # 验证子网名称唯一性
        if Subnet.objects.filter(sceneId=scene, subnetName=subnet_name).exists():
            return JsonResponse({
                'status': 'error',
                'message': f'场景 "{scene.sceneName}" 中已存在名为 "{subnet_name}" 的子网'
            }, status=400)

        # 新增：验证子网网段唯一性（相同IP+掩码）
        if Subnet.objects.filter(sceneId=scene,subnetIp=subnet_ip, subnetMask=subnet_mask).exists():
            return JsonResponse({
                'status': 'error',
                'message': f'子网网段 {subnet_ip}/{subnet_mask} 已存在'
            }, status=400)

        # 验证子网IP和掩码格式
        try:
            # 创建网络对象用于后续IP分配
            network = ipaddress.IPv4Network(f"{subnet_ip}/{subnet_mask}", strict=False)

            # 验证掩码是否合法
            mask_value = int(ipaddress.IPv4Address(subnet_mask))
            bin_str = bin(mask_value)[2:].zfill(32)
            if '01' in bin_str:
                raise ValidationError("无效的子网掩码格式")

        except (ipaddress.AddressValueError, ValueError, ipaddress.NetmaskValueError) as e:
            return JsonResponse({
                'status': 'error',
                'message': f'无效的IP或子网掩码: {str(e)}'
            }, status=400)
        except ValidationError as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

        # 使用事务确保原子操作
        with transaction.atomic():
            # 创建子网
            subnet = Subnet.objects.create(
                sceneId=scene,
                subnetName=subnet_name,
                subnetIp=subnet_ip,
                subnetMask=subnet_mask,
                subnetType = "sub"
            )
            # 准备IP分配（跳过网络地址和广播地址）
            ip_generator = network.hosts()
            allocated_ips = set()

            # 处理每个节点
            for node_id in node_list:
                try:
                    node = Node.objects.get(id=node_id, sceneId=scene)

                    # 获取下一个可用IP
                    while True:
                        new_ip = str(next(ip_generator))
                        # 确保IP在子网范围内且未分配
                        if new_ip not in allocated_ips:
                            allocated_ips.add(new_ip)
                            break

                    # 查找节点的默认接口
                    default_interface = node.interfaces.filter(is_default=True).first()

                    if default_interface:#不该是默认接口了！！
                        # 更新现有默认接口
                        default_interface.subnet = subnet
                        default_interface.interfaceIp = new_ip
                        default_interface.subnetMask = subnet_mask
                        default_interface.is_allocated = False
                        default_interface.is_default = False
                        default_interface.interfaceType = "sub"
                        default_interface.full_clean()
                        default_interface.save()
                    else:
                        # 创建新接口作为默认接口
                        # 查找可用接口索引（0-3）
                        existing_indices = node.interfaces.values_list('interfaceIndex', flat=True)
                        for index in range(4):
                            if index not in existing_indices:
                                interface_index = index
                                break
                        else:
                            # 找不到可用接口索引
                            return JsonResponse({
                                'status': 'error',
                                'message': f'节点 {node_id} 已达到最大接口数 (4个)'
                            }, status=400)

                        Interface.objects.create(
                            node=node,
                            interfaceIp=new_ip,
                            interfaceIndex=interface_index,
                            subnetMask=subnet_mask,
                            is_default=False,
                            is_allocated=False,
                            subnet=subnet,
                            interfaceType = "sub"
                        )

                except Node.DoesNotExist:
                    # 节点不存在，跳过处理但继续创建子网
                    continue
                except ValidationError as e:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'节点 {node_id} 接口处理失败: {str(e)}'
                    }, status=400)
                except StopIteration:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'子网 {subnet_ip}/{subnet_mask} 中没有足够可用IP地址'
                    }, status=400)

        return JsonResponse({
            'status': 'success',
            'message': '子网创建成功',
            'subnetId': subnet.id
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': '无效的JSON格式'}, status=400)
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_http_methods(["PUT"])
@csrf_exempt
def edit_subnet_list(request, subnet_id):
    if request.method != 'PUT':
        return JsonResponse({
            'status': 'error',
            'message': '仅支持PUT方法'
        }, status=405)
    try:
        # 从请求体获取JSON数据
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': '无效的JSON格式'}, status=400)
        # 获取子网对象
        try:
            subnet = Subnet.objects.select_related('sceneId').get(id=subnet_id)
        except Subnet.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'子网ID {subnet_id} 不存在'
            }, status=404)
        scene = subnet.sceneId
        try:
            default_subnet = Subnet.objects.get(sceneId=scene, subnetName=f"{scene.sceneName} (Default)")
        except (Scene.DoesNotExist, Subnet.DoesNotExist):
            default_subnet = None
        # 获取字段值
        subnet_ip = data.get('subnetIp', subnet.subnetIp)
        subnet_mask = data.get('subnetMask', subnet.subnetMask)
        subnet_name = data.get('subnetName', subnet.subnetName)
        node_list = data.get('nodeList', None)

        # 如果提供了新子网名称，才验证唯一性
        if 'subnetName' in data and subnet_name != subnet.subnetName:
            if Subnet.objects.filter(
                    sceneId=scene,
                    subnetName=subnet_name
            ).exclude(id=subnet_id).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': f'场景 "{scene.sceneName}" 中已存在名为 "{subnet_name}" 的子网'
                }, status=400)
        # 如果提供了新IP或掩码，才验证网段唯一性
        if ('subnetIp' in data or 'subnetMask' in data) and \
                (subnet_ip != subnet.subnetIp or subnet_mask != subnet.subnetMask):
            if Subnet.objects.filter(
                    subnetIp=subnet_ip,
                    subnetMask=subnet_mask,
                    sceneId=scene
            ).exclude(id=subnet_id).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': f'子网网段 {subnet_ip}/{subnet_mask} 已被其他子网使用'
                }, status=400)

        # 验证IP和掩码格式
        network = None
        if 'subnetIp' in data or 'subnetMask' in data:
            try:
                # 创建网络对象
                network = ipaddress.IPv4Network(f"{subnet_ip}/{subnet_mask}", strict=False)

                # 验证掩码格式
                mask_value = int(ipaddress.IPv4Address(subnet_mask))
                bin_str = bin(mask_value)[2:].zfill(32)
                if '01' in bin_str:
                    raise ValidationError("无效的子网掩码格式")

            except (ipaddress.AddressValueError, ValueError, ipaddress.NetmaskValueError) as e:
                return JsonResponse({
                    'status': 'error',
                    'message': f'无效的IP或子网掩码: {str(e)}'
                }, status=400)
            except ValidationError as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=400)
        else:
            # 使用原有网络配置
            network = ipaddress.IPv4Network(f"{subnet.subnetIp}/{subnet.subnetMask}", strict=False)

        # 使用事务确保原子操作
        with transaction.atomic():
            # 更新子网基本信息
            if any(field in data for field in ['subnetName', 'subnetIp', 'subnetMask']):
                subnet.subnetName = subnet_name
                subnet.subnetIp = subnet_ip
                subnet.subnetMask = subnet_mask
                subnet.full_clean()
                subnet.save()

            # 只有提供了节点列表才更新节点
            if node_list is not None:
                # 获取当前子网的所有节点
                current_nodes = set(subnet.interfaces.values_list('node__id', flat=True))
                new_nodes = set(node_list)

                # 需要移除的节点（当前在子网中但不在新列表中）
                nodes_to_remove = current_nodes - new_nodes

                # 需要添加的节点（在新列表中但当前不在子网中）
                nodes_to_add = new_nodes - current_nodes

                for node_id in current_nodes:
                    node = Node.objects.get(id=node_id, sceneId=scene)
                    interfaces = Interface.objects.filter(
                        node=node,
                        subnet=subnet
                    )
                    interfaces.delete()



                # === 处理需要移除的节点 ===
                for node_id in nodes_to_remove:
                    try:
                        node = Node.objects.get(id=node_id, sceneId=scene)
                        interfaces = Interface.objects.filter(node=node, subnet=subnet)

                        for interface in interfaces:
                            total_interfaces = node.interfaces.count()

                            if interface.is_default or total_interfaces == 1:
                                # 移动到默认子网并重新分配 IP
                                allocated_ips = set(
                                    Interface.objects.filter(subnet=default_subnet)
                                    .exclude(interfaceIp__isnull=True)
                                    .values_list('interfaceIp', flat=True)
                                )
                                network = ipaddress.IPv4Network(
                                    f"{default_subnet.subnetIp}/{default_subnet.subnetMask}", strict=False)

                                # 找可用IP
                                new_ip = None
                                for ip in network.hosts():
                                    ip_str = str(ip)
                                    if ip_str not in allocated_ips:
                                        new_ip = ip_str
                                        break

                                if not new_ip:
                                    raise ValidationError("默认子网中没有可用的 IP 地址")

                                interface.subnet = default_subnet
                                interface.interfaceIp = new_ip
                                interface.subnetMask = default_subnet.subnetMask
                                interface.is_allocated = True
                                interface.is_default = True
                                interface.save()
                            else:
                                # 否则删除接口
                                interface.delete()

                    except Node.DoesNotExist:
                        continue

                # ... 前面的代码保持不变 ...

                # === 处理需要添加的节点 ===
                # 先获取子网所有已分配IP（一次性查询提高效率）
                allocated_ips = set(
                    Interface.objects.filter(subnet=subnet)
                    .exclude(interfaceIp__isnull=True)
                    .values_list('interfaceIp', flat=True)
                )

                # 生成子网所有可用IP（按顺序）
                all_ips = [str(ip) for ip in network.hosts()]
                available_ips = [ip for ip in all_ips if ip not in allocated_ips]

                if len(available_ips) < len(new_nodes):
                    return JsonResponse({
                        'status': 'error',
                        'message': f'子网中可用IP不足（需要 {len(new_nodes)} 个，可用 {len(available_ips)} 个）'
                    }, status=400)

                # 按顺序分配IP
                ip_iter = iter(available_ips)

                for node_id in new_nodes:
                    try:
                        node = Node.objects.get(id=node_id, sceneId=scene)
                        new_ip = next(ip_iter)

                        # 查找节点的默认接口
                        default_interface = node.interfaces.filter(is_default=True).first()

                        if default_interface:
                            # 更新现有默认接口：移动到当前子网
                            default_interface.subnet = subnet
                            default_interface.interfaceIp = new_ip
                            default_interface.subnetMask = subnet_mask
                            default_interface.is_allocated = False
                            default_interface.is_default  = False
                            default_interface.save()
                        else:
                            # 没有默认接口，创建新接口作为默认接口
                            existing_indices = node.interfaces.values_list('interfaceIndex', flat=True)
                            interface_index = None
                            for index in range(4):
                                if index not in existing_indices:
                                    interface_index = index
                                    break

                            if interface_index is None:
                                return JsonResponse({
                                    'status': 'error',
                                    'message': f'节点 {node_id} 已达到最大接口数 (4个)'
                                }, status=400)

                            # 创建新接口并设为默认
                            Interface.objects.create(
                                node=node,
                                interfaceIp=new_ip,
                                interfaceIndex=interface_index,
                                subnetMask=subnet_mask,
                                is_default=False,
                                is_allocated=False,
                                subnet=subnet
                            )

                    except Node.DoesNotExist:
                        continue

                # ... 后面的代码保持不变 ...

                # === 批量处理默认子网的IP分配 ===
                # 为移动到默认子网的节点分配IP（批量操作提高效率）
                if default_subnet and nodes_to_remove:
                    # 获取默认子网的网络配置
                    default_network = ipaddress.IPv4Network(
                        f"{default_subnet.subnetIp}/{default_subnet.subnetMask}",
                        strict=False
                    )

                    # 获取默认子网所有已分配IP
                    default_allocated_ips = set(
                        Interface.objects.filter(subnet=default_subnet)
                        .exclude(interfaceIp__isnull=True)
                        .values_list('interfaceIp', flat=True)
                    )

                    # 生成默认子网所有可用IP（按顺序）
                    default_all_ips = [str(ip) for ip in default_network.hosts()]
                    default_available_ips = [ip for ip in default_all_ips if ip not in default_allocated_ips]

                    # 获取需要分配IP的接口
                    interfaces_to_update = []
                    for node_id in nodes_to_remove:
                        try:
                            node = Node.objects.get(id=node_id, sceneId=scene)
                            for interface in node.interfaces.filter(subnet=default_subnet, interfaceIp__isnull=True):
                                if default_available_ips:
                                    interface.interfaceIp = default_available_ips.pop(0)
                                    interface.is_allocated = True
                                    interfaces_to_update.append(interface)
                        except Node.DoesNotExist:
                            continue

                    # 批量更新接口
                    if interfaces_to_update:
                        Interface.objects.bulk_update(
                            interfaces_to_update,
                            ['interfaceIp', 'is_allocated']
                        )

        return JsonResponse({
            'status': 'success',
            'message': '子网更新成功',
            'subnetId': subnet.id
        })

    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def get_subnet_list(request):
    """
    获取子网列表接口（仅返回类型为 sub 的子网）

    查询参数:
    - subnetId (可选): 指定子网ID，获取单个子网详情
    - sceneId (可选): 指定场景ID，获取该场景下的所有子网
    - subnetName (可选): 子网名称模糊搜索
    - subnetIp (可选): 指定子网 IP 精确匹配

    响应:
    - 成功: {'status': 'success', 'subnets': [子网数据]}
    - 错误: {'status': 'error', 'message': 错误信息}
    """
    try:
        # 获取查询参数
        subnet_id = request.GET.get('subnetId')
        scene_id = request.GET.get('sceneId')
        subnet_name = request.GET.get('subnetName')
        subnet_ip = request.GET.get('subnetIp')

        # 预取接口数据
        interface_prefetch = Prefetch(
            'interfaces',
            queryset=Interface.objects.select_related('node').only(
                'id', 'interfaceIp', 'interfaceIndex', 'subnetMask',
                'is_default', 'is_allocated', 'node__id', 'node__nodeName'
            )
        )

        # 构建基础查询集（只查询类型为 sub 的子网）
        queryset = Subnet.objects.filter(subnetType=Subnet.SubnetTypeChoices.SUB)\
                                 .prefetch_related(interface_prefetch)\
                                 .select_related('sceneId')

        # 过滤条件
        if subnet_id:
            try:
                subnet_id = int(subnet_id)
                queryset = queryset.filter(id=subnet_id)
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'subnetId 必须是整数'}, status=400)

        if scene_id:
            try:
                scene_id = int(scene_id)
                queryset = queryset.filter(sceneId=scene_id)
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'sceneId 必须是整数'}, status=400)

        if subnet_name:
            queryset = queryset.filter(subnetName__icontains=subnet_name)

        if subnet_ip:
            queryset = queryset.filter(subnetIp=subnet_ip)

        # 排序执行查询
        queryset = queryset.order_by('sceneId__id', 'id')
        subnets = list(queryset)

        if subnet_id and not subnets:
            return JsonResponse({'status': 'error', 'message': f'子网ID {subnet_id} 不存在'}, status=404)

        # 构建响应数据
        subnet_list = []
        for subnet in subnets:
            subnet_data = {
                'id': subnet.id,
                'sceneId': subnet.sceneId.id,
                'sceneName': subnet.sceneId.sceneName,
                'subnetName': subnet.subnetName,
                'subnetIp': subnet.subnetIp,
                'subnetMask': subnet.subnetMask,
                'subnetType': subnet.subnetType,
                'interfaceCount': subnet.interfaces.count(),
                'interfaces': []
            }

            for interface in subnet.interfaces.all():
                subnet_data['interfaces'].append({
                    'id': interface.id,
                    'nodeId': interface.node.id,
                    'nodeName': interface.node.nodeName,
                    'interfaceIp': interface.interfaceIp,
                    'interfaceIndex': interface.interfaceIndex,
                    'subnetMask': interface.subnetMask,
                    'isDefault': interface.is_default,
                    'isAllocated': interface.is_allocated
                })

            subnet_list.append(subnet_data)

        return JsonResponse({
            'status': 'success',
            'count': len(subnet_list),
            'subnets': subnet_list
        })

    except ObjectDoesNotExist:
        return JsonResponse({'status': 'error', 'message': '请求的资源不存在'}, status=404)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'服务器内部错误: {str(e)}'}, status=500)



@csrf_exempt
@require_http_methods(["DELETE"])  # 限制只接受 DELETE 请求
@transaction.atomic
def delete_subnet_list(request, subnet_id=None):
    # 优先从 URL 路径参数获取 subnet_id
    if subnet_id is None:
        # 如果 URL 中未提供，尝试从查询字符串获取
        subnet_id = request.GET.get('subnetId')
        if not subnet_id:
            # 最后尝试从请求体获取（不推荐）
            try:
                data = json.loads(request.body)
                subnet_id = data.get('subnetId')
            except (json.JSONDecodeError, TypeError):
                pass

    if not subnet_id:
        return JsonResponse({
            'status': 'error',
            'message': '缺少子网ID参数'
        }, status=400)

    try:
        # 确保 subnet_id 是整数
        subnet_id = int(subnet_id)
    except (TypeError, ValueError):
        return JsonResponse({
            'status': 'error',
            'message': '无效的子网ID格式'
        }, status=400)

    try:
        # 获取子网对象
        subnet = Subnet.objects.get(id=subnet_id)
    except Subnet.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': f'子网ID {subnet_id} 不存在'
        }, status=404)

    try:
        # 获取所有属于该子网的接口及其相关节点
        interfaces = Interface.objects.filter(subnet=subnet).select_related('node')
        affected_nodes = set(interface.node for interface in interfaces)

        # 删除这些接口
        interfaces.delete()

        # 处理每个受影响的节点
        for node in affected_nodes:
            # 获取节点剩余接口
            remaining_interfaces = node.interfaces.all()

            if remaining_interfaces.count() == 0:
                # 如果没有剩余接口，创建默认接口
                create_default_interface(node)

        # 删除子网
        subnet_name = subnet.subnetName
        subnet.delete()

        return JsonResponse({
            'status': 'success',
            'message': f'子网 "{subnet_name}" 已成功删除',
            'deleted_subnet_id': subnet_id,
            'affected_nodes': [node.id for node in affected_nodes]
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'删除子网失败: {str(e)}'
        }, status=500)

'''
节点表
'''


def create_default_interface(node):
    """
    为节点创建默认接口（序号0）
    :param node: 节点对象
    :return: 创建的接口对象
    """
    if not node.sceneId:
        raise ValidationError("节点未关联到场景，无法创建默认接口")

    scene = node.sceneId
    default_subnet_name = f"{scene.sceneName} (Default)"

    with transaction.atomic():
        # 尝试获取或创建默认子网
        default_subnet, created = Subnet.objects.get_or_create(
            sceneId=scene,
            subnetName=default_subnet_name,
            defaults={
                'subnetIp': "192.168.1.0",
                'subnetMask': "255.255.255.0"
            }
        )

        # 锁定子网记录确保原子操作
        locked_subnet = Subnet.objects.select_for_update().get(pk=default_subnet.pk)

        # 获取已分配的IP地址
        allocated_ips = set(
            Interface.objects.filter(subnet=locked_subnet)
            .exclude(interfaceIp__isnull=True)
            .values_list('interfaceIp', flat=True)
        )

        # 创建网络对象
        try:
            network = ipaddress.IPv4Network(f"{locked_subnet.subnetIp}/{locked_subnet.subnetMask}", strict=False)
        except ValueError as e:
            raise ValidationError(f"无效的子网参数: {str(e)}")

        # 查找最小可用IP
        for ip in network.hosts():
            ip_str = str(ip)
            if ip_str not in allocated_ips:
                ip_address = ip_str
                break
        else:
            raise ValidationError(f"子网 {locked_subnet.subnetIp}/{locked_subnet.subnetMask} 中没有可用IP地址")

        # 创建接口对象
        interface = Interface.objects.create(
            node=node,
            interfaceIp=ip_address,
            interfaceIndex=0,
            subnetMask=locked_subnet.subnetMask,
            is_default=True,
            is_allocated=False,
            subnet=locked_subnet,
            interfaceType = "sub"
        )

    return interface
@csrf_exempt
@require_http_methods(["POST"])
def add_node_list(request):
    try:
        # 明确解码并验证 JSON 格式
        try:
            body_unicode = request.body.decode('utf-8')  # 避免乱码问题
            data = json.loads(body_unicode)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            return JsonResponse({'status': 'error', 'message': f'无效的JSON格式: {str(e)}'}, status=400)

        required_fields = ['nodeName', 'nodeType']
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            return JsonResponse({
                'status': 'error',
                'message': f'缺少必填字段: {", ".join(missing_fields)}'
            }, status=400)

        scene_id = data.get('sceneId')
        scene = None
        if scene_id:
            try:
                scene = Scene.objects.get(id=scene_id)
            except Scene.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': f'场景ID {scene_id} 不存在'
                }, status=404)

        with transaction.atomic():
            node = Node(
                sceneId=scene,
                nodeName=data['nodeName'],
                nodeImage=data.get('nodeImage'),
                nodeType=data['nodeType'],
                details=data.get('details')
            )

            if node.nodeType == 'satellite':
                required_fields = ['eccentricity', 'argPerigee', 'inclination',
                                   'meanAnomaly', 'meanMotion', 'raan', 'startTime']
                for field in required_fields:
                    if field not in data:
                        raise ValidationError(f'缺少卫星节点必填字段: {field}')
                    setattr(node, field, data[field])

            elif node.nodeType == 'normalNode':
                required_fields = ['lon', 'lat', 'alt', 'startTime']
                for field in required_fields:
                    if field not in data:
                        raise ValidationError(f'缺少普通节点必填字段: {field}')
                    setattr(node, field, data[field])

                via_points = data.get('viaPoints')
                if via_points:
                    if not isinstance(via_points, list):
                        raise ValidationError('viaPoints必须是列表')
                    for point in via_points:
                        if not isinstance(point, dict):
                            raise ValidationError('每个viaPoint必须是字典')
                        if not all(k in point for k in ['lon', 'lat', 'alt', 'time']):
                            raise ValidationError('每个viaPoint必须包含 lon、lat、alt 和 time')
                node.viaPoints = via_points
            else:
                raise ValidationError('无效的节点类型')

            node.full_clean()
            node.save()

            if scene_id:
                try:
                    create_default_interface(node)
                except Exception as e:
                    raise ValidationError(f'创建默认接口失败: {str(e)}')

        return JsonResponse({'status': 'success'})

    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'服务器错误: {str(e)}'}, status=500)


@require_http_methods(["GET"])
@csrf_exempt
def get_node_list(request):
    try:
        # 获取查询参数
        scene_id = request.GET.get('sceneId', '')
        node_type = request.GET.get('nodeType', '')
        node_name = request.GET.get('nodeName', '')
        page_size = int(request.GET.get('size', 10))
        page_number = int(request.GET.get('page', 1))

        # 构建查询条件
        query = Q()
        if scene_id:
            query &= Q(sceneId__id=scene_id)
        if node_type:
            query &= Q(nodeType=node_type)
        if node_name:
            query &= Q(nodeName__icontains=node_name)

        # 获取查询结果并分页
        nodes = Node.objects.filter(query).order_by('nodeName')
        paginator = Paginator(nodes, page_size)
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            return JsonResponse({'status': 'error', 'message': '页码必须是整数'}, status=400)
        except EmptyPage:
            return JsonResponse({'status': 'error', 'message': '页码超出范围'}, status=400)

        # 准备返回数据结构
        node_list = []
        for node in page_obj:
            interfaces = node.interfaces.all().order_by('interfaceIndex')

            # 保持原始 details 中每个接口的 JSON 字符串，不进行解析或修复
            details_list = []
            for interface in interfaces:
                try:
                    # 确保是 JSON 对象，转成带反斜杠的字符串
                    detail_obj = interface.detail
                    if isinstance(detail_obj, str):
                        # 如果已经是字符串，先转成 dict
                        detail_obj = json.loads(detail_obj)
                    json_str = json.dumps(detail_obj)  # 会自动加 \ 转义
                    details_list.append(json_str)
                except Exception as e:
                    logger.warning(f"接口 {interface.id} 的 detail 转换失败: {e}")
                    details_list.append("{}")  # 保底返回空 JSON

            node_data = {
                'sceneId': node.sceneId.id if node.sceneId else None,
                'id': node.id,
                'nodeName': node.nodeName,
                'nodeType': node.nodeType,
                'nodeImage': node.nodeImage,
                'lon': node.lon,
                'lat': node.lat,
                'alt': node.alt,
                'eccentricity': node.eccentricity,
                'argPerigee': node.argPerigee,
                'inclination': node.inclination,
                'meanAnomaly': node.meanAnomaly,
                'meanMotion': node.meanMotion,
                'raan': node.raan,
                'startTime': node.startTime.isoformat() if node.startTime else None,
                'viaPoints': node.viaPoints if node.viaPoints else [],
                'details': details_list  # ⬅️ 接口 detail 的 JSON 字符串数组
            }
            node_list.append(node_data)

        # 统计节点类型数量
        node_types = ['satellite', 'normalNode']
        node_count = {node_type: 0 for node_type in node_types}
        for node in nodes:
            if node.nodeType in node_count:
                node_count[node.nodeType] += 1

        # 返回结果
        return JsonResponse({
            'nodeList': node_list,
            'nodeCount': node_count,
            'page': page_obj.number,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'totalPages': paginator.num_pages,
            'total_count': paginator.count
        }, json_dumps_params={'ensure_ascii': False})

    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'Invalid page or size'}, status=400)
    except Exception as e:
        import traceback
        logger.error(f"Error in get_node_list: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["PUT"])
def edit_node_list(request, node_id):
    try:
        node = Node.objects.get(id=node_id)
    except Node.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Node not found'}, status=404)

    try:
        data = json.loads(request.body)

        # 更新通用字段
        node.nodeName = data.get('nodeName', node.nodeName)
        node.nodeImage = data.get('nodeImage', node.nodeImage)
        node.nodeType = data.get('nodeType', node.nodeType)

        # 验证场景是否存在（如果提供了 sceneId）
        scene_id = data.get('sceneId')
        if scene_id is not None:  # 允许 sceneId 为空字符串或显式设置为 None 的情况
            try:
                scene = Scene.objects.get(id=scene_id)
                node.sceneId = scene
            except Scene.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Scene not found'}, status=404)

        # 根据节点类型处理特定字段
        if node.nodeType == 'satellite':
            # 使用 get 方法获取字段，未提供则保留原值
            node.eccentricity = data.get('eccentricity', node.eccentricity)
            node.argPerigee = data.get('argPerigee', node.argPerigee)
            node.inclination = data.get('inclination', node.inclination)
            node.meanAnomaly = data.get('meanAnomaly', node.meanAnomaly)
            node.meanMotion = data.get('meanMotion', node.meanMotion)
            node.raan = data.get('raan', node.raan)
            node.startTime = data.get('startTime', node.startTime)

        elif node.nodeType == 'normalNode':
            node.lon = data.get('lon', node.lon)
            node.lat = data.get('lat', node.lat)
            node.alt = data.get('alt', node.alt)
            node.startTime = data.get('startTime', node.startTime)

            # 处理 viaPoints
            if 'viaPoints' in data:
                via_points = data['viaPoints']
                try:
                    if not isinstance(via_points, list):
                        return JsonResponse({'status': 'error', 'message': 'viaPoints must be a JSON list of points'},
                                            status=400)
                    for point in via_points:
                        if not isinstance(point, dict) or \
                                not all(key in point for key in ['lon', 'lat', 'alt', 'time']):
                            return JsonResponse({'status': 'error',
                                                 'message': 'Each viaPoint must contain \'lon\', \'lat\', \'alt\', and \'time\''},
                                                status=400)
                    node.viaPoints = via_points
                except (TypeError, ValueError):
                    return JsonResponse({'status': 'error', 'message': 'viaPoints must be valid JSON'}, status=400)
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid node type'}, status=400)

        # 处理 details 字段,#还没有处理接口ip。
        if 'details' in data:
            details = data['details']
            interfaces = list(node.interfaces.all().order_by('interfaceIndex'))

            if not isinstance(details, list):
                return JsonResponse({'status': 'error', 'message': 'details must be a list'}, status=400)

            if len(details) != len(interfaces):
                return JsonResponse({
                    'status': 'error',
                    'message': f'Details count ({len(details)}) does not match interface count ({len(interfaces)})'
                }, status=400)

            # 更新每个接口的 detail 字段
            for i, interface in enumerate(interfaces):
                try:
                    json.loads(details[i])  # 检查是否为合法 JSON 字符串
                except json.JSONDecodeError:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Invalid JSON at details index {i}'
                    }, status=400)

                interface.detail = details[i]
                interface.save(update_fields=['detail'])
        node.save()
        return JsonResponse({'status': 'success'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_http_methods(["DELETE"])
@csrf_exempt
def delete_node_list(request, node_id):
    try:
        node = Node.objects.get(id=node_id)
        node.delete()
        return JsonResponse({'status': 'success'})
    except Node.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '节点不存在'}, status=404)


'''
业务表
add: 节点必须已经有。
'''
@api_view(['POST'])
@csrf_exempt
def add_configuration_list(request):
    serializer = ConfigurationSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@require_http_methods(["GET"])
def get_configuration_list(request):
    page_size = int(request.GET.get('size', 10))
    page_number = int(request.GET.get('page', 1))
    business_name = request.GET.get('businessName', '')
    source_node_name = request.GET.get('sourceNodeName', '')
    destination_node_name = request.GET.get('destinationNodeName', '')
    business_type = request.GET.get('businessType', '')

    # 构建查询条件
    query = Q()
    if business_name:
        query &= Q(businessName__icontains=business_name)
    if source_node_name:
        query &= Q(sourceNodeId__nodeName__icontains=source_node_name)
    if destination_node_name:
        query &= Q(destinationNodeId__nodeName__icontains=destination_node_name)
    if business_type:
        query &= Q(businessType__icontains=business_type)

    # 获取查询结果并分页
    configurations = Configuration.objects.filter(query).order_by('businessName')
    paginator = Paginator(configurations, page_size)
    page_obj = paginator.get_page(page_number)

    # 准备要返回的数据
    configuration_list = [{
        'sceneId': config.sceneId.id,
        'id': config.id,
        'businessName': config.businessName,
        'sourceNodeId': config.sourceNodeId.id,
        'sourceNodeName': config.sourceNodeId.nodeName,
        'destinationNodeId': config.destinationNodeId.id,
        'destinationNodeName': config.destinationNodeId.nodeName,
        'cbrStartTime': config.cbrStartTime,
        'cbrEndTime': config.cbrEndTime,
        'cbrSendInterval': config.cbrSendInterval,
        'cbrPacketSize': config.cbrPacketSize,
        'ftpStartTime': config.ftpStartTime,
        'ftpPacketCount': config.ftpPacketCount,
        'businessType': config.businessType
    } for config in page_obj]

    return JsonResponse({
        'configurationList': configuration_list,
        'page': page_obj.number,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'totalPages': page_obj.paginator.num_pages,
        'total_count': paginator.count,  # 当前查询结果的总记录数
    })

@require_http_methods(["PUT", "PATCH"])
@csrf_exempt
def edit_configuration_list(request, configuration_id):
    try:
        config = Configuration.objects.get(id=configuration_id)
    except Configuration.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '业务不存在'}, status=404)

    # 从请求中获取数据
    data = json.loads(request.body)
    businessName = data.get('businessName', config.businessName)
    sourceNodeId = data.get('sourceNodeId', config.sourceNodeId_id)  # 注意这里是 sourceNodeId_id
    destinationNodeId = data.get('destinationNodeId', config.destinationNodeId_id)  # 注意这里是 destinationNodeId_id

    # 更新业务名称
    config.businessName = businessName

    # 更新节点 ID
    if sourceNodeId:
        config.sourceNodeId = Node.objects.get(id=sourceNodeId)
    if destinationNodeId:
        config.destinationNodeId = Node.objects.get(id=destinationNodeId)
    # 更新业务类型特定的字段
    business_type = data.get('businessType', config.businessType)
    config.businessType = business_type

    if business_type == 'cbr':
        config.cbrStartTime = data.get('cbrStartTime', config.cbrStartTime)
        config.cbrEndTime = data.get('cbrEndTime', config.cbrEndTime)
        config.cbrSendInterval = data.get('cbrSendInterval', config.cbrSendInterval)
        config.cbrPacketSize = data.get('cbrPacketSize', config.cbrPacketSize)
    elif business_type == 'ftp':
        config.ftpStartTime = data.get('ftpStartTime', config.ftpStartTime)
        config.ftpPacketCount = data.get('ftpPacketCount', config.ftpPacketCount)
    # 保存更新的配置
    config.save()

    return JsonResponse({'status': 'success'})

@require_http_methods(["DELETE"])
@csrf_exempt
def delete_configuration_list(request, configuration_id):
    try:
        # 尝试获取业务实例
        config = Configuration.objects.get(id=configuration_id)
        # 删除业务实例
        config.delete()
        return JsonResponse({'status': 'success'})
    except Configuration.DoesNotExist:
        # 如果业务不存在，返回404错误
        return JsonResponse({'status': 'error', 'message': '业务不存在'}, status=404)
    except Exception as e:
        # 其他错误，返回500错误
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



# subnet_manager = SubnetManager()
def allocate_link_ips(scene_id, subnet_ip, subnetMask, source_node, dest_node):
    """为链路两端分配唯一的IP地址"""
    # 获取子网对象
    subnet = IPv4Network(f"{subnet_ip}/{subnetMask}")

    # 查询当前子网所有已用IP（包含事务中未提交的数据）
    all_interfaces = Interface.objects.filter(
        subnetMask=subnetMask,
        node__sceneId=scene_id
    ).select_related('node')

    # 构建已用IP集合（包含同事务内已分配的IP）
    used_ips = set()
    for interface in all_interfaces:
        try:
            ip = ipaddress.IPv4Address(interface.interfaceIp)
            if ip in subnet:
                used_ips.add(str(ip))
        except AddressValueError:
            continue

    # 寻找两个可用IP
    available_ips = []
    for host in subnet.hosts():
        ip_str = str(host)
        if ip_str in {str(subnet.network_address), str(subnet.broadcast_address)}:
            continue
        if ip_str not in used_ips:
            available_ips.append(ip_str)
            if len(available_ips) >= 2:
                break

    if len(available_ips) < 2:
        raise ValueError(f"子网 {subnet} 可用IP不足，需要2个，当前找到{len(available_ips)}个")

    return available_ips[0], available_ips[1]

def get_or_create_interface(node, ip, mask, subnet):
    # 优先尝试复用默认接口
    interface = Interface.objects.filter(
        node=node,
        is_default=True,
        interfaceType=Interface.InterfaceTypeChoices.SUB  # 只复用“普通子网”接口
    ).first()

    if interface:
        # 修改已有默认接口的属性为链路接口
        interface.interfaceIp = ip
        interface.subnetMask = mask
        interface.is_allocated = True
        interface.is_default = False  # 不再默认
        interface.interfaceType = Interface.InterfaceTypeChoices.LINK
        interface.subnet = subnet
        interface.save()
    else:
        # 新建接口
        interface = Interface.objects.create(
            node=node,
            interfaceIp=ip,
            subnetMask=mask,
            interfaceIndex=Interface.objects.filter(node=node).count(),
            is_allocated=True,
            is_default=False,
            interfaceType=Interface.InterfaceTypeChoices.LINK,
            subnet=subnet
        )

    return interface

@csrf_exempt
@require_http_methods(["POST"])
def add_link_list(request):
    try:
        data = json.loads(request.body)
        scene_id = data.get('sceneId')
        source_node_name = data.get('sourceNodeName')
        dest_node_name = data.get('destinationNodeName')
        link_type = data.get('linkType')
        bandwidth = data.get('bandwidth')
        packet_header_size = data.get('packetHeaderSize')
        link_name = data.get('linkName') or f"{source_node_name}到{dest_node_name}({link_type})"
        subnet_ip = data.get('subnetIp')
        subnet_mask = data.get('subnetMask')

        # 新增：根据链路类型获取特有属性
        transmission_delay = None
        packet_loss_rate = None
        transmission_speed = None

        if link_type == '有线':
            transmission_delay = data.get('transmissionDelay')
            packet_loss_rate = data.get('packetLossRate')
        elif link_type == '无线':
            transmission_speed = data.get('transmissionSpeed')

        if not all([scene_id, source_node_name, dest_node_name, link_type]):
            return JsonResponse({'status': 'error', 'message': '缺少必要参数'}, status=400)

        if link_type not in ['有线', '无线']:
            return JsonResponse({'status': 'error', 'message': '无效的链路类型'}, status=400)

        scene = Scene.objects.get(id=scene_id)
        source_node = Node.objects.get(sceneId=scene, nodeName=source_node_name)
        dest_node = Node.objects.get(sceneId=scene, nodeName=dest_node_name)

        with transaction.atomic():
            # ---------- 1. 获取或创建子网 ----------
            if subnet_ip and subnet_mask:
                subnet, created = Subnet.objects.get_or_create(
                    sceneId=scene,
                    subnetIp=subnet_ip,
                    subnetMask=subnet_mask,
                    defaults={
                        'subnetName': f"{link_name}子网",
                        'subnetType': Subnet.SubnetTypeChoices.LINK
                    }
                )
            else:
                # ---------- 2. 自动分配未使用的子网 ----------
                candidate_ips = [f"190.0.{i}.0" for i in range(1, 100)]
                subnet_mask = "255.255.255.0"  # 固定掩码
                used_ips = set(scene.subnets.values_list("subnetIp", flat=True))
                subnet_ip = next((ip for ip in candidate_ips if ip not in used_ips), None)

                if not subnet_ip:
                    raise ValidationError("已无可用的默认子网IP")

                subnet = Subnet.objects.create(
                    sceneId=scene,
                    subnetName=f"{link_name}子网",
                    subnetIp=subnet_ip,
                    subnetMask=subnet_mask,
                    subnetType=Subnet.SubnetTypeChoices.LINK
                )

            # ---------- 3. 锁定子网，分配 IP ----------
            subnet = Subnet.objects.select_for_update().get(pk=subnet.pk)

            allocated_ips = set(
                Interface.objects.filter(subnet=subnet)
                .exclude(interfaceIp__isnull=True)
                .values_list('interfaceIp', flat=True)
            )

            try:
                network = ipaddress.IPv4Network(f"{subnet.subnetIp}/{subnet.subnetMask}", strict=False)
            except ValueError as e:
                raise ValidationError(f"无效的子网参数: {str(e)}")

            available_ips = []
            for ip in network.hosts():
                ip_str = str(ip)
                if ip_str not in allocated_ips:
                    available_ips.append(ip_str)
                    if len(available_ips) == 2:
                        break

            if len(available_ips) < 2:
                raise ValidationError(f"子网 {subnet.subnetIp}/{subnet.subnetMask} 中没有足够的可用IP地址")

            source_ip = available_ips[0]
            dest_ip = available_ips[1]

            # ---------- 4. 创建或复用源节点接口 ----------
            source_interface = get_or_create_interface(source_node, source_ip, subnet.subnetMask, subnet)

            # ---------- 5. 创建或复用目标节点接口 ----------
            dest_interface = get_or_create_interface(dest_node, dest_ip, subnet.subnetMask, subnet)

            # ---------- 6. 创建链路 ----------
            link = Link.objects.create(
                sceneId=scene,
                linkName=link_name,
                linkType=link_type,
                bandwidth=bandwidth,
                packetHeaderSize=packet_header_size,
                sourceNodeId=source_node,
                destinationNodeId=dest_node,
                subnetIp=subnet.subnetIp,
                subnetMask=subnet.subnetMask,
                sourceInterface=source_interface,
                destinationInterface=dest_interface,
                subnet=subnet,
                transmissionDelay=transmission_delay if link_type == '有线' else None,
                packetLossRate=packet_loss_rate if link_type == '有线' else None,
                transmissionSpeed=transmission_speed if link_type == '无线' else None
            )

        return JsonResponse({'status': 'success'})

    except (Scene.DoesNotExist, Node.DoesNotExist) as e:
        return JsonResponse({'status': 'error', 'message': '场景或节点不存在'}, status=404)
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'服务器错误: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_link_list(request):
    try:
        # 获取查询参数
        link_name = request.GET.get('linkName', '')
        source_node_name = request.GET.get('sourceNodeName', '')
        destination_node_name = request.GET.get('destinationNodeName', '')
        link_type = request.GET.get('linkType', '')
        scene_id = request.GET.get('sceneId', '')
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('pageSize', 10))

        # 构建查询条件
        query = Q()
        if link_name:
            query &= Q(linkName__icontains=link_name)
        if link_type:
            query &= Q(linkType__icontains=link_type)
        if source_node_name:
            query &= Q(sourceNodeId__nodeName__icontains=source_node_name)
        if destination_node_name:
            query &= Q(destinationNodeId__nodeName__icontains=destination_node_name)
        if scene_id:
            query &= Q(sceneId=scene_id)

        # 查询链路信息并选择相关对象
        links = Link.objects.filter(query).select_related(
            'sourceNodeId',
            'destinationNodeId',
            'sceneId',
            'sourceInterface',
            'destinationInterface',
            'subnet'
        )

        # 分页
        paginator = Paginator(links, page_size)
        try:
            page_obj = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)

        # 准备返回的数据 - 包含所有属性
        link_list = []
        for link in page_obj:
            link_data = {
                'id': link.id,
                'linkName': link.linkName,
                'linkType': link.linkType,
                'sourceNodeId': link.sourceNodeId.id,
                'sourceNodeName': link.sourceNodeId.nodeName,
                'destinationNodeId': link.destinationNodeId.id,
                'destinationNodeName': link.destinationNodeId.nodeName,
                'sceneId': link.sceneId.id,
                'sceneName': link.sceneId.sceneName,
                'subnetIp': link.subnetIp,
                'subnetMask': link.subnetMask,
                'bandwidth': link.bandwidth,
                'packetHeaderSize': link.packetHeaderSize,
                'transmissionDelay': link.transmissionDelay,
                'packetLossRate': link.packetLossRate,
                'transmissionSpeed': link.transmissionSpeed,

                # 新增接口信息
                'sourceInterfaceIp': link.sourceInterface.interfaceIp if link.sourceInterface else None,
                'sourceInterfaceIndex': link.sourceInterface.interfaceIndex if link.sourceInterface else None,
                'destinationInterfaceIp': link.destinationInterface.interfaceIp if link.destinationInterface else None,
                'destinationInterfaceIndex': link.destinationInterface.interfaceIndex if link.destinationInterface else None,
            }
            link_list.append(link_data)

        return JsonResponse({
            'status': 'success',
            'linkList': link_list,
            'pagination': {
                'currentPage': page_obj.number,
                'hasNextPage': page_obj.has_next(),
                'hasPreviousPage': page_obj.has_previous(),
                'totalPages': paginator.num_pages,
                'totalLinks': paginator.count
            }
        })

    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': f'参数错误: {str(e)}'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'服务器错误: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["PUT"])
def edit_link_list(request, link_id):
    try:
        with transaction.atomic():
            # 获取链路及关联对象（预加载相关数据）
            link = Link.objects.select_related(
                'sceneId',
                'sourceNodeId',
                'destinationNodeId',
                'sourceInterface',
                'destinationInterface',
                'subnet'  # 预加载子网对象
            ).get(id=link_id)

            # 解析请求数据
            data = json.loads(request.body)
            scene_id = data.get('sceneId', link.sceneId.id)
            subnet_ip = data.get('subnetIp', link.subnetIp)
            subnet_mask = data.get('subnetMask', link.subnetMask)
            source_interface_ip = data.get('sourceInterfaceIp')
            dest_interface_ip = data.get('destinationInterfaceIp')
            source_node_name = data.get('sourceNodeName', link.sourceNodeId.nodeName)
            dest_node_name = data.get('destinationNodeName', link.destinationNodeId.nodeName)
            link_type = data.get('linkType', link.linkType)
            link_name = data.get('linkName', f"{source_node_name}到{dest_node_name}({link_type})")

            # 新增：根据链路类型获取特有属性
            bandwidth = data.get('bandwidth', link.bandwidth)
            packet_header_size = data.get('packetHeaderSize', link.packetHeaderSize)

            # 处理有线特有属性
            transmission_delay = data.get('transmissionDelay', link.transmissionDelay)
            packet_loss_rate = data.get('packetLossRate', link.packetLossRate)

            # 处理无线特有属性
            transmission_speed = data.get('transmissionSpeed', link.transmissionSpeed)

            # 验证基础参数
            if link_type not in ['有线', '无线']:
                return JsonResponse({'status': 'error', 'message': '无效的链路类型'}, status=400)

            # 公共参数检查
            if None in [bandwidth, packet_header_size]:
                return JsonResponse({'status': 'error', 'message': '缺少带宽或包头大小参数'}, status=400)

            # 类型特定参数检查
            if link_type == '有线':
                # 清空无线参数
                transmission_speed = None

                # 检查有线特有参数
                if transmission_delay is None:
                    return JsonResponse({'status': 'error', 'message': '缺少传输延迟参数'}, status=400)
                if packet_loss_rate is None:
                    return JsonResponse({'status': 'error', 'message': '缺少丢包率参数'}, status=400)
                if packet_loss_rate < 0 or packet_loss_rate > 100:
                    return JsonResponse({'status': 'error', 'message': '丢包率应在0-100之间'}, status=400)

            elif link_type == '无线':
                # 清空有线参数
                transmission_delay = None
                packet_loss_rate = None

                # 检查无线特有参数
                if transmission_speed is None:
                    return JsonResponse({'status': 'error', 'message': '缺少传输速度参数'}, status=400)
                if transmission_speed <= 0:
                    return JsonResponse({'status': 'error', 'message': '传输速度必须大于0'}, status=400)

            # 获取关联对象
            scene = Scene.objects.get(id=scene_id)
            source_node = Node.objects.get(sceneId=scene, nodeName=source_node_name)
            dest_node = Node.objects.get(sceneId=scene, nodeName=dest_node_name)

            # 业务验证逻辑
            def check_link_conflict():
                """检查链路名称和节点对冲突"""
                # 名称冲突检查（排除自身）
                if Link.objects.filter(
                        sceneId=scene,
                        linkName=link_name
                ).exclude(id=link.id).exists():
                    return JsonResponse(
                        {'status': 'error', 'message': '链路名称已存在'},
                        status=400
                    )

                # 节点对类型冲突检查
                existing = Link.objects.filter(
                    Q(sourceNodeId=source_node, destinationNodeId=dest_node) |
                    Q(sourceNodeId=dest_node, destinationNodeId=source_node),
                    linkType=link_type
                ).exclude(id=link.id).first()
                if existing:
                    return JsonResponse(
                        {'status': 'error', 'message': f'已存在相同类型的链路：{existing.linkName}'},
                        status=400
                    )
                return None

            if conflict_response := check_link_conflict():
                return conflict_response

            # 处理子网变更
            subnet = link.subnet
            subnet_changed = False

            # 如果前端传了子网信息
            if subnet_ip and subnet_mask:
                # 检查子网是否已存在
                subnet, created = Subnet.objects.get_or_create(
                    sceneId=scene,
                    subnetIp=subnet_ip,
                    subnetMask=subnet_mask,
                    defaults={'subnetName': f"子网 {subnet_ip}/{subnet_mask}"},
                    subnetType = "link"
                )

                # 如果子网是新创建的或不同于原来的子网
                if created or subnet != link.subnet:
                    subnet_changed = True
            else:
                # 如果没有传递子网信息，使用原来的子网
                subnet = link.subnet
                subnet_ip = subnet.subnetIp
                subnet_mask = subnet.subnetMask

            # 记录节点是否变更
            nodes_changed = link.sourceNodeId != source_node or link.destinationNodeId != dest_node

            # 更新核心字段
            link.sceneId = scene
            link.linkName = link_name
            link.linkType = link_type
            link.bandwidth = bandwidth
            link.packetHeaderSize = packet_header_size
            link.transmissionDelay = transmission_delay
            link.packetLossRate = packet_loss_rate
            link.transmissionSpeed = transmission_speed
            link.subnetIp = subnet_ip
            link.subnetMask = subnet_mask
            link.sourceNodeId = source_node
            link.destinationNodeId = dest_node
            link.subnet = subnet

            # 处理接口变更
            interface_update_needed = subnet_changed or nodes_changed

            # 如果前端传了接口IP
            if source_interface_ip or dest_interface_ip:
                # 验证源接口IP
                if source_interface_ip:
                    # 检查IP是否已被占用（排除当前接口）
                    if Interface.objects.filter(
                            interfaceIp=source_interface_ip,
                            subnetMask=subnet_mask
                    ).exclude(id=link.sourceInterface.id).exists():
                        return JsonResponse(
                            {'status': 'error', 'message': f'源IP地址 {source_interface_ip} 已被占用'},
                            status=400
                        )

                    # 验证IP是否在子网内
                    try:
                        network = ipaddress.IPv4Network(f"{subnet_ip}/{subnet_mask}", strict=False)
                        ip_address = ipaddress.IPv4Address(source_interface_ip)
                        if ip_address not in network:
                            return JsonResponse(
                                {'status': 'error',
                                 'message': f'源IP地址 {source_interface_ip} 不在子网 {subnet_ip}/{subnet_mask} 内'},
                                status=400
                            )
                    except ValueError:
                        return JsonResponse(
                            {'status': 'error', 'message': '无效的子网配置'},
                            status=400
                        )

                    link.sourceInterface.interfaceIp = source_interface_ip
                    interface_update_needed = True

                # 验证目的接口IP
                if dest_interface_ip:
                    # 检查IP是否已被占用（排除当前接口）
                    if Interface.objects.filter(
                            interfaceIp=dest_interface_ip,
                            subnetMask=subnet_mask
                    ).exclude(id=link.destinationInterface.id).exists():
                        return JsonResponse(
                            {'status': 'error', 'message': f'目的IP地址 {dest_interface_ip} 已被占用'},
                            status=400
                        )

                    # 验证IP是否在子网内
                    try:
                        network = ipaddress.IPv4Network(f"{subnet_ip}/{subnet_mask}", strict=False)
                        ip_address = ipaddress.IPv4Address(dest_interface_ip)
                        if ip_address not in network:
                            return JsonResponse(
                                {'status': 'error',
                                 'message': f'目的IP地址 {dest_interface_ip} 不在子网 {subnet_ip}/{subnet_mask} 内'},
                                status=400
                            )
                    except ValueError:
                        return JsonResponse(
                            {'status': 'error', 'message': '无效的子网配置'},
                            status=400
                        )

                    link.destinationInterface.interfaceIp = dest_interface_ip
                    interface_update_needed = True

            # 如果没有传接口IP且需要更新接口
            elif interface_update_needed:
                # 获取子网中已分配的IP地址
                allocated_ips = set(
                    Interface.objects.filter(subnet=subnet)
                    .exclude(interfaceIp__isnull=True)
                    .values_list('interfaceIp', flat=True)
                )

                # 排除当前链路的接口IP
                if link.sourceInterface.interfaceIp:
                    allocated_ips.discard(link.sourceInterface.interfaceIp)
                if link.destinationInterface.interfaceIp:
                    allocated_ips.discard(link.destinationInterface.interfaceIp)

                # 创建网络对象
                try:
                    network = ipaddress.IPv4Network(f"{subnet_ip}/{subnet_mask}", strict=False)
                except ValueError as e:
                    return JsonResponse(
                        {'status': 'error', 'message': f'无效的子网参数: {str(e)}'},
                        status=400
                    )

                # 找出两个可用的最小IP
                available_ips = []
                for ip in network.hosts():
                    ip_str = str(ip)
                    if ip_str not in allocated_ips:
                        available_ips.append(ip_str)
                        if len(available_ips) == 2:
                            break

                if len(available_ips) < 2:
                    return JsonResponse(
                        {'status': 'error', 'message': f'子网 {subnet_ip}/{subnet_mask} 中没有足够的可用IP地址'},
                        status=400
                    )

                source_ip = available_ips[0]
                dest_ip = available_ips[1]

                link.sourceInterface.interfaceIp = source_ip
                link.destinationInterface.interfaceIp = dest_ip

            # 更新接口的其他属性
            if interface_update_needed:
                link.sourceInterface.node = source_node
                link.sourceInterface.subnet = subnet
                link.sourceInterface.subnetMask = subnet_mask
                link.sourceInterface.interfaceType = "link"
                link.sourceInterface.save()

                link.destinationInterface.node = dest_node
                link.destinationInterface.subnet = subnet
                link.destinationInterface.subnetMask = subnet_mask
                link.destinationInterface.interfaceType = "link"
                link.destinationInterface.save()

            # 保存最终修改
            link.save()

            return JsonResponse({'status': 'success'})

    except Link.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '链路不存在'}, status=404)
    except (Scene.DoesNotExist, Node.DoesNotExist):
        return JsonResponse({'status': 'error', 'message': '场景或节点不存在'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': '无效的JSON格式'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse(
            {'status': 'error', 'message': f'服务器错误: {str(e)}'},
            status=500
        )


def rearrange_interfaceIndexes(node):
    interfaces = Interface.objects.filter(node=node).order_by('interfaceIndex')
    for index, interface in enumerate(interfaces):
        if interface.interfaceIndex != index:
            interface.interfaceIndex = index
            interface.save()

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_link_list(request, link_id):
    try:
        with transaction.atomic():  # 事务包装整个操作
            # 1. 获取链路及关联对象（使用select_related优化查询）
            link = Link.objects.get(id=link_id)
            # 删除链路
            link.delete()

            # 4. 维护节点接口状态
            def maintain_node(node):
                """维护节点接口状态"""
                # 重新排列接口索引（批量更新优化）
                interfaces = list(node.interfaces.order_by('id'))
                Interface.objects.bulk_update(
                    [Interface(id=i.id, interfaceIndex=idx) for idx, i in enumerate(interfaces)],
                    ['interfaceIndex']
                )

                # 检查并创建默认接口
                if not node.interfaces.exists():
                    create_default_interface(node)

            # 维护源节点
            maintain_node(link.sourceNodeId)
            # 维护目标节点
            maintain_node(link.destinationNodeId)

            return JsonResponse({'status': 'success'})

    except Link.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '链路不存在'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'删除失败: {str(e)}'}, status=500)


# 优化后的索引重排函数
def rearrange_interfaceIndexes(node):
    """批量更新接口索引（性能优化版）"""
    interfaces = list(node.interfaces.order_by('id'))
    update_list = []

    for index, interface in enumerate(interfaces):
        if interface.interfaceIndex != index:
            interface.interfaceIndex = index
            update_list.append(interface)

    if update_list:
        Interface.objects.bulk_update(update_list, ['interfaceIndex'])


'''
节点故障表
'''

@require_http_methods(["POST"])
def add_node_error_list(request):
    # 解析 JSON 数据
    data = json.loads(request.body)

    # 获取表单字段
    scene_id = data.get('sceneId')
    node_id = data.get('nodeId')
    error_start_time = data.get('errorStartTime')
    error_end_time = data.get('errorEndTime')

    # 查询 Scene 实例
    try:
        scene = Scene.objects.get(id=scene_id)
    except Scene.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '场景不存在'}, status=404)

    # 查询 Node 实例
    try:
        node = Node.objects.get(id=node_id)
    except Node.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '节点不存在'}, status=404)

        # 将字符串转换为 datetime 对象
    if error_start_time:
        try:
            error_start_time = datetime.fromisoformat(error_start_time)
        except ValueError:
            return JsonResponse({'status': 'error', 'message': '无效的开始时间格式'}, status=400)
    if error_end_time:
        try:
            error_end_time = datetime.fromisoformat(error_end_time)
        except ValueError:
            return JsonResponse({'status': 'error', 'message': '无效的结束时间格式'}, status=400)
            # 验证开始时间是否早于结束时间
    if error_start_time and error_end_time and error_start_time >= error_end_time:
        return JsonResponse({'status': 'error', 'message': '开始时间必须早于结束时间'}, status=400)
    # 创建表单实例
    form = ErrorForm({
        'sceneId': scene_id,
        'nodeId': node_id,
        'errorStartTime': error_start_time,
        'errorEndTime': error_end_time,
    })

    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
#
@require_http_methods(["DELETE"])
def delete_node_error_list(request, node_error_id):
    try:
        # 尝试获取节点故障实例
        node_error = Error.objects.get(id=node_error_id)
        # 删除节点故障实例
        node_error.delete()
        return JsonResponse({'status': 'success'})
    except Error.DoesNotExist:
        # 如果节点故障不存在，返回404错误
        return JsonResponse({'status': 'error', 'message': '节点故障不存在'}, status=404)
    except Exception as e:
        # 其他错误，返回500错误
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
#
@require_http_methods(["GET"])
def get_node_error_list(request):
    # 获取查询参数
    scene_id = request.GET.get('sceneId', '')
    node_name = request.GET.get('nodeName', '')
    node_type = request.GET.get('nodeType', '')
    node_id = request.GET.get('nodeId', '')  # 新增节点ID查询参数
    page_size = int(request.GET.get('size', 10))
    page_number = int(request.GET.get('page', 1))

    # 构建查询条件
    query = Q()
    if scene_id:
        query &= Q(sceneId__id=scene_id)  # 根据场景 ID 过滤
    if node_name:
        query &= Q(nodeId__nodeName__icontains=node_name)
    if node_type:
        query &= Q(nodeId__nodeType__icontains=node_type)
    if node_id:  # 新增节点ID过滤条件
        query &= Q(nodeId__id=node_id)

    # 获取查询结果并分页
    node_errors = Error.objects.filter(query).order_by('nodeId__nodeName')
    paginator = Paginator(node_errors, page_size)
    page_obj = paginator.get_page(page_number)

    # 准备要返回的数据
    node_error_list = [{
        'sceneId': error.sceneId.id,
        'id': error.id,
        'nodeId': error.nodeId.id,
        'nodeName': error.nodeId.nodeName,
        'nodeType': error.nodeId.nodeType,
        'errorStartTime': error.errorStartTime,
        'errorEndTime': error.errorEndTime
    } for error in page_obj]

    return JsonResponse({
        'nodeErrorList': node_error_list,
        'page': page_obj.number,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'total_pages': page_obj.paginator.num_pages,
        'total_count': paginator.count,  # 当前查询结果的总记录数
    })

'''
链路故障表
'''


@require_http_methods(["POST"])
@csrf_exempt
def add_link_error_list(request):
    # 解析 JSON 数据
    data = json.loads(request.body)

    # 获取表单字段
    scene_id = data.get('sceneId')
    link_id = data.get('linkId')
    error_start_time = data.get('errorStartTime')
    error_end_time = data.get('errorEndTime')

    # 查询 Scene 实例
    try:
        scene = Scene.objects.get(id=scene_id)
    except Scene.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '场景不存在'}, status=404)

    # 查询 Link 实例
    try:
        link = Link.objects.get(id=link_id)
    except Link.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '链路不存在'}, status=404)

    # 将字符串转换为 datetime 对象
    if error_start_time:
        try:
            error_start_time = datetime.fromisoformat(error_start_time)
        except ValueError:
            return JsonResponse({'status': 'error', 'message': '无效的开始时间格式'}, status=400)
    if error_end_time:
        try:
            error_end_time = datetime.fromisoformat(error_end_time)
        except ValueError:
            return JsonResponse({'status': 'error', 'message': '无效的结束时间格式'}, status=400)

    # 创建表单实例
    form = LinkErrorForm({
        'sceneId': scene.id,
        'linkId': link.id,
        'errorStartTime': error_start_time,
        'errorEndTime': error_end_time,
    })

    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


@require_http_methods(["GET"])
def get_link_error_list(request):
    try:
        # 获取查询参数
        page_size = int(request.GET.get('size', 10))
        page_number = int(request.GET.get('page', 1))
        link_name = request.GET.get('linkName', '')
        source_node_name = request.GET.get('sourceNodeName', '')
        destination_node_name = request.GET.get('destinationNodeName', '')
        scene_id = request.GET.get('sceneId', '')  # 新增场景ID查询参数

        # 构建查询条件
        query = Q()

        # 1. 添加场景ID过滤
        if scene_id:
            try:
                # 验证场景ID是否存在
                scene = Scene.objects.get(id=scene_id)
                query &= Q(sceneId=scene)
            except Scene.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': f'场景ID {scene_id} 不存在'
                }, status=400)

        # 2. 添加链路名称过滤
        if link_name:
            query &= Q(linkId__linkName__icontains=link_name)

        # 3. 添加源节点名称过滤
        if source_node_name:
            query &= Q(linkId__sourceNodeId__nodeName__icontains=source_node_name)

        # 4. 添加目标节点名称过滤
        if destination_node_name:
            query &= Q(linkId__destinationNodeId__nodeName__icontains=destination_node_name)

        # 获取查询结果并分页
        link_errors = LinkError.objects.filter(query).select_related(
            'linkId__sourceNodeId',
            'linkId__destinationNodeId',
            'sceneId'  # 新增场景关联
        ).order_by('-errorStartTime')  # 按错误开始时间倒序排序

        paginator = Paginator(link_errors, page_size)
        page_obj = paginator.get_page(page_number)

        # 准备要返回的数据
        link_error_list = [
            {
                'id': error.id,
                'sceneId': error.sceneId.id,
                'sceneName': error.sceneId.sceneName,  # 新增场景名称
                'linkId': error.linkId.id,  # 新增链路ID
                'linkName': error.linkId.linkName,
                'sourceNodeId': error.linkId.sourceNodeId.id,  # 新增源节点ID
                'sourceNodeName': error.linkId.sourceNodeId.nodeName,
                'destinationNodeId': error.linkId.destinationNodeId.id,  # 新增目标节点ID
                'destinationNodeName': error.linkId.destinationNodeId.nodeName,
                'errorStartTime': error.errorStartTime.isoformat() if error.errorStartTime else None,
                'errorEndTime': error.errorEndTime.isoformat() if error.errorEndTime else None,
            }
            for error in page_obj
        ]

        return JsonResponse({
            'status': 'success',
            'linkErrorList': link_error_list,
            'pagination': {
                'current_page': page_obj.number,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
            }
        })

    except ValueError as e:
        return JsonResponse({
            'status': 'error',
            'message': f'参数错误: {str(e)}'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'服务器错误: {str(e)}'
        }, status=500)

@require_http_methods(["DELETE"])
def delete_link_error_list(request, link_error_id):
    try:
        # 尝试获取链路故障实例
        link_error = LinkError.objects.get(id=link_error_id)
        # 删除链路故障实例
        link_error.delete()
        return JsonResponse({'status': 'success'})
    except LinkError.DoesNotExist:
        # 如果链路故障不存在，返回404错误
        return JsonResponse({'status': 'error', 'message': '链路故障不存在'}, status=404)
    except Exception as e:
        # 其他错误，返回500错误
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["PUT"])
def edit_link_error_list(request,link_error_id):
    # 解析 JSON 数据
    data = json.loads(request.body)
    # 获取表单字段
    error_id = link_error_id
    link_id = data.get('linkId')
    error_start_time = data.get('errorStartTime')
    error_end_time = data.get('errorEndTime')

    # 查询 LinkError 实例
    try:
        link_error = LinkError.objects.get(id=error_id)
    except LinkError.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '故障记录不存在'}, status=404)

    # 更新字段
    if link_id:
        try:
            link = Link.objects.get(id=link_id)
            link_error.linkId = link
        except Link.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '链路不存在'}, status=404)

    if error_start_time:
        try:
            error_start_time = datetime.fromisoformat(error_start_time)
            link_error.errorStartTime = error_start_time
        except ValueError:
            return JsonResponse({'status': 'error', 'message': '无效的开始时间格式'}, status=400)

    if error_end_time:
        try:
            error_end_time = datetime.fromisoformat(error_end_time)
            link_error.errorEndTime = error_end_time
        except ValueError:
            return JsonResponse({'status': 'error', 'message': '无效的结束时间格式'}, status=400)

    # 保存更新
    link_error.save()

    return JsonResponse({'status': 'success'})


@csrf_exempt
@require_http_methods(["PUT"])
def edit_node_error_list(request, node_error_id):
    # 解析 JSON 数据
    data = json.loads(request.body)
    # 获取表单字段
    error_id = node_error_id
    node_id = data.get('nodeId')
    error_start_time = data.get('errorStartTime')
    error_end_time = data.get('errorEndTime')

    # 查询 NodeError 实例
    try:
        node_error = Error.objects.get(id=error_id)
    except Error.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '故障记录不存在'}, status=404)
    # 更新字段
    if node_id:
        try:
            node = Node.objects.get(id=node_id)
            node_error.nodeId = node
        except Node.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '节点不存在'}, status=404)

    if error_start_time:
        try:
            error_start_time = datetime.fromisoformat(error_start_time)
            node_error.errorStartTime = error_start_time
        except ValueError:
            return JsonResponse({'status': 'error', 'message': '无效的开始时间格式'}, status=400)

    if error_end_time:
        try:
            error_end_time = datetime.fromisoformat(error_end_time)
            node_error.errorEndTime = error_end_time
        except ValueError:
            return JsonResponse({'status': 'error', 'message': '无效的结束时间格式'}, status=400)

    # 保存更新
    node_error.save()

    return JsonResponse({'status': 'success'})

'''
节点模板表
'''


@require_http_methods(["POST"])
def add_node_template_list(request):
    try:
        data = json.loads(request.body)
        template_name = data.get("templateName")
        template_type = data.get("templateType")
        template_info = data.get("templateInfo")

        if not template_name or not template_type or not template_info:
            return JsonResponse({"status": "error", "message": "缺少必要字段"}, status=400)

        # 检查 templateName 是否已存在
        if NodeTemplate.objects.filter(templateName=template_name).exists():
            return JsonResponse({"status": "error", "message": "模板名称已存在"}, status=400)

        new_template = NodeTemplate(
            templateName=template_name,
            templateType=template_type,
            templateInfo=template_info
        )
        new_template.save()

        return JsonResponse({"status": "success", "message": "模板添加成功"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@require_http_methods(["GET"])
def get_node_template_list(request):
    template_type = request.GET.get('templateType', '')
    template_name = request.GET.get(' templateName', '')
    page_size = int(request.GET.get('size', 10))
    page_number = int(request.GET.get('page', 1))

    # 构建查询条件
    query = Q()
    if template_type:
        query &= Q(nodeType__icontains=template_type)
    if template_name:
        query &= Q(nodeName__icontains=template_name)

    # 获取查询结果并分页
    node_templates = NodeTemplate.objects.filter(query).order_by('templateName')
    paginator = Paginator(node_templates, page_size)
    page_obj = paginator.get_page(page_number)

    # 准备要返回的数据
    node_template_list = [{
        'id': template.id,
        'templateName': template.templateName,
        'templateType': template.templateType,
        # 其他字段...
    } for template in page_obj]

    return JsonResponse({
        'nodeTemplateList': node_template_list,
        'page': page_obj.number,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'total_pages': page_obj.paginator.num_pages,
        'total_count': paginator.count,  # 当前查询结果的总记录数
    })


@csrf_exempt  # 如果你不需要 CSRF 保护，可以添加这个装饰器
@require_http_methods(["PUT"])  # 确保视图只响应 PUT 请求
def edit_node_template_list(request, node_template_id):
    try:
        template = NodeTemplate.objects.get(id=node_template_id)
    except NodeTemplate.DoesNotExist:
        return JsonResponse({"status": "error", "message": "节点模板不存在"}, status=404)

    try:
        data = json.loads(request.body)
        new_template_name = data.get("templateName", template.templateName)
        new_template_type = data.get("templateType", template.templateType)
        new_template_info = data.get("templateInfo", template.templateInfo)

        # 检查 templateName 是否已存在（排除当前记录）
        if NodeTemplate.objects.filter(templateName=new_template_name).exclude(id=template.id).exists():
            return JsonResponse({"status": "error", "message": "模板名称已存在"}, status=400)

        # 更新字段
        template.templateName = new_template_name
        template.templateType = new_template_type
        template.templateInfo = new_template_info
        template.save()

        return JsonResponse({"status": "success", "message": "模板更新成功"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@require_http_methods(["DELETE"])
def delete_node_template_list(request, node_template_id):
    try:
        # 尝试获取节点模板实例
        node_template = NodeTemplate.objects.get(id=node_template_id)
        # 删除节点模板实例
        node_template.delete()
        return JsonResponse({'status': 'success'})
    except NodeTemplate.DoesNotExist:
        # 如果节点模板不存在，返回404错误
        return JsonResponse({'status': 'error', 'message': '节点模板不存在'}, status=404)
    except Exception as e:
        # 其他错误，返回500错误
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

'''
IP映射表
'''
@require_http_methods(["POST"])
def add_node_map_list(request):
    try:
        # 获取前端传值
        data = json.loads(request.body)
        scene_id = data.get('sceneId')
        interfaceIp = data.get('interfaceIp')
        mapping_ip = data.get('mappingIp')
        print(f"Received data: sceneId={scene_id}, interfaceIp={interfaceIp}, mappingIp={mapping_ip}")

        # 验证数据
        if not all([scene_id, interfaceIp, mapping_ip]):
            return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)

        # 查找对应的场景
        try:
            scene = Scene.objects.get(id=scene_id)
        except Scene.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Scene not found'}, status=404)

        # 查找对应的接口（结合场景ID进行查询）
        try:
            interface = Interface.objects.get(node__sceneId=scene, interfaceIp=interfaceIp)
        except Interface.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Interface not found'}, status=400)

        # 创建新的 NodeMapping 记录
        node_mapping = NodeMapping.objects.create(
            sceneId=scene,
            interface=interface,
            mappingIp=mapping_ip
        )

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def get_node_interfaces(request):
    try:
        # 获取查询参数
        scene_id = request.GET.get('sceneId')

        # 检查场景是否存在
        try:
            scene = Scene.objects.get(id=scene_id)
        except Scene.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '场景不存在'}, status=404)

        # 查询场景下的所有节点
        nodes = Node.objects.filter(sceneId=scene)

        # 准备返回的数据
        interface_list = []
        for node in nodes:
            # 查询节点的所有接口
            interfaces = Interface.objects.filter(node=node)
            for interface in interfaces:
                interface_list.append({
                    'nodeId': str(node.id),
                    'nodeName': node.nodeName,
                    'interfaceIndex': str(interface.interfaceIndex),
                    'nodeInterfaceIp': interface.interfaceIp,
                    'nodeInterfaceType': interface.interfaceType,
                    "is_default":interface.is_default
                })

        return JsonResponse(interface_list, safe=False)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_http_methods(["DELETE"])
def delete_node_map_list(request, mapping_id):
    try:
        # 获取指定的 NodeMapping 对象
        mapping = get_object_or_404(NodeMapping, id=mapping_id)

        # 删除对象
        mapping.delete()

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_http_methods(["PUT"])
def edit_node_map_list(request, mapping_id):
    try:
        # 获取映射结果对象
        mapping = get_object_or_404(NodeMapping, id=mapping_id)
        print(mapping_id)
        # 解析 JSON 请求体
        data = json.loads(request.body)

        # 获取前端传值
        interface_ip = data.get('interfaceIp')
        mapping_ip = data.get('mappingIp')

        # 验证数据
        if not all([interface_ip, mapping_ip]):
            return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)

        # 查找对应的接口 - 使用 filter() 替代 get() 处理多个结果的情况
        interfaces = Interface.objects.filter(
            interfaceIp=interface_ip,
            node__sceneId=mapping.sceneId.id
        )
        print('interface_ip:{}',interface_ip,mapping.sceneId.id)
        # 检查是否找到接口
        if not interfaces.exists():
            return JsonResponse({'status': 'error', 'message': 'Interface not found'}, status=400)

        # 如果有多个接口，选择第一个（或根据业务逻辑处理）
        if interfaces.count() > 1:
            # 这里可以根据业务需求添加更复杂的处理逻辑
            # 例如：选择与当前映射相关的接口，或者返回错误要求指定更多信息
            interface = interfaces.first()
        else:
            interface = interfaces.first()

        # 更新映射结果
        mapping.interface = interface
        mapping.mappingIp = mapping_ip
        mapping.save()

        return JsonResponse({'status': 'ok'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_http_methods(["GET"])
def get_map_list(request):
    try:
        # 获取前端传值
        scene_id = request.GET.get('sceneId')
        mapping_ip = request.GET.get('mappingIp')

        # 构建查询条件
        query = Q()
        if scene_id:
            query &= Q(sceneId=scene_id)
        if mapping_ip:
            query &= Q(mappingIp=mapping_ip)

        # 查询映射信息
        mappings = NodeMapping.objects.filter(query).select_related('interface')

        # 准备返回的数据
        mapping_list = [
            {
                'mappingId': mapping.id,
                'interfaceIp': mapping.interface.interfaceIp,
                'mappingIp': mapping.mappingIp
            }
            for mapping in mappings
        ]

        return JsonResponse({
            'mappingList': mapping_list
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


'''
生成配置文件
'''
import logging

logger = logging.getLogger(__name__)


def generate_exata_config(request):
    try:
        scene_id = request.GET.get('sceneId')
        if not scene_id:
            return JsonResponse({'status': 'error', 'message': 'Missing sceneId parameter'}, status=400)

        try:
            scene = Scene.objects.get(id=scene_id)
        except Scene.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Scene not found'}, status=404)

        # 计算仿真持续时间（分钟）
        time_delta = scene.endTime - scene.startTime
        simulation_duration = int(time_delta.total_seconds() // 60)  # 转换为整数分钟

        # 准备模板数据
        exata_config_data = {
            'scene': scene,
            'nodes': Node.objects.filter(sceneId=scene).prefetch_related('interfaces'),
            'links': Link.objects.filter(sceneId=scene).select_related('sourceInterface','destinationInterface'),
            'simulation_duration': simulation_duration  # 新增持续时间参数
        }

        config_content = render_to_string('exata/exata_config.template', exata_config_data)

        response = HttpResponse(config_content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{scene.sceneName}.config"'
        return response

    except Exception as e:
        logger.error(f'Error generating Exata config: {str(e)}', exc_info=True)
        return HttpResponse(f'Error generating Exata config: {str(e)}', status=500)
@csrf_exempt
@require_http_methods(["POST"])
def configure_protocol(request, node_id, interfaceIndex):
    try:
        # 查找接口
        interface = Interface.objects.get(node_id=node_id, interfaceIndex=interfaceIndex)
    except Interface.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Interface not found'}, status=404)

    try:
        data = json.loads(request.body)

        # 更新物理层配置
        physical_layer_data = data.get('physicalLayer', {})
        if hasattr(interface, 'physical_layer'):
            physical_layer = interface.physical_layer
        else:
            physical_layer = PhysicalLayer(interface=interface)

        physical_layer.radioType = physical_layer_data.get('radioType', physical_layer.radioType)
        physical_layer.radioCoverageId = physical_layer_data.get('radioCoverageId', physical_layer.radioCoverageId)
        physical_layer.centerFrequency = physical_layer_data.get('centerFrequency', physical_layer.centerFrequency)
        physical_layer.bandwidth = physical_layer_data.get('bandwidth', physical_layer.bandwidth)
        physical_layer.dataRate = physical_layer_data.get('dataRate', physical_layer.dataRate)
        physical_layer.transmitPower = physical_layer_data.get('transmitPower', physical_layer.transmitPower)
        physical_layer.receiveSensitivity = physical_layer_data.get('receiveSensitivity',
                                                                    physical_layer.receiveSensitivity)
        physical_layer.receiveThreshold = physical_layer_data.get('receiveThreshold', physical_layer.receiveThreshold)
        physical_layer.antennaType = physical_layer_data.get('antennaType', physical_layer.antennaType)
        physical_layer.gain = physical_layer_data.get('gain', physical_layer.gain)
        physical_layer.height = physical_layer_data.get('height', physical_layer.height)
        physical_layer.efficiency = physical_layer_data.get('efficiency', physical_layer.efficiency)
        physical_layer.mismatchLoss = physical_layer_data.get('mismatchLoss', physical_layer.mismatchLoss)
        physical_layer.cableLoss = physical_layer_data.get('cableLoss', physical_layer.cableLoss)
        physical_layer.connectionLoss = physical_layer_data.get('connectionLoss', physical_layer.connectionLoss)
        physical_layer.azimuth = physical_layer_data.get('azimuth', physical_layer.azimuth)
        physical_layer.elevation = physical_layer_data.get('elevation', physical_layer.elevation)
        physical_layer.roll = physical_layer_data.get('roll', physical_layer.roll)

        # 如果是 Patterned 天线，更新额外的字段
        if physical_layer.antennaType == 'Patterned':
            physical_layer.patternType = physical_layer_data.get('patternType', physical_layer.patternType)
            physical_layer.patternNumber = physical_layer_data.get('patternNumber', physical_layer.patternNumber)
            physical_layer.azimuthPatternFile = physical_layer_data.get('azimuthPatternFile',
                                                                        physical_layer.azimuthPatternFile)
            physical_layer.elevationPatternFile = physical_layer_data.get('elevationPatternFile',
                                                                          physical_layer.elevationPatternFile)
            physical_layer.patternCoverageParameter = physical_layer_data.get('patternCoverageParameter',
                                                                              physical_layer.patternCoverageParameter)
            physical_layer.azimuthResolution = physical_layer_data.get('azimuthResolution',
                                                                       physical_layer.azimuthResolution)
            physical_layer.elevationResolution = physical_layer_data.get('elevationResolution',
                                                                         physical_layer.elevationResolution)

        physical_layer.save()

        # 更新MAC层配置
        mac_layer_data = data.get('macLayer', {})
        if hasattr(interface, 'mac_layer'):
            mac_layer = interface.mac_layer
        else:
            mac_layer = MacLayer(interface=interface)

        mac_layer.macProtocol = mac_layer_data.get('macProtocol', mac_layer.macProtocol)
        mac_layer.shortPacketLimit = mac_layer_data.get('shortPacketLimit', mac_layer.shortPacketLimit)
        mac_layer.longPacketLimit = mac_layer_data.get('longPacketLimit', mac_layer.longPacketLimit)
        mac_layer.rtsThreshold = mac_layer_data.get('rtsThreshold', mac_layer.rtsThreshold)
        mac_layer.macPropagationDelay = mac_layer_data.get('macPropagationDelay', mac_layer.macPropagationDelay)
        mac_layer.save()

        # 更新网络层配置
        network_layer_data = data.get('networkLayer', {})
        if hasattr(interface, 'network_layer'):
            network_layer = interface.network_layer
        else:
            network_layer = NetworkLayer(interface=interface)

        network_layer.networkProtocol = network_layer_data.get('networkProtocol', network_layer.networkProtocol)
        network_layer.ipv4Address = network_layer_data.get('ipv4Address', network_layer.ipv4Address)
        network_layer.ipv4SubnetMask = network_layer_data.get('ipv4SubnetMask', network_layer.ipv4SubnetMask)
        network_layer.ipFragmentationUnit = network_layer_data.get('ipFragmentationUnit',
                                                                   network_layer.ipFragmentationUnit)
        network_layer.save()

        # 更新路由协议配置
        routing_protocol_data = data.get('routingProtocol', {})
        if hasattr(interface, 'routing_protocol'):
            routing_protocol = interface.routing_protocol
        else:
            routing_protocol = RoutingProtocol(interface=interface)

        routing_protocol.routingProtocol = routing_protocol_data.get('routingProtocol',
                                                                     routing_protocol.routingProtocol)
        routing_protocol.enableMulticast = routing_protocol_data.get('enableMulticast',
                                                                     routing_protocol.enableMulticast)
        routing_protocol.enableHSRP = routing_protocol_data.get('enableHSRP', routing_protocol.enableHSRP)
        routing_protocol.save()

        return JsonResponse({'status': 'success'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@require_http_methods(["GET"])
def get_interface_config(request, node_id, interfaceIndex):
    try:
        # 查找接口
        interface = Interface.objects.get(node_id=node_id, interfaceIndex=interfaceIndex)

        # 获取物理层配置
        try:
            physical_layer = interface.physical_layer
            physical_layer_data = {
                'radioType': physical_layer.radioType,
                'radioCoverageId': physical_layer.radioCoverageId,
                'centerFrequency': physical_layer.centerFrequency,
                'bandwidth': physical_layer.bandwidth,
                'dataRate': physical_layer.dataRate,
                'transmitPower': physical_layer.transmitPower,
                'receiveSensitivity': physical_layer.receiveSensitivity,
                'receiveThreshold': physical_layer.receiveThreshold,
                'antennaType': physical_layer.antennaType,
                'gain': physical_layer.gain,
                'height': physical_layer.height,
                'efficiency': physical_layer.efficiency,
                'mismatchLoss': physical_layer.mismatchLoss,
                'cableLoss': physical_layer.cableLoss,
                'connectionLoss': physical_layer.connectionLoss,
                'azimuth': physical_layer.azimuth,
                'elevation': physical_layer.elevation,
                'roll': physical_layer.roll,
            }
            if physical_layer.antennaType == 'Patterned':
                physical_layer_data.update({
                    'patternType': physical_layer.patternType,
                    'patternNumber': physical_layer.patternNumber,
                    'azimuthPatternFile': physical_layer.azimuthPatternFile,
                    'elevationPatternFile': physical_layer.elevationPatternFile,
                    'patternCoverageParameter': physical_layer.patternCoverageParameter,
                    'azimuthResolution': physical_layer.azimuthResolution,
                    'elevationResolution': physical_layer.elevationResolution,
                })
        except PhysicalLayer.DoesNotExist:
            physical_layer_data = None

        # 获取MAC层配置
        try:
            mac_layer = interface.mac_layer
            mac_layer_data = {
                'macProtocol': mac_layer.macProtocol,
                'shortPacketLimit': mac_layer.shortPacketLimit,
                'longPacketLimit': mac_layer.longPacketLimit,
                'rtsThreshold': mac_layer.rtsThreshold,
                'macPropagationDelay': mac_layer.macPropagationDelay,
            }
        except MacLayer.DoesNotExist:
            mac_layer_data = None

        # 获取网络层配置
        try:
            network_layer = interface.network_layer
            network_layer_data = {
                'networkProtocol': network_layer.networkProtocol,
                'ipv4Address': network_layer.ipv4Address,
                'ipv4SubnetMask': network_layer.ipv4SubnetMask,
                'ipFragmentationUnit': network_layer.ipFragmentationUnit,
            }
        except NetworkLayer.DoesNotExist:
            network_layer_data = None

        # 获取路由协议配置
        try:
            routing_protocol = interface.routing_protocol
            routing_protocol_data = {
                'routingProtocol': routing_protocol.routingProtocol,
                'enableMulticast': routing_protocol.enableMulticast,
                'enableHSRP': routing_protocol.enableHSRP,
            }
        except RoutingProtocol.DoesNotExist:
            routing_protocol_data = None

        # 构建响应数据
        response_data = {
            'interfaceIp': interface.interfaceIp,
            'interfaceIndex': interface.interfaceIndex,
            'physicalLayer': physical_layer_data,
            'macLayer': mac_layer_data,
            'networkLayer': network_layer_data,
            'routingProtocol': routing_protocol_data,
        }

        return JsonResponse({'status': 'success', 'data': response_data})

    except Interface.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Interface not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


'''
生成文件
'''
def generate_link_file(request):
    try:
        # 获取查询参数
        scene_id = request.GET.get('sceneId')
        if not scene_id:
            return HttpResponse('Error: Missing sceneId parameter', status=400)

        # 获取指定场景的所有链路信息
        links = Link.objects.filter(sceneId=scene_id)

        # 准备 link.txt 文件内容
        link_content = []
        for link in links:
            # 获取接口 IP 地址
            source_interfaceIp = link.sourceInterface.interfaceIp if link.sourceInterface else ""
            destination_interfaceIp = link.destinationInterface.interfaceIp if link.destinationInterface else ""

            # 构建链路数据行
            line = (
                f"{link.id} -1 "
                f"{link.sourceNodeId.id} {link.destinationNodeId.id} "
                f"{link.sourceInterface.interfaceIndex if link.sourceInterface else ''} "
                f"{link.destinationInterface.interfaceIndex if link.destinationInterface else ''} "
                f"{source_interfaceIp} {destination_interfaceIp} "
                f"{1 if link.linkType == '无线' else 2}\n"
            )
            link_content.append(line)

        # 将内容写入文件或返回给用户
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="link.txt"'  # 指定文件名为 link.txt
        response.writelines(link_content)

        return response

    except Exception as e:
        return HttpResponse(f'Error generating link file: {str(e)}', status=500)


#轨道六根数：包括偏心率、近地点幅角、轨道倾角、平近点角、均运动、升交点赤经。
def generate_orbit_file(request):
    try:
        # 获取查询参数
        scene_id = request.GET.get('sceneId')
        if not scene_id:
            return HttpResponse('Error: Missing sceneId parameter', status=400)

        # 获取指定场景的所有卫星节点
        satellites = Node.objects.filter(sceneId=scene_id, nodeType='satellite')

        # 准备 orbit.txt 文件内容
        orbit_content = []
        for satellite in satellites:
            # 构建轨道数据行
            line = (
                f"{satellite.id} "
                f"{satellite.startTime.year} {satellite.startTime.month} {satellite.startTime.day} "
                f"{satellite.startTime.hour} {satellite.startTime.minute} {satellite.startTime.second} "
                f"{satellite.startTime.microsecond // 1000} "
                f"{satellite.eccentricity} "
                f"{satellite.argPerigee} "
                f"{satellite.inclination} "
                f"{satellite.meanAnomaly} "
                f"{satellite.meanMotion} "
                f"{satellite.raan} "
                f"{satellite.nodeImage} "
                f"{satellite.nodeName}\n"
            )
            orbit_content.append(line)

        # 将内容写入文件或返回给用户
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="orbit.txt"'
        response.writelines(orbit_content)

        return response

    except Exception as e:
        return HttpResponse(f'Error generating orbit file: {str(e)}', status=500)




def generate_node_file(request):
    try:
        # 获取查询参数
        scene_id = request.GET.get('sceneId')
        if not scene_id:
            return HttpResponse('Error: Missing sceneId parameter', status=400)

        # 获取指定场景的所有普通节点
        nodes = Node.objects.filter(sceneId=scene_id, nodeType='normalNode')

        # 准备 node.txt 文件内容
        node_content = []
        for node in nodes:
            # 构建节点数据行
            line = (
                f"{node.id} "
                f"{node.startTime.year} {node.startTime.month} {node.startTime.day} "
                f"{node.startTime.hour} {node.startTime.minute} {node.startTime.second} "
                f"{node.startTime.microsecond // 1000} "
                f"{node.lat} "
                f"{node.lon} "
                f"{node.alt} "
                f"{node.nodeImage} "
                f"{node.nodeName}\n"
            )
            node_content.append(line)

        # 将内容写入文件或返回给用户
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="node.txt"'
        response.writelines(node_content)

        return response

    except Exception as e:
        return HttpResponse(f'Error generating node file: {str(e)}', status=500)



def generate_fault_file(request):
    try:
        # 获取查询参数
        scene_id = request.GET.get('sceneId')
        if not scene_id:
            return HttpResponse('Error: Missing sceneId parameter', status=400)

        # 获取指定场景
        try:
            scene = Scene.objects.get(id=scene_id)
        except Scene.DoesNotExist:
            return HttpResponse('Error: Scene not found', status=404)

        # 获取指定场景的所有故障记录
        errors = Error.objects.filter(sceneId=scene)

        # 准备 fault.txt 文件内容
        fault_content = []
        for error in errors:
            # 获取节点的所有接口
            interfaces = Interface.objects.filter(node=error.nodeId)
            if not interfaces:
                # 如果节点没有接口，跳过此错误记录
                continue

            # 计算故障开始和结束时间相对于场景开始时间的秒数
            start_time = (error.errorStartTime - scene.startTime).total_seconds()
            end_time = (error.errorEndTime - scene.startTime).total_seconds()

            # 构建故障数据行，为每个接口生成一行
            for interface in interfaces:
                line = (
                    f"{error.nodeId.id} {interface.interfaceIndex} {int(start_time)} {int(end_time)}\n"
                )
                fault_content.append(line)

        # 将内容写入文件或返回给用户
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="fault.txt"'
        response.writelines(fault_content)

        return response

    except Exception as e:
        return HttpResponse(f'Error generating fault file: {str(e)}', status=500)



def generate_initial_file(request):
    try:
        # 获取查询参数
        scene_id = request.GET.get('sceneId')
        if not scene_id:
            return HttpResponse('Error: Missing sceneId parameter', status=400)

        # 获取指定场景
        try:
            scene = Scene.objects.get(id=scene_id)
        except Scene.DoesNotExist:
            return HttpResponse('Error: Scene not found', status=404)

        # 计算仿真结束时间相对于开始时间的秒数
        simulation_end_time = (scene.endTime - scene.startTime).total_seconds()

        # 准备 initial.txt 文件内容
        initial_content = [
            f"INTERVAL {scene.simulationStep}\n",
            f"FINAL {int(simulation_end_time)}\n"
        ]

        # 将内容写入文件或返回给用户
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="initial.txt"'
        response.writelines(initial_content)

        return response

    except Exception as e:
        return HttpResponse(f'Error generating initial file: {str(e)}', status=500)

'''
生成文件
'''
'''
def generate_scene_app(request,):
    scene_id = request.GET.get('sceneId')
    try:
        scene = Scene.objects.get(pk=scene_id)
    except Scene.DoesNotExist:
        return HttpResponse("Scene not found", status=404)

    configurations = Configuration.objects.filter(sceneId=scene)

    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="场景名称_{scene_id}.app"'

    for config in configurations:
        if config.businessType == 'CBR':
            start_time = config.cbrStartTime
            end_time = config.cbrEndTime
            packet_count = 0
            packet_size = config.cbrPacketSize
            interval = config.cbrSendInterval
        elif config.businessType == 'FTP':
            start_time = config.ftpStartTime
            end_time = None
            packet_count = config.ftpPacketCount
            packet_size = 0
            interval = 0
        else:
            continue

        # 将开始时间和结束时间转换为相对于场景开始时间的秒数
        time_offset = 0
        if start_time:
            time_offset = (start_time - scene.startTime).total_seconds()

        end_time_offset = 0
        if end_time:
            end_time_offset = (end_time - scene.startTime).total_seconds()

        # 构建文件行
        config_line = f"{config.businessType} {config.sourceNodeId.id} {config.destinationNodeId.id} {packet_count} {packet_size} {interval} {int(time_offset)} {int(end_time_offset)}\n"
        response.write(config_line)

    return response


def generate_scene_nodes(request):
    # 从请求中获取sceneId参数
    scene_id = request.GET.get('sceneId')
    if not scene_id:
        return HttpResponse('Error: Missing sceneId parameter', status=400)

    try:
        # 尝试将sceneId转换为整数
        scene_id = int(scene_id)
    except ValueError:
        return HttpResponse('Error: Invalid sceneId parameter', status=400)

    try:
        # 检索指定场景
        scene = Scene.objects.get(pk=scene_id)
    except Scene.DoesNotExist:
        return HttpResponse('Error: Scene not found', status=404)

    # 获取场景中所有的节点
    nodes = Node.objects.filter(Q(sceneId=scene)).order_by('id')

    # 创建HTTP响应对象，设置内容类型为纯文本
    response = HttpResponse(content_type='text/plain')
    # 设置响应头，指定文件名为场景名称加.nodes后缀
    response['Content-Disposition'] = f'attachment; filename="{scene.sceneName}.nodes"'

    # 处理每个节点并写入响应内容
    for node in nodes:
        node_line = ''
        # 添加节点ID
        node_line += f"{node.id} "

        # 计算节点开始时间相对于场景开始时间的秒数
        if node.startTime and scene.startTime:
            time_offset = (node.startTime - scene.startTime).total_seconds()
        else:
            time_offset = 0
        node_line += f"{int(time_offset)} "

        # 添加经纬度和高度
        if node.nodeType == 'normalNode':
            node_line += f"{node.lat if node.lat is not None else 0} {node.lon if node.lon is not None else 0} {node.alt if node.alt is not None else 0}"
        else:
            # 对于非普通节点类型，提供默认值
            node_line += "0 0 0"

        # 添加三个0
        node_line += " 0 0 0"

        # 换行
        node_line += "\n"

        # 将构建好的节点行写入响应
        response.write(node_line)

    return response


def generate_scene_fault(request):
    # 从请求中获取sceneId参数
    scene_id = request.GET.get('sceneId')
    if not scene_id:
        return HttpResponse('Error: Missing sceneId parameter', status=400)

    try:
        # 尝试将sceneId转换为整数
        scene_id = int(scene_id)
    except ValueError:
        return HttpResponse('Error: Invalid sceneId parameter', status=400)

    try:
        # 检索指定场景
        scene = Scene.objects.get(pk=scene_id)
    except Scene.DoesNotExist:
        return HttpResponse('Error: Scene not found', status=404)

    # 获取场景中所有的链路错误
    link_errors = LinkError.objects.filter(sceneId=scene)

    # 创建HTTP响应对象，设置内容类型为纯文本
    response = HttpResponse(content_type='text/plain')
    # 设置响应头，指定文件名为场景名称加.fault后缀
    response['Content-Disposition'] = f'attachment; filename="{scene.sceneName}.fault"'

    # 处理每个链路错误并写入响应内容
    for link_error in link_errors:
        link = link_error.linkId
        source_node = link.sourceNodeId
        destination_node = link.destinationNodeId

        # 计算错误开始时间和结束时间相对于场景开始时间的秒数
        if link_error.errorStartTime and scene.startTime:
            start_time_offset = (link_error.errorStartTime - scene.startTime).total_seconds()
        else:
            start_time_offset = 0

        if link_error.errorEndTime and scene.startTime:
            end_time_offset = (link_error.errorEndTime - scene.startTime).total_seconds()
        else:
            end_time_offset = 0

        # 获取源节点和目的节点的所有接口序号
        source_interfaces = Interface.objects.filter(node=source_node)
        destination_interfaces = Interface.objects.filter(node=destination_node)

        # 构建文件行
        for source_interface in source_interfaces:
            for destination_interface in destination_interfaces:
                # 假设子网ID为1
                fault_line = f"INTERFACE-FAULT LINK1/{source_node.id}/{source_interface.interfaceIndex} {int(start_time_offset)}S {int(end_time_offset)}S NO\n"
                response.write(fault_line)
                fault_line = f"INTERFACE-FAULT LINK1/{destination_node.id}/{destination_interface.interfaceIndex} {int(start_time_offset)}S {int(end_time_offset)}S NO\n"
                response.write(fault_line)

    return response
def generate_display_file(request):
    scene_id = request.GET.get('sceneId')
    if not scene_id:
        return HttpResponse('Error: Missing sceneId parameter', status=400)

    try:
        scene_id = int(scene_id)
    except ValueError:
        return HttpResponse('Error: Invalid sceneId parameter', status=400)

    try:
        scene = Scene.objects.get(pk=scene_id)
    except Scene.DoesNotExist:
        return HttpResponse('Error: Scene not found', status=404)

    display_content = (
        "[General]\n"
        "showAnimation=false\n"
        "showLegend=true\n"
        "showNodeIds=true\n"
        "showHierarchy=true\n"
        "showHierarchyDisplay=true\n"
        "showIpAddresses=false\n"
        "showWiredLinks=true\n"
        "showAppLinks=true\n"
        "showGrid=true\n"
        "showBgImages=true\n"
        "showWeather=true\n"
        "showHierarchyNames=false\n"
        "showPatterns=true\n"
        "showNightView=false\n"
        "showHostNames=false\n"
        "showInterfaceNames=true\n"
        "showWirelessSubnets=true\n"
        "showSatelliteLinks=true\n"
        "showRuler=true\n"
        "showWaypoint=true\n"
        "showAnnotations=true\n"
        "showAsIds=false\n"
        "showQueues=false\n"
        "showAxes=false\n"
        "nodeOrientationIcon=true\n"
        "nodeOrientationArrow=true\n"
        "viewHeatMapInDesignMode=false\n"
        "runTimeIndicator=false"
    )

    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{scene.sceneName}.display"'
    response.write(display_content)
    return response
'''


def download_all_files(request):
    scene_id = request.GET.get('sceneId')
    if not scene_id:
        return HttpResponse('Error: Missing sceneId parameter', status=400)

    try:
        scene_id = int(scene_id)
    except ValueError:
        return HttpResponse('Error: Invalid sceneId parameter', status=400)

    try:
        scene = Scene.objects.get(pk=scene_id)
    except Scene.DoesNotExist:
        return HttpResponse('Error: Scene not found', status=404)

    # 创建场景文件夹
    scene_folder = os.path.join(settings.MEDIA_ROOT, 'scene_files', scene.sceneName)
    os.makedirs(scene_folder, exist_ok=True)  # 确保文件夹存在

    # 清空现有文件夹内容
    for filename in os.listdir(scene_folder):
        file_path = os.path.join(scene_folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"删除文件失败 {file_path}: {e}")

    # 计算仿真持续时间
    time_delta = scene.endTime - scene.startTime
    simulation_duration = int(time_delta.total_seconds() // 60)

    # 获取所有相关数据
    links = Link.objects.filter(sceneId=scene).select_related('sourceInterface', 'destinationInterface')
    nodes = Node.objects.filter(sceneId=scene).prefetch_related('interfaces')
    satellites = Node.objects.filter(sceneId=scene, nodeType='satellite')
    normal_nodes = Node.objects.filter(sceneId=scene, nodeType='normalNode')
    errors = Error.objects.filter(sceneId=scene)
    # 计算最大节点 ID
    max_node_id = nodes.aggregate(max_id=Max('id'))['max_id'] or 0
    count = Node.objects.filter(sceneId=scene).count()
    num_nodes = count
    # 查找默认子网（假设名为"默认无线子网"）
    default_subnet = Subnet.objects.filter(
        sceneId=scene,
    ).first()
    # 收集孤立节点（没有链路的节点）
    # 1. 获取所有属于默认子网的节点（孤立节点）
    isolated_nodes = Node.objects.filter(
        sceneId=scene,
        interfaces__subnet=default_subnet
    ).distinct()
    # 获取孤立节点ID列表
    isolated_node_ids = [str(node.id) for node in isolated_nodes]
    # 获取所有子网
    all_subnets = Subnet.objects.filter(sceneId=scene,subnetType = Subnet.SubnetTypeChoices.SUB).prefetch_related('interfaces__node')
    # 分离默认子网与其他子网
    subnets = all_subnets.exclude(id=default_subnet.id if default_subnet else None)
    print(subnets)
    # 准备模板数据
    exata_config_data = {
        'scene': scene,
        'num_nodes':num_nodes,
        'nodes': nodes,
        'links': links,
        'simulation_duration': simulation_duration,
        'default_subnet': default_subnet,
        'subnets': subnets,
        'isolated_node_ids': isolated_node_ids
    }

    # 生成 Exata 配置文件内容
    exata_config_content = render_to_string('exata/exata_config.template', exata_config_data)

    # 保存到文件
    config_path = os.path.join(scene_folder, f"{scene.sceneName}.config")
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(exata_config_content)

    # 初始化响应
    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{scene.sceneName}_files.txt"'

    # 写入 Exata 配置文件内容
    response.write(f"[{scene.sceneName}.config]\n")
    response.write(exata_config_content + "\n\n")

    # 生成并保存 .app 文件
    app_content = generate_scene_app_content(scene)
    app_path = os.path.join(scene_folder, f"{scene.sceneName}.app")
    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(app_content)

    response.write(f"[{scene.sceneName}.app]\n")
    response.write(app_content + "\n\n")

    # 生成并保存 .nodes 文件
    nodes_content = generate_scene_nodes_content(scene)
    nodes_path = os.path.join(scene_folder, f"{scene.sceneName}.nodes")
    with open(nodes_path, 'w', encoding='utf-8') as f:
        f.write(nodes_content)

    response.write(f"[{scene.sceneName}.nodes]\n")
    response.write(nodes_content + "\n\n")

    # 生成并保存 .fault 文件
    fault_content = generate_scene_fault_content(scene)
    fault_path = os.path.join(scene_folder, f"{scene.sceneName}.fault")
    with open(fault_path, 'w', encoding='utf-8') as f:
        f.write(fault_content)

    response.write(f"[{scene.sceneName}.fault]\n")
    response.write(fault_content + "\n\n")

    # 生成并保存 .display 文件
    display_content = generate_display_file_content(scene)
    display_path = os.path.join(scene_folder, f"{scene.sceneName}.display")
    with open(display_path, 'w', encoding='utf-8') as f:
        f.write(display_content)

    response.write(f"[{scene.sceneName}.display]\n")
    response.write(display_content + "\n\n")

    # 生成并保存 link.txt 文件
    link_content = []
    for link in links:
        source_interfaceIp = link.sourceInterface.interfaceIp if link.sourceInterface else ""
        destination_interfaceIp = link.destinationInterface.interfaceIp if link.destinationInterface else ""
        line = (
            f"{link.id} -1 "
            f"{link.sourceNodeId.id} {link.destinationNodeId.id} "
            f"{link.sourceInterface.interfaceIndex if link.sourceInterface else ''} "
            f"{link.destinationInterface.interfaceIndex if link.destinationInterface else ''} "
            f"{source_interfaceIp} {destination_interfaceIp} "
            f"{1 if link.linkType == '无线' else 2}\n"
        )
        link_content.append(line)

    link_path = os.path.join(scene_folder, "link.txt")
    with open(link_path, 'w', encoding='utf-8') as f:
        f.writelines(link_content)

    response.write("[link.txt]\n")
    response.writelines(link_content)
    response.write("\n")

    # 生成并保存 orbit.txt 文件
    orbit_content = []
    for satellite in satellites:
        line = (
            f"{satellite.id} "
            f"{satellite.startTime.year} {satellite.startTime.month} {satellite.startTime.day} "
            f"{satellite.startTime.hour} {satellite.startTime.minute} {satellite.startTime.second} "
            f"{satellite.startTime.microsecond // 1000} "
            f"{satellite.eccentricity} "
            f"{satellite.argPerigee} "
            f"{satellite.inclination} "
            f"{satellite.meanAnomaly} "
            f"{satellite.meanMotion} "
            f"{satellite.raan} "
            f"{satellite.nodeImage} "
            f"{satellite.nodeName}\n"
        )
        orbit_content.append(line)

    orbit_path = os.path.join(scene_folder, "orbit.txt")
    with open(orbit_path, 'w', encoding='utf-8') as f:
        f.writelines(orbit_content)

    response.write("[orbit.txt]\n")
    response.writelines(orbit_content)
    response.write("\n")

    # 生成并保存 node.txt 文件
    node_content = []
    for node in normal_nodes:
        line = (
            f"{node.id} "
            +"0 "+
            f"{node.lat} "
            f"{node.lon} "
            f"{node.alt} "
            f"{node.nodeImage} "
            f"{node.nodeName}\n"
        )
        node_content.append(line)

    node_path = os.path.join(scene_folder, "node.txt")
    with open(node_path, 'w', encoding='utf-8') as f:
        f.writelines(node_content)

    response.write("[node.txt]\n")
    response.writelines(node_content)
    response.write("\n")

    # 生成并保存 fault.txt 文件
    fault_txt_content = []
    for error in errors:
        interfaces = Interface.objects.filter(node=error.nodeId)
        if not interfaces:
            continue
        start_time = (error.errorStartTime - scene.startTime).total_seconds()
        end_time = (error.errorEndTime - scene.startTime).total_seconds()
        for interface in interfaces:
            line = (
                f"{error.nodeId.id} {interface.interfaceIndex} {int(start_time)} {int(end_time)}\n"
            )
            fault_txt_content.append(line)

    fault_txt_path = os.path.join(scene_folder, "fault.txt")
    with open(fault_txt_path, 'w', encoding='utf-8') as f:
        f.writelines(fault_txt_content)

    response.write("[fault.txt]\n")
    response.writelines(fault_txt_content)
    response.write("\n")

    # 生成并保存 initial.txt 文件
    simulation_end_time = (scene.endTime - scene.startTime).total_seconds()
    initial_content = [
        f"INTERVAL {scene.simulationStep}\n",
        f"FINAL {int(simulation_end_time)}\n"
    ]

    initial_path = os.path.join(scene_folder, "initial.txt")
    with open(initial_path, 'w', encoding='utf-8') as f:
        f.writelines(initial_content)

    response.write("[initial.txt]\n")
    response.writelines(initial_content)

    return response


def generate_scene_app_content(scene):
    configurations = Configuration.objects.filter(sceneId=scene)
    content = ""
    for config in configurations:
        if config.businessType == 'CBR':
            start_time = config.cbrStartTime
            end_time = config.cbrEndTime
            packet_count = 0
            packet_size = config.cbrPacketSize
            interval = config.cbrSendInterval
        elif config.businessType == 'FTP':
            start_time = config.ftpStartTime
            end_time = None
            packet_count = config.ftpPacketCount
            packet_size = 0
            interval = 0
        else:
            continue

        time_offset = 0
        if start_time:
            time_offset = (start_time - scene.startTime).total_seconds()

        end_time_offset = 0
        if end_time:
            end_time_offset = (end_time - scene.startTime).total_seconds()

        config_line = f"{config.businessType} {config.sourceNodeId.id} {config.destinationNodeId.id} {packet_count} {packet_size} {interval} {int(time_offset)} {int(end_time_offset)}\n"
        content += config_line
    return content


def generate_scene_nodes_content(scene):
    nodes = Node.objects.filter(Q(sceneId=scene)).order_by('id')
    content = ""
    for node in nodes:
        node_line = f"{node.id} "
        if node.startTime and scene.startTime:
            # time_offset = (node.startTime - scene.startTime).total_seconds()
            time_offset = 0
        else:
            time_offset = 0
        node_line += f"{int(time_offset)} "

        if node.nodeType == 'normalNode':
            node_line += f"({node.lat if node.lat is not None else 0} {node.lon if node.lon is not None else 0} {node.alt if node.alt is not None else 0})"
        else:
            node_line += "(0 0 0)"

        node_line += " 0 0 0\n"
        content += node_line
    return content


def generate_scene_fault_content(scene):
    link_errors = LinkError.objects.filter(sceneId=scene)
    content = ""
    for link_error in link_errors:
        link = link_error.linkId
        source_node = link.sourceNodeId
        destination_node = link.destinationNodeId

        if link_error.errorStartTime and scene.startTime:
            start_time_offset = (link_error.errorStartTime - scene.startTime).total_seconds()
        else:
            start_time_offset = 0

        if link_error.errorEndTime and scene.startTime:
            end_time_offset = (link_error.errorEndTime - scene.startTime).total_seconds()
        else:
            end_time_offset = 0

        source_interfaces = Interface.objects.filter(node=source_node)
        destination_interfaces = Interface.objects.filter(node=destination_node)

        for source_interface in source_interfaces:
            for destination_interface in destination_interfaces:
                fault_line = f"INTERFACE-FAULT LINK1/{source_node.id}/{source_interface.interfaceIndex} {int(start_time_offset)}S {int(end_time_offset)}S NO\n"
                content += fault_line
                fault_line = f"INTERFACE-FAULT LINK1/{destination_node.id}/{destination_interface.interfaceIndex} {int(start_time_offset)}S {int(end_time_offset)}S NO\n"
                content += fault_line
    return content


def generate_display_file_content(scene):
    return (
        "[General]\n"
        "showAnimation=false\n"
        "showLegend=true\n"
        "showNodeIds=true\n"
        "showHierarchy=true\n"
        "showHierarchyDisplay=true\n"
        "showIpAddresses=false\n"
        "showWiredLinks=true\n"
        "showAppLinks=true\n"
        "showGrid=true\n"
        "showBgImages=true\n"
        "showWeather=true\n"
        "showHierarchyNames=false\n"
        "showPatterns=true\n"
        "showNightView=false\n"
        "showHostNames=false\n"
        "showInterfaceNames=true\n"
        "showWirelessSubnets=true\n"
        "showSatelliteLinks=true\n"
        "showRuler=true\n"
        "showWaypoint=true\n"
        "showAnnotations=true\n"
        "showAsIds=false\n"
        "showQueues=false\n"
        "showAxes=false\n"
        "nodeOrientationIcon=true\n"
        "nodeOrientationArrow=true\n"
        "viewHeatMapInDesignMode=false\n"
        "runTimeIndicator=false"
    )



class ResultsAnalysis:

    def __init__(self, file_path):
        """初始化类，设置目标文件路径"""
        self.file_path = Path(file_path)
        if not self.file_path.exists() or not self.file_path.is_file():
            raise ValueError(f"文件不存在或不是有效文件: {self.file_path}")
        self.directory = self.file_path.parent  # 存储文件所在目录


    def read_filter_file(self):
        """
        读取该目录下的第一个文件，并打印文件内容。

        假设该文件是文本格式（如txt）。
        """
        try:
            first_file = self.file_path
            print(first_file)
            # 存储符合条件的行
            filtered_lines = []

            # 打开并读取文件内容
            with open(first_file, "r", encoding="utf-8") as file:
                print(f"\n正在读取文件: {first_file.name}")

                # 遍历文件的每一行
                for line in file:
                    # 去除每行的空白字符，并检查第三列是否是有效的业务标识符
                    columns = line.split(',')
                    if len(columns) > 2 and columns[2].strip() and columns[3].strip() == "Application":  # 第三列有值
                        filtered_lines.append(line.strip())  # 存储符合条件的行

            # 输出符合条件的行数
            # print(f"共找到 {len(filtered_lines)} 行包含业务标识符的数据：")
            # return filtered_lines

            # 存储结果列表
            results_sent = []
            results_received = []
            results_drop = []
            results_delay = []
            results_jitter = []
            results_throughput = []

            business_info = {}

            business_sent = {}
            business_received = {}
            business_delays = {}
            business_jitter = {}
            business_throughput = {}
            for line in filtered_lines:
                fields = [field.strip() for field in line.split(',')]
                business_id = fields[2].strip('[]')
                node_id = fields[0].strip()
                service_type = fields[4].strip()

                # 发包统计
                sent_value = None
                if "Total Unicast Fragments Sent" in line:
                    sent_match = re.search(r"Total Unicast Fragments Sent \(fragments\) = ([\d\.]+)", line)
                    if sent_match:
                        sent_value = float(sent_match.group(1))
                        # 存储延迟与业务序列号的关联
                        business_sent[business_id] = sent_value

                # 收包统计
                received_value = None
                if "Total Unicast Fragments Received" in line:
                    received_match = re.search(r"Total Unicast Fragments Received \(fragments\) = ([\d\.]+)", line)
                    if received_match:
                        received_value = float(received_match.group(1))
                        # 存储延迟与业务序列号的关联
                        business_received[business_id] = received_value

                # 延迟统计
                delay_value = None
                if "Average Unicast End-to-End Delay" in line:
                    delay_match = re.search(r"Average Unicast End-to-End Delay \(seconds\) = ([\d\.]+)", line)
                    if delay_match:
                        delay_value = float(delay_match.group(1))
                        # 存储延迟与业务序列号的关联
                        business_delays[business_id] = delay_value

                # 抖动统计
                jitter_value = None
                if "Average Unicast Jitter" in line:
                    jitter_match = re.search(r"Average Unicast Jitter \(seconds\) = ([\d\.]+)", line)
                    if jitter_match:
                        jitter_value = float(jitter_match.group(1))
                        # 存储延迟与业务序列号的关联
                        business_jitter[business_id] = jitter_value

                # 吞吐量统计
                throughput_value = None
                if "Unicast Received Throughput" in line:
                    throughput_match = re.search(r"Unicast Received Throughput \(bits/second\) = ([\d\.]+)", line)
                    if throughput_match:
                        throughput_value = float(throughput_match.group(1))
                        # 存储延迟与业务序列号的关联
                        business_throughput[business_id] = throughput_value

                # 判断是起始节点还是终端节点
                if service_type == "CBR Client":  # 起始节点
                    if business_id not in business_info:
                        business_info[business_id] = {"start_node": node_id, "end_node": None}
                    else:
                        business_info[business_id]["start_node"] = node_id
                elif service_type == "CBR Server":  # 终端节点
                    if business_id not in business_info:
                        business_info[business_id] = {"start_node": None, "end_node": node_id}
                    else:
                        business_info[business_id]["end_node"] = node_id

            for business_id, info in business_info.items():
                if info["start_node"] and info["end_node"]:
                    # 获取发包
                    sent = business_sent.get(business_id, None)
                    if sent is not None:
                        results_sent.append(['bar', business_id, info["start_node"] + '-' + info["end_node"], sent])

                    # 获取收包
                    received = business_received.get(business_id, None)
                    if received is not None:
                        results_received.append(['bar', business_id, info["start_node"] + '-' + info["end_node"], received])

                    # 获取业务丢包率
                    drop = received / sent
                    if drop is not None:
                        results_drop.append(['bar', business_id, info["start_node"] + '-' + info["end_node"], drop])

                    # 获取延迟值
                    delay = business_delays.get(business_id, None)
                    if delay is not None:
                        results_delay.append(['bar', business_id, info["start_node"] + '-' + info["end_node"], delay])
                    # 获取抖动值
                    jitter = business_jitter.get(business_id, None)
                    if jitter is not None:
                        results_jitter.append(['bar', business_id, info["start_node"] + '-' + info["end_node"], jitter])
                    # 获取吞吐量值
                    throughput = business_throughput.get(business_id, None)
                    if throughput is not None:
                        results_throughput.append(['bar', business_id, info["start_node"] + '-' + info["end_node"], throughput])

            results_sent_dic = {
                'type': 'bar',
                'serveiceid': [item[1] for item in results_sent],
                'x': [item[2] for item in results_sent],
                'y': [item[3] for item in results_sent]
            }

            results_received_dic = {
                'type': 'bar',
                'serveiceid': [item[1] for item in results_received],
                'x': [item[2] for item in results_received],
                'y': [item[3] for item in results_received]
            }

            results_drop_dic = {
                'type': 'bar',
                'serveiceid': [item[1] for item in results_drop],
                'x': [item[2] for item in results_drop],
                'y': [item[3] for item in results_drop]
            }

            results_delay_dic = {
                'type': 'bar',
                'serveiceid': [item[1] for item in results_delay],
                'x': [item[2] for item in results_delay],
                'y': [item[3] for item in results_delay]
            }

            results_jitter_dic = {
                'type': 'bar',
                'serveiceid': [item[1] for item in results_jitter],
                'x': [item[2] for item in results_jitter],
                'y': [item[3] for item in results_jitter]
            }

            results_throughput_dic = {
                'type': 'bar',
                'serveiceid': [item[1] for item in results_throughput],
                'x': [item[2] for item in results_throughput],
                'y': [item[3] for item in results_throughput]
            }

            json_results_sent = json.dumps(results_sent_dic)
            json_results_received = json.dumps(results_received_dic)
            json_results_drop = json.dumps(results_drop_dic)
            json_results_delay = json.dumps(results_delay_dic)
            json_results_jitter = json.dumps(results_jitter_dic)
            json_results_throughput = json.dumps(results_throughput_dic)

            return json_results_sent, json_results_received, json_results_drop, json_results_delay, json_results_jitter, json_results_throughput

        except Exception as e:
            print(f"读取文件时发生错误: {e}")


@require_http_methods(["GET"])  # 只允许GET请求
def analysis_results(request):
    """处理分析结果请求的函数视图"""
    try:
        # 只处理GET请求
        if request.method != 'GET':
            return JsonResponse({
                "status": "error",
                "message": "仅支持GET方法"
            }, status=405)

        # 获取路径参数
        directory_path = request.GET.get('path', '')
        if not directory_path:
            return JsonResponse({
                "status": "error",
                "message": "缺少必要参数: path"
            }, status=400)

        # 使用Pathlib正确拼接路径，确保使用系统默认分隔符
        base_dir = Path('scene_files')
        full_path = base_dir / directory_path
        print(full_path)
        # 安全检查：防止路径遍历攻击
        if not str(full_path).startswith(str(base_dir)):
            return JsonResponse({
                "status": "error",
                "message": "非法路径"
            }, status=400)

        # 创建分析实例
        analyzer = ResultsAnalysis(full_path)
        print('创建实力成功')
        # 获取分析结果
        results = analyzer.read_filter_file()

        # 组织响应数据
        return JsonResponse({
            "status": "success",
            "data": {
                "sent": json.loads(results[0]),
                "received": json.loads(results[1]),
                "drop_rate": json.loads(results[2]),
                "delay": json.loads(results[3]),
                "jitter": json.loads(results[4]),
                "throughput": json.loads(results[5])
            }
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"分析失败: {str(e)}"
        }, status=500)


def get_scene_files(request):
    """
    获取 scene_files 文件夹下一级的所有文件夹名称，以及每个文件夹中所有 .stat 文件的名称
    请求方法: GET
    返回: JSON {
        status: 'success',
        folders: {
            "folder1": ["file1.stat", "file2.stat"],
            "folder2": ["file3.stat"],
            ...
        }
    } 或错误信息
    """
    try:
        # 构建 scene_files 文件夹路径
        scene_files_path = os.path.join(settings.MEDIA_ROOT, 'scene_files')

        # 检查文件夹是否存在
        if not os.path.exists(scene_files_path):
            return JsonResponse({'status': 'error', 'message': 'scene_files folder not found'}, status=404)

        # 获取所有一级文件夹及其中的 .stat 文件
        folder_files = {}

        for folder_name in os.listdir(scene_files_path):
            folder_path = os.path.join(scene_files_path, folder_name)

            # 只处理文件夹
            if not os.path.isdir(folder_path):
                continue

            # 获取文件夹中的所有 .stat 文件
            stat_files = []
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)

                # 检查是否是 .stat 文件
                if os.path.isfile(file_path) and file_name.lower().endswith('.stat'):
                    stat_files.append(file_name)

            # 按文件名排序
            stat_files.sort()
            folder_files[folder_name] = stat_files

        return JsonResponse({
            'status': 'success',
            'folders': folder_files
        })

    except Exception as e:
        import traceback
        logger.error(f"Error in get_scene_files: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


selected_scene = None
@require_http_methods(["POST"])
@csrf_exempt
def start_simulation(request):
    global absolute_path
    global selected_scene
    try:
        # 解析JSON请求体
        data = json.loads(request.body)
        scene_id = data.get('sceneId')

        if not scene_id:
            return JsonResponse({
                'status': 'error',
                'message': '缺少场景ID参数'
            }, status=400)

        try:
            # 获取场景对象
            scene = Scene.objects.get(id=scene_id)
        except Scene.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'场景ID {scene_id} 不存在'
            }, status=404)

        # 设置当前选中的场景
        selected_scene = scene_id

        # ====== 新增功能：获取并打印场景文件夹绝对路径 ======
        # 构建场景文件夹路径
        scene_folder = os.path.join(
            settings.MEDIA_ROOT,
            'scene_files',
            scene.sceneName  # 使用场景名称作为文件夹名
        )

        # path = r"C:\Users\lyk\Desktop\zuixinban\mytestdjango_five\scene1"
        # absolute_path = Path(path)
        # 获取绝对路径并打印
        # absolute_path_str = os.path.abspath(scene_folder)
        absolute_path =r"C:\Users\xukz1\Desktop\scene1\scene1"
        absolute_path = Path(absolute_path)
        print(type(absolute_path))
        print(f"场景文件夹绝对路径: {absolute_path}")
        # ====== 新增功能结束 ======

        # 添加成功响应（可选：在响应中包含路径信息）
        return JsonResponse({
            'status': 'success'
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': '无效的JSON格式'
        }, status=400)

    except Exception as e:
        # 记录错误日志
        logger.error(f"启动模拟失败: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'服务器内部错误: {str(e)}'
        }, status=500)








#以下是lykcode

# python manage.py runserver

def getToken(request):
    token = get_token(request)
    return HttpResponse(json.dumps({'token': token}), content_type="application/json,charset=utf-8")


def sendtofrontbysocket(request, time, satellites, links, applications):
    """
    通过 WebSocket 发送消息到前端，消息格式包含时间和卫星数据。
    :param request: HTTP 请求对象
    :param time: 时间值，整数或字符串
    :param satellites: 卫星数据列表，每个卫星是一个包含 id, lat, lon, alt 的字典
    """
    channel_layer = get_channel_layer()

    # 构建消息字典
    message = {
        "type": "satellite_and_link",
        "time": time,
        "satellite": satellites,  # 动态传入卫星数据
        "links": links,
        "applications": applications,
    }

    # 将字典转换为 JSON 字符串
    message_json = json.dumps(message)

    print(f"已发送消息：{message_json}")

    # 发送消息到 WebSocket 组
    async_to_sync(channel_layer.group_send)(
        "test_group",  # 组名
        {
            "type": "chat_message",  # 消息类型
            "message": message_json,  # 动态消息（JSON 格式字符串）
        }
    )


def sendlinkstatetofrontbysocket(request, linkstate):
    """
    通过 WebSocket 发送消息到前端，消息格式包含时间和卫星数据。
    :param request: HTTP 请求对象
    :param time: 时间值，整数或字符串
    :param satellites: 卫星数据列表，每个卫星是一个包含 id, lat, lon, alt 的字典
    """
    channel_layer = get_channel_layer()

    # 构建消息字典
    message = {
        "type": "linkstate",
        "linkstate": linkstate,
    }

    # 将字典转换为 JSON 字符串
    message_json = json.dumps(message)

    print(f"已发送消息：{message_json}")

    # 发送消息到 WebSocket 组
    async_to_sync(channel_layer.group_send)(
        "test_group",  # 组名
        {
            "type": "chat_message",  # 消息类型
            "message": message_json,  # 动态消息（JSON 格式字符串）
        }
    )


def updatelink(request, time, satellites, links):
    """
    通过 WebSocket 发送消息到前端，消息格式包含时间和卫星数据。
    :param request: HTTP 请求对象
    :param time: 时间值，整数或字符串
    :param satellites: 卫星数据列表，每个卫星是一个包含 id, lat, lon, alt 的字典
    """
    channel_layer = get_channel_layer()

    # 构建消息字典
    message = {
        "type": "updatelink",
        "time": time,
        "satellite": satellites,  # 动态传入卫星数据
        "links": links
    }

    # 将字典转换为 JSON 字符串
    message_json = json.dumps(message)

    print(f"已发送消息：{message_json}")

    # 发送消息到 WebSocket 组
    async_to_sync(channel_layer.group_send)(
        "test_group",  # 组名
        {
            "type": "chat_message",  # 消息类型
            "message": message_json,  # 动态消息（JSON 格式字符串）
        }
    )


#以下是lykcode

def test_eci2geodetic(eci_x, eci_y, eci_z, utc):
    lla = pm.eci2geodetic(eci_x, eci_y, eci_z, utc)
    return lla


def sat_init():
    '''
    读取前端生成的txt文件，生成所有卫星对象，将初始化后的卫星对象保存到列表sat_arr中
    ori_time,ecco,argpo,inclo,mo,no_kozai,nodeo
    :param ori_time: 初始时间
    :param ecco: 偏心率
    :param argpo: 近地点辐角
    :param inclo: 轨道倾角
    :param mo: 平近点角
    :param no_kozai: 均运动
    :param nodeo: 升交点赤经
    :return:
    '''
    # 打开文件并逐行读取
    # 打开文件并读取所有行到列表中
    with open(absolute_path / 'orbit.txt', 'r') as file:
        lines = file.readlines()
    # 打印每一行
    for line in lines:  #遍历每一行(一行代表一个卫星)
        input_info = line.split()
        ori_time = datetime(int(input_info[0]), int(input_info[1]), int(input_info[2]), int(input_info[3]),
                            int(input_info[4]), int(input_info[5]))
        SocketView.start_time.append(ori_time)  #将每颗卫星初始时间保存
        jtime_ori = jday(int(input_info[0]), int(input_info[1]), int(input_info[2]), int(input_info[3]),
                         int(input_info[4]), int(input_info[5]))
        epoch = jtime_ori[0] + jtime_ori[1] - 0.5 - 2433281
        ecco = float(input_info[6])
        argpo = float(input_info[7])
        inclo = float(input_info[8])
        mo = float(input_info[9])
        no_kozai = float(input_info[10])
        nodeo = float(input_info[11])
        bstar = 0
        ndot = 0
        nddot = 0
        # 初始化Satrec对象
        satrec = Satrec()
        satrec.sgp4init(
            WGS72,  # 重力模型
            'i',  # 'a' = 旧的AFSPC模式，'i' = 改进模式
            0,  # 卫星编号
            epoch,  # 历元
            bstar,  # 拖曳系数
            ndot,  # 弹道系数
            nddot,  # 均运动二阶导数
            ecco,  # 偏心率
            argpo,  # 近地点辐角
            inclo,  # 轨道倾角
            mo,  # 平近点角
            no_kozai,  # 均运动
            nodeo  # 升交点赤经
        )
        SocketView.sat_arr.append(satrec)


def cal_sat_pos(t):
    '''
    :param t: 给定时间
    :return: 给定时间的经纬高
    '''
    num = 0
    if (num == 0):
        filee = open(absolute_path / 'config.txt', 'w', encoding='utf-8')
    for sat in SocketView.sat_arr:
        # 使用timedelta将秒数转换为时间差
        time_difference = timedelta(seconds=t)
        # 将时间差加到起始日期上
        new_time = SocketView.start_time[num] + time_difference
        jd, fr = jday(new_time.year, new_time.month, new_time.day, new_time.hour, new_time.minute, new_time.second)
        # 计算卫星的位置和速度
        e, r, v = sat.sgp4(jd, fr)
        lla = test_eci2geodetic(r[0] * 1000, r[1] * 1000, r[2] * 1000, new_time)
        # 使用 open 函数打开文件，模式为 'a' 表示追加模式
        # 使用 open 函数打开文件，模式为 'w' 表示写入模式（如果文件不存在则创建）
        if (SocketView.print_state == 1):
            if (num == 0):
                with open(absolute_path / 'config.txt', 'w', encoding='utf-8') as file:
                    file.write(
                        f"UPDATEPLATFORM {num + 1} {t} LAT {int(lla[0])} LON {int(lla[1])} ALT {int(lla[2])} DAMAGESTATE 0\n")
            else:
                with open(absolute_path / 'config.txt', 'a', encoding='utf-8') as file:
                    file.write(
                        f"UPDATEPLATFORM {num + 1} {t} LAT {int(lla[0])} LON {int(lla[1])} ALT {int(lla[2])} DAMAGESTATE 0\n")
        else:  #print_state 打印状态为0：第一次输出
            if (num == 0):
                with open(absolute_path / 'config.txt', 'w', encoding='utf-8') as file:
                    file.write(
                        f"CREATEPLATFORM {num + 1} {t} LAT {int(lla[0])} LON {int(lla[1])} ALT {int(lla[2])} DAMAGESTATE 0 Type 1\n")
            else:
                with open(absolute_path / 'config.txt', 'a', encoding='utf-8') as file:
                    file.write(
                        f"CREATEPLATFORM {num + 1} {t} LAT {int(lla[0])} LON {int(lla[1])} ALT {int(lla[2])} DAMAGESTATE 0 Type 1\n")

        num += 1  # 每颗卫星对应各自的初始时间 并且num=0 表示开始写一个新的txt文件，覆盖原有的内容。。
    SocketView.print_state = 1



class SocketView(View):

    carStart = 0
    link_x = 1
    cari = 0
    car_info1 = []
    car_info2 = []
    car_info3 = []
    car_info4 = []
    ddk1 = 1
    i = 0
    ddk2 = 1
    normal_node = []
    client_socket = None  # 类变量，所有实例共享

    config_file = absolute_path / 'config.txt'
    initial_file = absolute_path / 'initial.txt'
    exata_response = ""  # 存储从 Exata 接收的响应
    handleMessage_queue = []  # 存储处理的消息
    data = ""  # 存储发送的消息的头部和内容
    timeToSend = 5
    send_queue = []  # 存储所有需要发送的消息
    receive_queue = []  # 存储接受到的信息
    simulation_running = False  # 用于判断仿真是否正在运行
    message_indexStep = 0  # 当前发送的消息索引
    message_indexContinue = 0  # 当前发送的消息索引
    initialmessage = "01 01 00 00 00 00 00 12 00 00 00 00 CD 00 00 00 09 01"
    pausemessage = "02 00 00 00 00 00 00 08"
    startmessage = "03 00 00 00 00 00 00 08"
    initial_k = 1
    over_controlmessage = ""
    controlmessage = ""
    isPaused = False
    isStep = False
    hasbeenstep = False
    isPaused_lock = Lock()
    isStep_lock = Lock()
    interval = 0
    now_time = 0
    final = 0
    continue_send = True
    frontshowisover = True
    exataisidle = False
    satellites = []
    # 以下参数和sgp4相关
    sat_arr = []  # 卫星列表
    start_time = []  # 卫星初始时间
    print_state = 0  # 打印状态：0 表示第一次，1表示非第一次
    links = []
    x = 0
    gene_read_send_thread = None
    handle_thread = None
    receive_thread = None
    stop_receive_message = 0
    stop_handle_message = 0
    stop_send_message = 0
    ip_list = []
    link_state = []
    time_link_state = []  #包含上个时间片内的全部链路数据包消息
    update_links = []
    json_list = []
    message_prefixes = ['16000000000000', '07000000000000', '000000000000000a', ]

    @staticmethod
    def set_isPaused(value):
        with SocketView.isPaused_lock:
            SocketView.isPaused = value

    @staticmethod
    def get_isPaused():
        with SocketView.isPaused_lock:
            return SocketView.isPaused

    @staticmethod
    def set_isStep(value):
        with SocketView.isStep_lock:
            SocketView.isStep = value

    @staticmethod
    def get_isStep():
        with SocketView.isStep_lock:
            return SocketView.isStep

    def read_node_file(self) -> dict:
        """
        读取 node.txt，并在当前仿真时刻 SocketView.now_time 下：
        • 为每个节点选择唯一一行（规则见函数说明），
        • 写入 config_no_move.txt，
        • 返回 {"node": SocketView.normal_node}。
        """
        # 清空旧数据
        SocketView.normal_node = []

        # 收集各节点的候选行
        zero_rows: dict[str, dict] = {}  # time == 0 行
        future_rows: dict[str, dict] = {}  # time > now_time 且最大的那行

        with open(absolute_path / "node.txt", "r", encoding="utf-8") as f:
            for raw in f:
                if not raw.strip():
                    continue  # 跳过空行

                parts = raw.split()
                node_id = parts[0]
                t = int(parts[1])
                lat, lon, alt = map(float, parts[2:5])
                node_type = parts[5]
                name = " ".join(parts[6:])  # 节点名称可能含空格

                info = {
                    "satellite_id": f"satellite_{node_id}",
                    "time": t,
                    "lat": str(lat),
                    "lon": str(lon),
                    "alt": str(alt),
                    "type": node_type,
                    "name": name
                }

                if t == 0:
                    # 只第一次记录，同一节点假设最多一行 t==0
                    zero_rows.setdefault(node_id, info)
                elif t <= SocketView.now_time:
                    # 保留 time 最大的一行
                    if t > future_rows.get(node_id, {}).get("time", -1):
                        future_rows[node_id] = info

        # 为每个节点选出最终行：优先 future_rows，其次 zero_rows
        final_nodes: dict[str, dict] = zero_rows.copy()
        final_nodes.update(future_rows)  # future_rows 覆盖同 id 的 zero_rows

        # 写文件 & 填充 SocketView.normal_node（按 id 升序，便于核对）
        with open(absolute_path / "config_no_move.txt", "w", encoding="utf-8") as cfg:
            for info in sorted(final_nodes.values(),
                               key=lambda x: int(x["satellite_id"].split("_")[1])):
                cfg.write(
                    f"CREATEPLATFORM {info['satellite_id'].split('_')[1]} 0 "
                    f"LAT {int(float(info['lat']))} "
                    f"LON {int(float(info['lon']))} "
                    f"ALT {int(float(info['alt']))} "
                    f"DAMAGESTATE 0 Type 1\n"
                )
                SocketView.normal_node.append(info)

        return {"node": SocketView.normal_node}


    def connect_to_server(self):

        if SocketView.client_socket is not None:
            SocketView.client_socket.close()
            SocketView.client_socket = None
            time.sleep(2)
        if SocketView.client_socket is None:  # 仅在未连接时创建连接

            server_address = '127.0.0.1'
            server_port = 8005
            SocketView.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            for attempt in range(5):
                try:
                    SocketView.client_socket.connect((server_address, server_port))
                    SocketView.receive_thread = threading.Thread(target=self.receive_message,
                                                                 daemon=True).start()  # 不要加括号
                    SocketView.handle_thread = threading.Thread(target=self.handle_message,
                                                                daemon=True).start()  # 不要加括号
                    print(f"成功连接: {SocketView.client_socket}")
                    return {"status": "成功连接"}
                except socket.error as e:
                    return {"status": f"连接失败: {e}"}
        else:
            SocketView.client_socket.close()
            SocketView.client_socket = None
            return {"status": "上次连接未断开"}

    def handle_message(self):
        while True:
            if SocketView.stop_handle_message == 1:
                break
            if SocketView.receive_queue:
                SocketView.handleMessage = SocketView.receive_queue[0]

                if SocketView.handleMessage.startswith('16'):
                    # 从第21位开始读取，即从索引20开始
                    sub_string = SocketView.handleMessage[20:]

                    # 打印从第21位开始的子字符串
                    # print("Sub-string from the 21st position:", sub_string)

                    original_string = bytes.fromhex(sub_string)
                    # 使用decode()方法将字节串转换为字符串
                    str_data = original_string.decode('utf-8')
                    split_values = str_data.split()
                    # print(f"str_data is :{str_data}")
                    if split_values[5] == "0":
                        SocketView.link_state.append({
                            "source_satellite_id": split_values[0],
                            "destination_satellite_id": split_values[1],
                            "source_satellite_interface": split_values[2],
                            "destination_satellite_interface": split_values[3],
                            "time": split_values[4],
                            "type": "network_layer"
                        })
                    else:
                        SocketView.link_state.append({
                            "source_satellite_id": split_values[0],
                            "destination_satellite_id": split_values[1],
                            "source_satellite_interface": split_values[2],
                            "destination_satellite_interface": split_values[3],
                            "time": split_values[4],
                            "type": "application_layer",
                            "app_id": split_values[6],
                            "app_source_id": split_values[7],
                            "app_des_id": split_values[8],

                        })
                    # sendlinkstatetofrontbysocket(self, SocketView.link_state[-1])

                    # print(f"恢复的数字是{str_data}")
                if not SocketView.get_isStep():
                    # SocketView.handleMessage = SocketView.receive_queue[0]

                    if SocketView.handleMessage.startswith('07') and not SocketView.get_isPaused():
                        self.update_link_data()
                        SocketView.exataisidle = True
                        # SocketView.set_isPaused(False)
                        print(f"SocketView.exataisidle 已经被设为true {SocketView.exataisidle}")
                        SocketView.receive_queue.remove(SocketView.receive_queue[0])
                        # SocketView.handleMessage_queue.append(SocketView.handleMessage)
                    elif not SocketView.handleMessage.startswith('07'):
                        SocketView.receive_queue.remove(SocketView.receive_queue[0])
                        # SocketView.handleMessage_queue.append(SocketView.handleMessage)
                if SocketView.get_isStep():
                    # print("步进模式")
                    SocketView.handleMessage = SocketView.receive_queue[0]
                    if SocketView.handleMessage.startswith('07') and not SocketView.get_isPaused():
                        print(f"SocketView.exataisidle 步进中已经被设为true {SocketView.exataisidle}")
                        if SocketView.hasbeenstep:
                            self.pause_simulation()
                        else:
                            self.update_link_data()
                            SocketView.simulation_running = True
                            SocketView.receive_queue.remove(SocketView.receive_queue[0])
                            # SocketView.handleMessage_queue.append(SocketView.handleMessage)
                            SocketView.exataisidle = True
                        SocketView.hasbeenstep = True
                    elif not SocketView.handleMessage.startswith('07'):
                        SocketView.receive_queue.remove(SocketView.receive_queue[0])
                        # SocketView.handleMessage_queue.append(SocketView.handleMessage)

                # print(f"已处理接收消息队列：{SocketView.handleMessage_queue}")
                # return SocketView.handleMessage
            # 当仿真结束时，关闭线程
            # time.sleep(1)

    def update_link_data(self):
        if SocketView.car_info1:
            satellite_id_to_replace = SocketView.car_info1["satellite_id"]
            found = False

            for idx, satellite in enumerate(SocketView.satellites):
                if satellite["satellite_id"] == satellite_id_to_replace:
                    # 如果找到了，替换掉这个对象
                    SocketView.satellites[idx] = SocketView.car_info1
                    found = True
                    break  # 找到后直接退出循环

            # 如果没有找到相同satellite_id的对象
            if not found:
                SocketView.satellites.append(SocketView.car_info1)
                print("not found\n")
            else:
                print("found\n")

        SocketView.update_links = []
        SocketView.update_links = [SocketView() for _ in
                                   range(len(StaticDynamicLinkCalculator.static_link))]

        for idx, record in enumerate(StaticDynamicLinkCalculator.static_link):
            link_id, time, node1, node2, interface1, interface2, ip1, ip2, link_type = record

            # 赋值给 update_links 中的对应对象
            update_link = SocketView.update_links[idx]
            update_link.link_id = link_id
            update_link.time = time
            update_link.node1 = node1
            update_link.node2 = node2
            update_link.interface1 = interface1
            update_link.interface2 = interface2
            update_link.ip1 = ip1
            update_link.ip2 = ip2
            update_link.link_type = link_type
            # 设置第 9 和第 10 个属性
            update_link.flag1 = 0
            update_link.flag2 = 0
            update_link.active_time1 = 0
            update_link.active_time2 = 0
            update_link.application_from_direction1 = 0
            update_link.application_from_direction2 = 0
            update_link.app_id1 = None
            update_link.app_source_id1 = None
            update_link.app_des_id1 = None
            update_link.app_id2 = None
            update_link.app_source_id2 = None
            update_link.app_des_id2 = None
            update_link.app_1 = None
            update_link.app_2 = None
        # 遍历 link_state 和 update_links，进行匹配并更新 update_link 对象
        applications = []
        for link_state_obj in SocketView.link_state:
            # print(f"更新对象1")
            if link_state_obj["type"] == "network_layer":
                source_satellite_id = int(link_state_obj["source_satellite_id"])
                destination_satellite_id = int(link_state_obj["destination_satellite_id"])
                source_satellite_interface = int(link_state_obj["source_satellite_interface"])
                destination_satellite_interface = int(link_state_obj["destination_satellite_interface"])
                time = int(link_state_obj["time"])
                # print(f"更新对象2")
                # 遍历 update_links，检查是否有匹配的 link
                for update_link in SocketView.update_links:
                    node1 = int(update_link.node1)
                    node2 = int(update_link.node2)
                    interface1 = int(update_link.interface1)
                    interface2 = int(update_link.interface2)
                    # print(
                    #     f"link_state -> source_satellite_id: {source_satellite_id}, destination_satellite_id: {destination_satellite_id}, "
                    #     f"source_satellite_interface: {source_satellite_interface}, destination_satellite_interface: {destination_satellite_interface}")
                    # print(f"update_link -> node1: {node1}, node2: {node2}, "
                    #       f"interface1: {interface1}, interface2: {interface2}")

                    # 进行匹配，第一个条件：从 source 到 destination
                    if (node1 == source_satellite_id and
                            node2 == destination_satellite_id and
                            interface1 == source_satellite_interface and
                            interface2 == destination_satellite_interface):
                        # 如果匹配，更新 update_link 的 flag1 和 active_time1
                        update_link.flag1 = 1
                        update_link.active_time1 = time
                        # print(f"更新对象: {update_link}, active_time1 设置为: {time}")

                    # 第二个条件：从 destination 到 source
                    elif (node1 == destination_satellite_id and
                          node2 == source_satellite_id and
                          interface1 == destination_satellite_interface and
                          interface2 == source_satellite_interface):
                        # 如果匹配，更新 update_link 的 flag2 和 active_time2
                        update_link.flag2 = 1
                        update_link.active_time2 = time
                        # print(f"更新对象: {update_link}, active_time2 设置为: {time}")
            if link_state_obj["type"] == "application_layer":
                source_satellite_id = int(link_state_obj["source_satellite_id"])
                destination_satellite_id = int(link_state_obj["destination_satellite_id"])
                source_satellite_interface = int(link_state_obj["source_satellite_interface"])
                destination_satellite_interface = int(link_state_obj["destination_satellite_interface"])
                time = int(link_state_obj["time"])

                # print(f"更新对象2")
                # 遍历 update_links，检查是否有匹配的 link
                for update_link in SocketView.update_links:
                    node1 = int(update_link.node1)
                    node2 = int(update_link.node2)
                    interface1 = int(update_link.interface1)
                    interface2 = int(update_link.interface2)

                    # 检查是否匹配第一个方向的条件
                    if (node1 == source_satellite_id and
                            node2 == destination_satellite_id and
                            interface1 == source_satellite_interface and
                            interface2 == destination_satellite_interface):

                        update_link.application_from_direction1 += 1

                        # 合并 app_id1, app_source_id1, app_des_id1 为 app_1
                        new_app_id = str(link_state_obj["app_id"])
                        new_app_source_id = str(link_state_obj["app_source_id"])
                        new_app_des_id = str(link_state_obj["app_des_id"])

                        # 合并这些值为一个 JSON 对象
                        app_1_info = {
                            "app_id": new_app_id + new_app_source_id,
                            "app_source_id": new_app_source_id,
                            "app_des_id": new_app_des_id
                        }

                        # 如果 app_1 已经存在，检查是否已包含相同的对象
                        if update_link.app_1:
                            # 使用 list comprehension 判断是否已经存在相同的对象
                            if not any(
                                    app["app_id"] == app_1_info["app_id"] and
                                    app["app_source_id"] == app_1_info["app_source_id"] and
                                    app["app_des_id"] == app_1_info["app_des_id"]
                                    for app in update_link.app_1):
                                update_link.app_1.append(app_1_info)
                        else:
                            update_link.app_1 = [app_1_info]  # 如果没有旧值，初始化为一个包含当前合并信息的列表

                    # 检查是否匹配第二个方向的条件
                    if (node1 == destination_satellite_id and
                            node2 == source_satellite_id and
                            interface1 == destination_satellite_interface and
                            interface2 == source_satellite_interface):

                        update_link.application_from_direction2 += 1

                        # 合并 app_id2, app_source_id2, app_des_id2 为 app_2
                        new_app_id = str(link_state_obj["app_id"])
                        new_app_source_id = str(link_state_obj["app_source_id"])
                        new_app_des_id = str(link_state_obj["app_des_id"])

                        # 合并这些值为一个 JSON 对象
                        app_2_info = {
                            "app_id": new_app_id + new_app_source_id,
                            "app_source_id": new_app_source_id,
                            "app_des_id": new_app_des_id
                        }

                        # 如果 app_2 已经存在，检查是否已包含相同的对象
                        if update_link.app_2:
                            # 使用 list comprehension 判断是否已经存在相同的对象
                            if not any(
                                    app["app_id"] == app_2_info["app_id"] and
                                    app["app_source_id"] == app_2_info["app_source_id"] and
                                    app["app_des_id"] == app_2_info["app_des_id"]
                                    for app in update_link.app_2):
                                update_link.app_2.append(app_2_info)
                        else:
                            update_link.app_2 = [app_2_info]  # 如果没有旧值，初始化为一个包含当前合并信息的列表

                    # print(
                    #     f"link_state -> source_satellite_id: {source_satellite_id}, destination_satellite_id: {destination_satellite_id}, "
                    #     f"source_satellite_interface: {source_satellite_interface}, destination_satellite_interface: {destination_satellite_interface}")
                    # print(f"update_link -> node1: {node1}, node2: {node2}, "
                    #       f"interface1: {interface1}, interface2: {interface2}")

                    # 进行匹配，第一个条件：从 source 到 destination
                    if (node1 == source_satellite_id and
                        node2 == destination_satellite_id and
                        interface1 == source_satellite_interface and
                        interface2 == destination_satellite_interface) or (node1 == destination_satellite_id and
                                                                           node2 == source_satellite_id and
                                                                           interface1 == destination_satellite_interface and
                                                                           interface2 == source_satellite_interface):
                        # 如果匹配，更新 update_link 的 flag1 和 active_time1
                        update_link.flag1 = 1
                        update_link.active_time1 = time
                        update_link.flag2 = 1
                        update_link.active_time2 = time
                        # print(f"更新对象: {update_link}, active_time1 设置为: {time}")
        SocketView.json_list = []

        for idx, update_link in enumerate(SocketView.update_links):
            # 提取每个对象的属性
            link_id = update_link.link_id
            time = update_link.time
            node1 = update_link.node1
            node2 = update_link.node2
            interface1 = update_link.interface1
            interface2 = update_link.interface2
            ip1 = update_link.ip1
            ip2 = update_link.ip2
            link_type = int(update_link.link_type)
            # 额外设置的标志属性
            flag1 = update_link.flag1
            flag2 = update_link.flag2
            active_time1 = update_link.active_time1
            active_time2 = update_link.active_time2

            source_satellite = None
            target_satellite = None
            link_sat = []
            for satellite in SocketView.satellites:
                if satellite["satellite_id"] == "satellite_" + str(node1):
                    source_satellite = satellite
                    break
            for satellite in SocketView.satellites:
                if satellite["satellite_id"] == "satellite_" + str(node2):
                    target_satellite = satellite
                    break
            if source_satellite is not None:
                source_satellite_info11 = {
                    "satellite_id": source_satellite["satellite_id"],
                    "lat": source_satellite["lat"],
                    "lon": source_satellite["lon"],
                    "alt": source_satellite["alt"]
                }
                link_sat.append(source_satellite_info11)
            else:
                print("error happened in source")
            if target_satellite is not None:
                target_satellite_info11 = {
                    "satellite_id": target_satellite["satellite_id"],
                    "lat": target_satellite["lat"],
                    "lon": target_satellite["lon"],
                    "alt": target_satellite["alt"]
                }
                link_sat.append(target_satellite_info11)
            else:
                print("error happened in dest")
            # link_sat.append(source_satellite)
            # link_sat.append(target_satellite)
            linkflag = 0
            if flag1 == 0 and flag2 == 0:
                linkflag = 0
            elif flag1 == 1 and flag2 == 0:
                linkflag = 1
            elif flag1 == 0 and flag2 == 1:
                linkflag = 2
            elif flag1 == 1 and flag2 == 1:
                linkflag = 3
            if link_type == 1:
                linkflag = 5
            if link_type == 2:
                linkflag = 4
            record_dict = {
                "link_id": "link_" + str(link_id),
                "link_time": time,
                "link_sat": link_sat,
                "link_flag": linkflag,

            }
            # 将字典转换为 JSON 格式的字符串
            SocketView.json_list.append(record_dict)
            record_dict1 = {
                "application_sat": link_sat,
                "application_from_direction1": update_link.application_from_direction1,
                "application_from_direction2": update_link.application_from_direction2,
                "link_flag": linkflag,
                "app_1": update_link.app_1,
                "app_2": update_link.app_2,

            }
            applications.append(record_dict1)

        if int(SocketView.now_time) == 30000000000:  #原来是1260lyk
            SocketView.carStart = 1
        if SocketView.carStart == 1:
            if SocketView.cari % 2 == 1:
                lat1 = 42
                lon1 = 96
                SocketView.car_info1 = {
                    "satellite_id": "satellite_" + "4",
                    "lat": str(lat1),
                    "lon": str(lon1),
                    "alt": "500",
                    "type": "airplane",
                    "name": "一级节点1",
                    "error_interface": None,
                    "print_link": None,
                }
                SocketView.cari = SocketView.cari + 1
            if SocketView.cari % 2 == 0:
                lat1 = 43
                lon1 = 97
                SocketView.car_info1 = {
                    "satellite_id": "satellite_" + "4",
                    "lat": str(lat1),
                    "lon": str(lon1),
                    "alt": "0",
                    "type": "airplane",
                    "name": "一级节点1",
                    "error_interface": None,
                    "print_link": None,
                }
                SocketView.cari = SocketView.cari + 1

        for normal_item in SocketView.normal_node:
            normal_satellite_id = normal_item["satellite_id"]  # 获取 normal_node 中项的 satellite_id
            normal_property = normal_item["type"]  # 获取 normal_node 中的第五个属性（索引从 0 开始，所以第五个属性是索引 4）
            normal_name = normal_item["name"]
            # 遍历 satellites 列表，查找具有相同 satellite_id 的项
            for satellite in SocketView.satellites:
                if satellite["satellite_id"] == normal_satellite_id:
                    # 如果 satellite_id 匹配，将 normal_node 中的第五个属性赋值给 satellites 中对应项
                    satellite["type"] = normal_property  # 在 satellites 中新增一个属性存储该值
                    satellite["name"] = normal_name
                    break  # 找到匹配项后跳出内层循环
        # print(f"SocketView.normal_node is {SocketView.normal_node}")
        # print(f"SocketView.satellites is {SocketView.satellites}")
        SocketView.send_queue = []
        SocketView.update_satellite_error_interface(self, absolute_path / "fault.txt")
        SocketView.update_satellite_print_link(self, SocketView.update_links, SocketView.satellites)
        sendtofrontbysocket(self, int(SocketView.now_time) - int(SocketView.interval), SocketView.satellites,
                            SocketView.json_list, applications)
        SocketView.link_state = []

    def update_satellite_print_link(self, update_links, satellites):
        # 遍历update_links中的每个update_link对象
        for update_link in update_links:
            # 根据node1和node2查找对应的name
            name1 = None
            name2 = None

            # 查找对应的satellite name
            for satellite in satellites:
                satellite_id = int(satellite["satellite_id"].split('_')[1])
                if satellite_id == update_link.node1:
                    name1 = satellite["name"]
                if satellite_id == update_link.node2:
                    name2 = satellite["name"]

            # 如果找到了node1和node2对应的name
            if name1 and name2:
                # 根据link_type设置link名称
                if update_link.link_type == "1":
                    link = "微波网络"
                elif update_link.link_type == "2":
                    link = "地面光纤"
                else:
                    link = "其他"

                # 检查是否存在nodeError
                nodeError = False
                # 遍历satellites，检查name1对应的卫星的error_interface
                for satellite in satellites:
                    if satellite["name"] == name1:
                        # 获取error_interface并确保它是一个列表
                        error_interfaces = satellite.get("error_interface")
                        if error_interfaces is None:
                            error_interfaces = []  # 如果是None，设为空列表
                        # 遍历error_interface中的每个对象，检查interface1是否存在
                        for error in error_interfaces:
                            if "interface_id" in error and int(error["interface_id"]) == update_link.interface1:
                                nodeError = True
                                break
                        break  # 找到对应的name1之后可以提前退出

                # 拼接name1, name2, interface1, interface2, link
                link_info = {
                    "name1": name1,
                    "name2": name2,
                    "interface1": update_link.interface1,
                    "interface2": update_link.interface2,
                    "link": link,
                    "nodeError": nodeError,  # 根据逻辑设置nodeError
                }

                # 如果节点已有print_link属性且它是非空的，拼接新的信息，换行符分开
                for satellite in satellites:
                    satellite_id = int(satellite["satellite_id"].split('_')[1])
                    if satellite_id == update_link.node1:
                        if "print_link" in satellite and satellite["print_link"]:
                            satellite["print_link"].append(link_info)
                        else:
                            satellite["print_link"] = [link_info]

                nodeError = False
                # 遍历satellites，检查name1对应的卫星的error_interface
                for satellite in satellites:
                    if satellite["name"] == name2:
                        # 获取error_interface并确保它是一个列表
                        error_interfaces = satellite.get("error_interface")
                        if error_interfaces is None:
                            error_interfaces = []  # 如果是None，设为空列表
                        # 遍历error_interface中的每个对象，检查interface1是否存在
                        for error in error_interfaces:
                            if "interface_id" in error and int(error["interface_id"]) == update_link.interface2:
                                nodeError = True
                                break
                        break  # 找到对应的name1之后可以提前退出

                # 拼接name1, name2, interface1, interface2, link
                link_info = {
                    "name1": name2,
                    "name2": name1,
                    "interface1": update_link.interface2,
                    "interface2": update_link.interface1,
                    "link": link,
                    "nodeError": nodeError,  # 根据逻辑设置nodeError
                }

                # 如果节点已有print_link属性且它是非空的，拼接新的信息，换行符分开
                for satellite in satellites:
                    satellite_id = int(satellite["satellite_id"].split('_')[1])
                    if satellite_id == update_link.node2:
                        if "print_link" in satellite and satellite["print_link"]:
                            satellite["print_link"].append(link_info)
                        else:
                            satellite["print_link"] = [link_info]

    def update_satellite_error_interface(self, fault_file_path):
        # 获取当前时间
        current_time = int(SocketView.now_time)  # 获取当前时间的时间戳

        # 读取fault.txt
        with open(fault_file_path, "r") as file:
            for line in file:
                # 解析每一行
                parts = line.split()
                node_id = int(parts[0])  # 节点ID
                interface_id = int(parts[1])  # 接口ID
                start_time = int(parts[2])  # 开始时间
                end_time = int(parts[3])  # 结束时间

                # 检查当前时间是否在这个时间段内
                if start_time <= current_time <= end_time:
                    # 找到对应的节点，更新error_interface
                    for satellite in SocketView.satellites:
                        satellite_id = int(satellite["satellite_id"].split('_')[1])
                        if satellite_id == node_id:
                            # 如果error_interface是None，初始化为一个空列表
                            if satellite["error_interface"] is None:
                                satellite["error_interface"] = []

                            # 将新的接口ID作为一个JSON对象添加到列表中
                            interface_info = {"interface_id": interface_id}
                            satellite["error_interface"].append(interface_info)

    def receive_message(self):
        while True:
            try:
                if SocketView.stop_receive_message == 1:
                    break
                response_data = SocketView.client_socket.recv(1000000)  # 假设响应不超过 1024 字节
                SocketView.exata_response = binascii.hexlify(response_data).decode('utf-8')  # 转换为16进制字符串
                # 打印 response_data (字节串)，以十六进制表示
                while SocketView.exata_response:
                    for prefix in SocketView.message_prefixes:
                        if SocketView.exata_response.startswith(prefix):
                            # 提取长度字段，假设长度字段位于前缀之后的第16到19个字符（即，消息总长度包含前缀和内容）
                            length_field = SocketView.exata_response[14:16]  # 取长度字段
                            message_length = int(length_field, 16)  # 将十六进制字符串转换为整数

                            # 由于长度字段包含了前缀长度，实际内容长度应该是：message_length - 前缀长度
                            # 每条消息都包含前缀，因此消息内容的长度是 message_length - len(prefix)
                            content_length = message_length - len(prefix)

                            # 提取完整消息：前缀 + 内容
                            message = SocketView.exata_response[:message_length * 2]  # 这里将整个消息作为一条完整消息，包括前缀和内容

                            # 将完整消息添加到消息队列
                            SocketView.receive_queue.append(message)

                            # 移除已经处理过的消息部分
                            SocketView.exata_response = SocketView.exata_response[message_length * 2:]
                            break
                    else:
                        print("Error: Received data doesn't start with a valid prefix!")
                        break
                if SocketView.exata_response:
                    SocketView.receive_queue.append(SocketView.exata_response)
                    # print(f"response_data (raw): {response_data}")
                    # 打印 SocketView.exata_response
                    # print(f"SocketView.exata_response: {SocketView.exata_response}")
                    print(f"未处理接收消息队列：{SocketView.receive_queue}")
            except socket.error as e:
                print(f"接收失败: {e}")
                break

    @csrf_exempt
    def post(self, request):
        global absolute_path
        content_type = request.META.get('CONTENT_TYPE')
        if content_type == 'application/json':
            data = json.loads(request.body)
            if 'connect' in data:

                # 在仿真开始时，把消息队列设置为空
                # sendtofrontbysocket(request, "web socket 已经建立", "", "")
                SocketView.carStart = 0
                SocketView.cari = 0
                SocketView.car_info1 = []
                SocketView.car_info2 = []
                SocketView.car_info3 = []
                SocketView.car_info4 = []
                SocketView.initial_k = 1
                SocketView.i = 0
                SocketView.ddk1 = 1
                SocketView.ddk2 = 1
                SocketView.send_queue = []
                SocketView.receive_queue = []
                SocketView.handleMessage_queue = []
                SocketView.sat_arr = []
                SocketView.start_time = []
                SocketView.print_state = 0
                SocketView.stop_receive_message = 0
                SocketView.stop_send_message = 0
                SocketView.stop_handle_message = 0
                SocketView.ip_list = []
                SocketView.link_x = 1
                sat_init()  # 初始化各个卫星
                print(f"chushihua场景文件夹绝对路径: {absolute_path}")
                exata = ExataSimulator(

                    working_directory=absolute_path,
                    executable_path=r"D:\Program Files\Scalable\exata\7.3.0.0\bin\exata.exe",
                    config_file="cuixinbin.config",
                )
                exata.stop_simulation()
                #
                exata.run_simulation()
                # time.sleep(3)
                x = self.connect_to_server()
                print(f"连接中")
                SocketView.simulation_running = True
                SocketView.message_indexStep = 0  # 当前发送的消息索引
                SocketView.message_indexContinue = 0  # 当前发送的消息索引
                SocketView.send_start_message(self)
                SocketView.send_next_message(self)
                return JsonResponse(x)
            # elif 'sendsimulationmessage' in data:
            #     SocketView.now_time = 0
            #     SocketView.continue_send = True
            #     SocketView.exataisidle = False
            #     SocketView.gene_read_send_thread = threading.Thread(target=self.gene_read_send_message,
            #                                                         daemon=True).start()  # 不要加括号
            #     return JsonResponse({"status": "所有消息已发送完毕"})

            elif 'sendsimulationmessage' in data:
                current_path = absolute_path  # 捕获当前路径值
                SocketView.now_time = 0
                SocketView.continue_send = True
                SocketView.exataisidle = False
                # 将路径作为参数传递
                SocketView.gene_read_send_thread = threading.Thread(
                    target=self.gene_read_send_message,
                    args=(current_path,),  # 添加路径参数
                    daemon=True
                ).start()
                return JsonResponse({"status": "所有消息已发送完毕"})

            elif 'pausesimulation' in data:

                y = self.pause_simulation()
                return JsonResponse(y)
            elif 'continuesimulation' in data:

                y = self.continue_simulation()
                return JsonResponse(y)
            elif 'stepsimulation' in data:

                y = self.step_simulation()
                return JsonResponse(y)
            elif 'stopsimulation' in data:
                subprocess.Popen(['daphne', '-b', '0.0.0.0', '-p', '8001', 'mytest.asgi:application'])
                y = self.stop_simulation()

                return JsonResponse(y)
            # elif 'getHandleMessage' in data:
            #     if SocketView.handleMessage_queue:
            #         response = SocketView.handleMessage_queue[0]
            #         SocketView.handleMessage_queue.remove(SocketView.handleMessage_queue[0])
            #         return JsonResponse({"exata_response": f"收到处理后的消息:{response}"})
            #     else:
            #         return JsonResponse({"exata_response": "已发送全部消息"})

    @csrf_exempt
    def stop_simulation(self):

        # self.exata.stop_simulation()

        SocketView.stop_receive_message = 1
        SocketView.stop_handle_message = 1
        SocketView.stop_send_message = 1

        SocketView.exata_response = ""
        SocketView.handleMessage_queue = []
        SocketView.data = ""
        SocketView.send_queue = []
        SocketView.receive_queue = []
        SocketView.simulation_running = False
        SocketView.message_indexStep = 0
        SocketView.message_indexContinue = 0
        SocketView.over_controlmessage = ""
        SocketView.controlmessage = ""
        SocketView.isPaused = False
        SocketView.isStep = False
        SocketView.hasbeenstep = False
        SocketView.isPaused_lock = Lock()
        SocketView.isStep_lock = Lock()
        SocketView.now_time = 0
        SocketView.continue_send = True
        SocketView.frontshowisover = True
        SocketView.exataisidle = False
        SocketView.satellites = []
        SocketView.sat_arr = []
        SocketView.start_time = []
        SocketView.print_state = 0
        SocketView.links = []
        SocketView.x = 0
        # pid = get_daphne_pid_windows()
        #
        # if pid:
        #     # 如果有运行中的进程，先停止
        #     from runDaphne import stop_daphne_windows
        #     stop_daphne_windows(pid)
        #     from runDaphne import start_daphne
        #     start_daphne()

        # 启动 Daphne 服务

        return {"status": "停止仿真"}  # 返回状态

    def gene_read_send_message(self, current_path):
        # 因为原来文件来自于配置前端，其中保存一些固定配置，所以先读一些参数
        config_file = current_path / 'config.txt'
        initial_file = current_path / 'initial.txt'
        self.read_initial_config(initial_file)
        print(f"interval is {SocketView.interval},finaltime is {SocketView.final}")
        cal_sat_pos(SocketView.now_time)
        SocketView.read_node_file(self)
        calculator = StaticDynamicLinkCalculator(
            input_filename=current_path / 'link.txt',
            config_filename=current_path / 'config.txt',
            output_filename=current_path / 'config.txt',
        )
        calculator.append_orientation_to_file(SocketView.now_time, SocketView.now_time + int(SocketView.interval))
        self.read_message_file(current_path)  # 读取消息文件并初始化队列
        # 1表示生成初始化消息
        response = self.send_next_message()
        # print("我运行到while之前啦")
        while True:
            if SocketView.stop_send_message == 1:
                break
            # print("我运行到while啦")
            if not SocketView.continue_send:
                break
            if SocketView.frontshowisover and SocketView.exataisidle:
                # 如果单次消息已经发送，并且仿真还没结束，并且收到了idle消息，（收到了前端的相应），则启动下一次发送
                # print("我运行到if啦")
                SocketView.exataisidle = False
                # self.gene_message(0)111
                cal_sat_pos(SocketView.now_time)
                calculator.append_orientation_to_file(SocketView.now_time,
                                                      SocketView.now_time + int(SocketView.interval))
                SocketView.read_node_file(self) #每次都会读取节点的信息
                self.read_message_file(current_path)  # 读取消息文件并初始化队列
                response = self.send_next_message()

    def read_initial_config(self,initial_file):
        global absolute_path
        try:
            with open(initial_file, 'r') as file:
                print("intial absolute path" + str(initial_file))
                lines = file.readlines()
                SocketView.send_queue = []
                for line in lines:
                    if not line.strip():
                        continue
                    # 先去除行首尾的空白字符，然后按照空格分隔
                    command_parts = line.strip().split()
                    # 取出第一个部分（命令）
                    command = command_parts[0]
                    if command == 'INTERVAL':
                        SocketView.interval = command_parts[1]
                        print("intinalintinalintinalintinalintinal"+SocketView.interval)
                    if command == 'FINAL':
                        SocketView.final = command_parts[1]


        except Exception as e:
            print(f"读取消息文件失败: {e}")

    def float_to_hex(self, float_num):
        byte_data = struct.pack('>d', float(float_num))  # 大端字节序
        hex_float_num = ' '.join(f"{byte:02X}" for byte in byte_data)
        encoded_float_num = bytes.fromhex(hex_float_num)
        # print(f"Byte data in hex: {hex_float_num}")
        # x = encoded_float_num.hex()
        # print(f"Byte data in hex: {x}")
        return hex_float_num

    def int_to_hex(self, int_num, bytenum):
        hex_int_num = int(int_num).to_bytes(bytenum).hex()
        # print(f"platform_type is {hex_int_num}")
        return hex_int_num

    def string_to_hex(self, string):
        byte_data = string.encode('utf-8')
        hex_string = ''.join(f"{byte:02X}" for byte in byte_data)
        hex_len = int(len(string)).to_bytes(2).hex()
        # print(f"hex_len is {hex_len}")
        # print(f"hex_string is {hex_string}")
        full_hex_string = hex_len + hex_string

        return full_hex_string

    def add_message_header(self, input_value, hex_string, command, optionnum):
        # 第一个 16 进制数是函数输入的 input_value
        byte1 = input_value
        # 第二个字节固定为 02
        byte2 = optionnum
        otherLength = 0
        # 第三个和第四个字节固定为 00
        byte3 = 0x00
        byte4 = 0x00
        if command == 'CREATEPLATFORM':
            otherLength = 58
        if command == 'UPDATEPLATFORM':
            otherLength = 65
        if command == 'Write':
            otherLength = 9

        string_length = (len(hex_string) // 2) + otherLength

        # 获取 input_string 的长度，并将其作为一个 int 数值

        # 将字符串长度转换为 4 字节的十六进制表示
        # 使用 `format` 以确保是四字节十六进制数，不足部分用零填充
        hex_length = format(string_length, '08X')  # 以 8 位十六进制表示

        # 拼接所有字节，前四个字节固定，最后四个字节为字符串长度的十六进制
        hex_stream = f"{byte1:02X}{byte2:02X}{byte3:02X}{byte4:02X}{hex_length}"

        return hex_stream

    # 示例使用
    def add_option_header(self, option_type, option):
        hex_option = option_type
        if option_type == 2:
            hex_option = SocketView.float_to_hex(self, option)
        elif option_type == 4:
            hex_option = SocketView.int_to_hex(self, option, 1)
        elif option_type == 6:
            hex_option = option
        elif option_type == 7:
            hex_option = SocketView.int_to_hex(self, option, 1)
        elif option_type == 66:
            hex_option = SocketView.float_to_hex(self, option)
        byte1 = option_type
        byte2 = 0x00
        byte3 = 0x00
        byte4 = 0xCD
        if option_type == 66:
            byte1 = 6
            byte4 = 0x00

        hex_option_no_spaces = hex_option.replace(" ", "")
        byte8 = len(hex_option_no_spaces) // 2 + 8
        # print(f"1111  {hex_option}")
        hex_length = format(byte8, '08X')
        hex_option_header = f"{byte1:02X}{byte2:02X}{byte3:02X}{byte4:02X}{hex_length}"
        full_option = hex_option_header + hex_option
        return full_option

    def gene_message(self, sign, geneNumber):
        if sign == -1:
            if geneNumber == 1:
                message = ("CREATEPLATFORM PLAT1 0 LAT 45 LON -135 ALT 0 DAMAGESTATE 0 Type 1 \n"
                           "CREATEPLATFORM PLAT2 0 LAT 45 LON -125 ALT 0 DAMAGESTATE 0 Type 1 \n")
            elif geneNumber == -1:
                message = ("INTERVAL 5\n"
                           "FINAL 30\n")
                # 这个值应该是预先设计好的，此处非法
            else:
                message = ("UPDATEPLATFORM PLAT1 10 LAT 46 LON -135 ALT 5000.3 DAMAGESTATE 0 \n"
                           "UPDATEPLATFORM PLAT2 10 LAT 35 LON -135 ALT 20 DAMAGESTATE 0 \n")

        # 打开文件，如果文件不存在则创建
        try:
            with open(SocketView.config_file, 'w', encoding='utf-8') as file:
                file.write(message)
        except Exception as e:
            print(f"创建文件失败: {e}")

    def read_message_file(self,current_path):
        """读取消息文件并将符合条件的消息加入队列"""
        SocketView.config_file=current_path / "config_no_move.txt"
        if os.path.exists(SocketView.config_file):
            try:

                with open(current_path / "config_no_move.txt", 'r') as file:
                    lines = file.readlines()

                    SocketView.satellites = []
                    SocketView.links = []
                    for line in lines:
                        if not line.strip():
                            continue
                        # 先去除行首尾的空白字符，然后按照空格分隔
                        command_parts = line.strip().split()

                        # 取出第一个部分（命令）
                        command = command_parts[0]

                        if command == 'CREATEPLATFORM':
                            # 如果命令是 CreatePlatform，则继续解析后续参数
                            entity_id = command_parts[1]
                            command_type = 10
                            hex_entity_id = SocketView.string_to_hex(self, entity_id)
                            hex_header = SocketView.add_message_header(self, command_type, hex_entity_id, command, 2)

                            time = command_parts[2]
                            option_type = 2

                            hex_time = SocketView.add_option_header(self, option_type, time)
                            # 初始化默认值

                            hex_latitude = ""
                            hex_longitude = ""
                            hex_altitude = ""
                            hex_damage_state = ""
                            hex_type = ""
                            # 遍历剩下的命令参数
                            i = 3  # 从第4个元素开始遍历，因为前面已经处理了entityID和time
                            while i < len(command_parts):
                                if command_parts[i] == 'LAT':
                                    latitude = command_parts[i + 1]
                                    i += 2  # 跳过 'LAT' 和对应的值
                                    hex_latitude = SocketView.float_to_hex(self, latitude)

                                elif command_parts[i] == 'LON':
                                    longitude = command_parts[i + 1]
                                    hex_longitude = SocketView.float_to_hex(self, longitude)
                                    i += 2
                                elif command_parts[i] == 'ALT':
                                    altitude = command_parts[i + 1]
                                    hex_altitude = SocketView.float_to_hex(self, altitude)
                                    print(f"hex_altitude: {hex_altitude}")
                                    i += 2
                                elif command_parts[i] == 'VELLON':
                                    vellon = command_parts[i + 1]
                                    # 速度暂时不用
                                    i += 2
                                elif command_parts[i] == 'VELALT':
                                    velalt = command_parts[i + 1]
                                    # 速度暂时不用
                                    i += 2
                                elif command_parts[i] == 'DAMAGESTATE':
                                    damage_state = command_parts[i + 1]
                                    hex_damage_state = SocketView.int_to_hex(self, damage_state, 1)
                                    i += 2
                                elif command_parts[i] == 'Type':
                                    platform_type = command_parts[i + 1]
                                    # hex_platform_type = SocketView.int_to_hex(self, platform_type, 1)
                                    option_type = 4
                                    hex_type = SocketView.add_option_header(self, option_type, 1)
                                    # print(f"hex type is :{hex_type}")
                                    i += 2
                                else:
                                    i += 1  # 如果没有匹配项，则跳过当前参数

                            # 执行相应的操作
                            final_command = hex_header + hex_entity_id + hex_latitude + hex_longitude + hex_altitude + hex_damage_state + hex_time + hex_type
                            # print(f"final cp is :{final_command}")
                            SocketView.satellites.append({
                                "satellite_id": "satellite_" + command_parts[1],
                                "lat": command_parts[4],
                                "lon": command_parts[6],
                                "alt": command_parts[8],
                                "type": None,
                                "name": None,
                                "error_interface": None,
                                "print_link": None,
                            })
                            if SocketView.initial_k == 1:
                                SocketView.send_queue.append(final_command)
                    SocketView.initial_k = 0
                with open(SocketView.config_file, 'r') as file:
                    lines = file.readlines()
                    for line in lines:
                        if not line.strip():
                            continue
                        # 先去除行首尾的空白字符，然后按照空格分隔
                        command_parts = line.strip().split()

                        # 取出第一个部分（命令）
                        command = command_parts[0]

                        if command == 'CREATEPLATFORM':
                            # 如果命令是 CreatePlatform，则继续解析后续参数
                            entity_id = command_parts[1]
                            command_type = 10
                            hex_entity_id = SocketView.string_to_hex(self, entity_id)
                            hex_header = SocketView.add_message_header(self, command_type, hex_entity_id, command, 2)

                            time = command_parts[2]
                            option_type = 2

                            hex_time = SocketView.add_option_header(self, option_type, time)
                            # 初始化默认值

                            hex_latitude = ""
                            hex_longitude = ""
                            hex_altitude = ""
                            hex_damage_state = ""
                            hex_type = ""
                            # 遍历剩下的命令参数
                            i = 3  # 从第4个元素开始遍历，因为前面已经处理了entityID和time
                            while i < len(command_parts):
                                if command_parts[i] == 'LAT':
                                    latitude = command_parts[i + 1]
                                    i += 2  # 跳过 'LAT' 和对应的值
                                    hex_latitude = SocketView.float_to_hex(self, latitude)

                                elif command_parts[i] == 'LON':
                                    longitude = command_parts[i + 1]
                                    hex_longitude = SocketView.float_to_hex(self, longitude)
                                    i += 2
                                elif command_parts[i] == 'ALT':
                                    altitude = command_parts[i + 1]
                                    hex_altitude = SocketView.float_to_hex(self, altitude)
                                    print(f"hex_altitude: {hex_altitude}")
                                    i += 2
                                elif command_parts[i] == 'VELLON':
                                    vellon = command_parts[i + 1]
                                    # 速度暂时不用
                                    i += 2
                                elif command_parts[i] == 'VELALT':
                                    velalt = command_parts[i + 1]
                                    # 速度暂时不用
                                    i += 2
                                elif command_parts[i] == 'DAMAGESTATE':
                                    damage_state = command_parts[i + 1]
                                    hex_damage_state = SocketView.int_to_hex(self, damage_state, 1)
                                    i += 2
                                elif command_parts[i] == 'Type':
                                    platform_type = command_parts[i + 1]
                                    # hex_platform_type = SocketView.int_to_hex(self, platform_type, 1)
                                    option_type = 4
                                    hex_type = SocketView.add_option_header(self, option_type, 1)
                                    # print(f"hex type is :{hex_type}")
                                    i += 2
                                else:
                                    i += 1  # 如果没有匹配项，则跳过当前参数

                            # 执行相应的操作
                            final_command = hex_header + hex_entity_id + hex_latitude + hex_longitude + hex_altitude + hex_damage_state + hex_time + hex_type
                            # print(f"final cp is :{final_command}")
                            SocketView.satellites.append({
                                "satellite_id": "satellite_" + command_parts[1],
                                "lat": command_parts[4],
                                "lon": command_parts[6],
                                "alt": command_parts[8],
                                "type": None,
                                "name": None,
                                "error_interface": None,
                                "print_link": None,
                            })
                            SocketView.send_queue.append(final_command)
                        if command == 'UPDATEPLATFORM':
                            # 如果命令是 CreatePlatform，则继续解析后续参数
                            entity_id = command_parts[1]
                            command_type = 11
                            hex_entity_id = SocketView.string_to_hex(self, entity_id)
                            hex_header = SocketView.add_message_header(self, command_type, hex_entity_id, command, 3)

                            time = command_parts[2]
                            option_type = 2

                            hex_time = SocketView.add_option_header(self, option_type, time)
                            # 初始化默认值

                            hex_latitude = ""
                            hex_longitude = ""
                            hex_altitude = ""
                            hex_damage_state = ""
                            hex_type = ""
                            # 遍历剩下的命令参数
                            i = 3  # 从第4个元素开始遍历，因为前面已经处理了entityID和time
                            while i < len(command_parts):
                                if command_parts[i] == 'LAT':
                                    latitude = command_parts[i + 1]
                                    i += 2  # 跳过 'LAT' 和对应的值
                                    hex_latitude = SocketView.float_to_hex(self, latitude)

                                elif command_parts[i] == 'LON':
                                    longitude = command_parts[i + 1]
                                    hex_longitude = SocketView.float_to_hex(self, longitude)
                                    i += 2
                                elif command_parts[i] == 'ALT':
                                    altitude = command_parts[i + 1]
                                    hex_altitude = SocketView.float_to_hex(self, altitude)
                                    i += 2
                                elif command_parts[i] == 'VELLON':
                                    vellon = command_parts[i + 1]
                                    # 速度暂时不用
                                    i += 2
                                elif command_parts[i] == 'VELALT':
                                    velalt = command_parts[i + 1]
                                    # 速度暂时不用
                                    i += 2
                                elif command_parts[i] == 'DAMAGESTATE':
                                    damage_state = command_parts[i + 1]
                                    hex_damage_state = SocketView.int_to_hex(self, damage_state, 1)
                                    i += 2
                                elif command_parts[i] == 'Type':
                                    platform_type = command_parts[i + 1]
                                    # hex_platform_type = SocketView.int_to_hex(self, platform_type, 1)
                                    option_type = 4
                                    hex_type = SocketView.add_option_header(self, option_type, 1)
                                    # print(f"hex type is :{hex_type}")
                                    i += 2
                                else:
                                    i += 1  # 如果没有匹配项，则跳过当前参数
                            option_type = 6
                            position = hex_latitude + hex_longitude + hex_altitude
                            # print(f"position is {position}")
                            hex_position = SocketView.add_option_header(self, option_type, position)
                            option_type = 7
                            hex_damage_state = SocketView.add_option_header(self, option_type, hex_damage_state)
                            # 执行相应的操作
                            final_command = hex_header + hex_entity_id + hex_time + hex_position + hex_damage_state
                            # print(f"final cp is :{final_command}")
                            SocketView.satellites.append({
                                "satellite_id": "satellite_" + command_parts[1],
                                "lat": command_parts[4],
                                "lon": command_parts[6],
                                "alt": command_parts[8],
                                "type": None,
                                "name": None,
                                "error_interface": None,
                                "print_link": None,
                            })
                            SocketView.send_queue.append(final_command)
                        if command == 'Write':
                            link_time = command_parts[1]  #此变量没用
                            # 此处需要注意，节点的id和名称和ip和接口名称都息息相关
                            command_type = 8
                            field_type = "01"
                            interface_path = command_parts[3]
                            degrees = str(command_parts[5])
                            hex_entity_id1 = SocketView.string_to_hex(self, interface_path)
                            hex_entity_id2 = SocketView.string_to_hex(self, degrees)
                            hex_header = SocketView.add_message_header(self, command_type,
                                                                       hex_entity_id1 + hex_entity_id2, command, 0)
                            final_command = hex_header + field_type + hex_entity_id1 + hex_entity_id2
                            # print(f"write command is {final_command}")
                            # 拆分路径，提取 "169.0.0.2"
                            ip_segment = interface_path.split('/')[4]  # "169.0.0.2"
                            azimuth = interface_path.split('/')[-1]  # "PHY-ABSTRACT-AZIMUTH"
                            # 提取 "AZIMUTH"
                            azimuth_type = azimuth.split('-')[-1]  # "AZIMUTH"
                            # if azimuth_type == "AZIMUTH" and command_parts[8] != "false":
                            SocketView.send_queue.append(final_command)
                    # sendtofrontbysocket(self, SocketView.now_time, SocketView.satellites, SocketView.links)
                SocketView.send_control_message(self, int(SocketView.interval), int(SocketView.final))
                if SocketView.continue_send == False:
                    SocketView.send_stop_message(self, int(SocketView.final))


            except Exception as e:
                print(f"读取消息文件失败: {e}")
    def send_start_message(self):
        SocketView.send_queue.append(SocketView.initialmessage)
        SocketView.send_queue.append(SocketView.pausemessage)
        SocketView.send_queue.append(SocketView.startmessage)

    def send_control_message(self, interval, finaltime):

        SocketView.now_time = SocketView.now_time + interval
        if SocketView.now_time >= finaltime:
            # print("final time 已经被比较")
            SocketView.continue_send = False
        else:

            controlmessage = SocketView.add_option_header(self, 66, SocketView.now_time)
            SocketView.send_queue.append(controlmessage)
            print(f"simulaiton time is {SocketView.now_time}")

    def send_stop_message(self, finaltime):
        final_header = '04 01 00 00 00 00 00 18 '
        final_option = SocketView.add_option_header(self, 2, finaltime)
        final_message = final_header + final_option
        SocketView.send_queue.append(final_message)
        SocketView.send_queue.append(final_message)
        SocketView.controlmessage = SocketView.add_option_header(self, 66, finaltime)
        SocketView.over_controlmessage = SocketView.add_option_header(self, 66, finaltime + int(SocketView.interval))
        SocketView.send_queue.append(SocketView.controlmessage)
        SocketView.send_queue.append(SocketView.over_controlmessage)

    def send_next_message(self):
        """发送队列中的下一条消息"""
        while True:
            if SocketView.send_queue:
                # 用于开始暂停过的仿真
                SocketView.simulation_running = True
                message = SocketView.send_queue[0]
                print(f"发送消息队列：{SocketView.send_queue}")
                SocketView.send_queue.remove(SocketView.send_queue[0])
                encoded_message = bytes.fromhex(message)
                if message.startswith('06'):
                    time.sleep(0.5)
                    print("nihao")
                try:
                    if message == SocketView.over_controlmessage:
                        time.sleep(3)
                        SocketView.over_controlmessage = ""
                    if message == SocketView.controlmessage:
                        time.sleep(3)
                        SocketView.controlmessage = ""

                    SocketView.client_socket.sendall(encoded_message)
                    # time.sleep(0.5)
                    SocketView.message_indexContinue += 1
                    print(f"已发送消息: {message}")
                    # return {"status": "消息发送成功", "message": message}
                except socket.error as e:
                    return {"status": f"发送失败: {e}"}
            else:
                break


    @csrf_exempt
    def pause_simulation(self):
        """定时发送消息，间隔 3 秒发送下一条消息"""
        if SocketView.simulation_running:
            # SocketView.send_queue.insert(0, SocketView.pausemessage)
            SocketView.simulation_running = False  # 停止仿真
            SocketView.set_isPaused(True)
            return {"status": "仿真已暂停"}
        else:
            return {"status": "请不要重复暂停，但你不应该看见这句话"}

    @csrf_exempt
    def continue_simulation(self):
        """定时发送消息，间隔 3 秒发送下一条消息"""
        if not SocketView.simulation_running:
            # SocketView.send_queue.insert(0, SocketView.pausemessage)
            SocketView.simulation_running = True  # 停止仿真
            SocketView.set_isPaused(False)
            SocketView.isStep = False
            return {"status": "仿真已继续开始执行"}
        else:
            return {"status": "请不要重复开始，但你不应该看见这句话"}

    @csrf_exempt
    def step_simulation(self):
        """定时发送消息，间隔 3 秒发送下一条消息"""
        if not SocketView.simulation_running:
            print("我进入了step_simulation")
            SocketView.set_isPaused(False)
            SocketView.set_isStep(True)
            SocketView.hasbeenstep = False
            return {"status": "仿真已继续开始执行"}
        else:
            return {"status": "请不要重复开始，但你不应该看见这句话"}

    @classmethod
    def close_connection(cls):
        if cls.client_socket:
            cls.client_socket.close()
            cls.client_socket = None
            print("关闭连接")
