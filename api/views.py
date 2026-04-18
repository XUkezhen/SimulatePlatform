import shutil
import sys
from pathlib import Path
import importlib.util
from functools import lru_cache

'''
以下是lykcode
'''

import socket

import struct
import time
import threading
import binascii
import math

from django.views import View
from django.middleware.csrf import get_token

from threading import Lock

from .consumers import trigger_push

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
# 以下软件包和sgp4相关
from sgp4.api import Satrec, WGS72
from sgp4.functions import jday
import pymap3d as pm
from datetime import datetime, timedelta

from links import StaticDynamicLinkCalculator

from runExata import ExataSimulator

import subprocess

import json
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from .models import *
from .forms import *
from django.db.models import Q, Prefetch
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from .serializers import ConfigurationSerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from django.utils import timezone
from datetime import datetime
from ipaddress import IPv4Network, AddressValueError
from django.shortcuts import get_object_or_404
import os
import re
import glob
from typing import List, Dict, Tuple
from django.conf import settings
from jinja2 import Environment, FileSystemLoader


def env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


EXATA_MANAGED_EXTERNALLY = env_flag("EXATA_MANAGED_EXTERNALLY", False)
EXATA_SERVICE_HOST = os.getenv("EXATA_SERVICE_HOST", "127.0.0.1")
EXATA_SERVICE_PORT = int(os.getenv("EXATA_SERVICE_PORT", "8005"))
EXATA_EXECUTABLE_PATH = os.getenv(
    "EXATA_EXECUTABLE_PATH",
    str(Path(__file__).resolve().parents[2] / "exata.exe"),
)
EXATA_RESTART_SCRIPT = os.getenv("EXATA_RESTART_SCRIPT", "restart_backend_pm2.bat")
PM2_LOG_DIR = Path(
    os.getenv("PM2_LOG_DIR", str(Path.home() / ".pm2" / "logs"))
)
RUNTIME_LOG_LINE_LIMIT = int(os.getenv("RUNTIME_LOG_LINE_LIMIT", "200"))


def build_exata_simulator(working_directory, config_file, **_ignored):
    return ExataSimulator(
        working_directory=working_directory,
        executable_path=EXATA_EXECUTABLE_PATH,
        config_file=config_file,
    )


def create_exata_simulator(working_directory, config_file):
    return build_exata_simulator(
        working_directory=working_directory,
        config_file=config_file,
    )


def _parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _decode_log_bytes(content):
    for encoding in ("utf-8", "gb18030", "gbk", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _read_log_tail(path: Path, lines: int) -> list[str]:
    if not path.exists() or not path.is_file():
        return []

    text = _decode_log_bytes(path.read_bytes())
    return text.splitlines()[-lines:]
from .network_layer_data import find_bellmanford_files, get_block_by_sim_time, parse_bellmanford_file
from .物理层数据采集2 import extract_config_parameters
from .链路层数据采集 import process_link_relationships


def _extract_channel_name(channel_config):
    if not isinstance(channel_config, dict):
        return None

    for key, value in channel_config.items():
        if isinstance(key, str) and key.startswith('PROPAGATION-CHANNEL-NAME'):
            return str(value)

    return None


def _get_scene_channel_data(scene):
    raw_channel_configs = scene.channelConfigs or []
    if not isinstance(raw_channel_configs, list):
        return [], [], 'Channel0'

    channel_configs = [config for config in raw_channel_configs if isinstance(config, dict)]
    channel_names = []

    for config in channel_configs:
        channel_name = _extract_channel_name(config)
        if channel_name:
            channel_names.append(channel_name)

    primary_channel_name = channel_names[0] if channel_names else 'Channel0'
    return channel_configs, channel_names, primary_channel_name


def _normalize_yes_no_flag(value, field_name, default='YES'):
    if value in (None, ''):
        return default

    if isinstance(value, bool):
        return 'YES' if value else 'NO'

    normalized_value = str(value).strip().upper()
    if normalized_value in {'YES', 'TRUE', '1'}:
        return 'YES'
    if normalized_value in {'NO', 'FALSE', '0'}:
        return 'NO'

    raise ValueError(f'{field_name} must be YES or NO')


def _calculate_link_layer_azimuth(x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    azimuth = math.degrees(math.atan2(dx, dy))
    return (azimuth + 360) % 360


def _calculate_link_layer_elevation(x1, y1, z1, x2, y2, z2):
    dx = x2 - x1
    dy = y2 - y1
    dz = z2 - z1
    horizontal_distance = math.sqrt(dx ** 2 + dy ** 2)
    return math.degrees(math.atan2(dz, horizontal_distance))


def _parse_link_layer_groups(config_file: Path) -> List[set]:
    connected_groups = []

    with config_file.open('r', encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not (line.startswith('SUBNET') or line.startswith('LINK ')):
                continue

            match = re.search(r'\{\s*([\d\s,]+)\s*\}', line)
            if not match:
                continue

            nodes = [int(node_id.strip()) for node_id in match.group(1).split(',')]
            connected_groups.append(set(nodes))

    return connected_groups


def _parse_link_layer_positions(nodes_file: Path) -> Dict[int, Tuple[float, float, float]]:
    positions: Dict[int, Tuple[float, float, float]] = {}

    with nodes_file.open('r', encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            match = re.match(r'^(\d+)\s+\S+\s+\(([^)]+)\)', line)
            if not match:
                continue

            node_id = int(match.group(1))
            if node_id in positions:
                continue

            coord_parts = [part for part in re.split(r'[\s,]+', match.group(2).strip()) if part]
            if len(coord_parts) != 3:
                continue

            positions[node_id] = tuple(float(value) for value in coord_parts)

    return positions


def _build_link_layer_data(config_file: Path, nodes_file: Path) -> List[Dict]:
    connected_groups = _parse_link_layer_groups(config_file)
    positions = _parse_link_layer_positions(nodes_file)
    all_nodes = sorted(positions.keys())

    results = []
    for index, node1 in enumerate(all_nodes):
        for node2 in all_nodes[index + 1:]:
            is_neighbor = any(node1 in group and node2 in group for group in connected_groups)
            pos1 = positions[node1]
            pos2 = positions[node2]
            azimuth1 = _calculate_link_layer_azimuth(pos1[0], pos1[1], pos2[0], pos2[1])
            azimuth2 = _calculate_link_layer_azimuth(pos2[0], pos2[1], pos1[0], pos1[1])
            elevation1 = _calculate_link_layer_elevation(pos1[0], pos1[1], pos1[2], pos2[0], pos2[1], pos2[2])
            elevation2 = _calculate_link_layer_elevation(pos2[0], pos2[1], pos2[2], pos1[0], pos1[1], pos1[2])

            results.append({
                'Node1': node1,
                'Node2': node2,
                'Is_Neighbor': is_neighbor,
                'Node1_Pos': f'({pos1[0]:.4f}, {pos1[1]:.4f}, {pos1[2]:.4f})',
                'Node2_Pos': f'({pos2[0]:.4f}, {pos2[1]:.4f}, {pos2[2]:.4f})',
                'Azimuth_1_to_2': round(azimuth1, 2),
                'Azimuth_2_to_1': round(azimuth2, 2),
                'Elevation_1_to_2': round(elevation1, 2),
                'Elevation_2_to_1': round(elevation2, 2),
            })

    return results


def _parse_link_relationships_file(file_path: Path) -> List[Dict]:
    with file_path.open('r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return []

    results = []
    for line in lines[1:]:
        parts = line.split('\t')
        if len(parts) != 9:
            continue

        results.append({
            'Node1': int(parts[0]),
            'Node2': int(parts[1]),
            'Is_Neighbor': parts[2].strip().lower() == 'true',
            'Node1_Pos': parts[3],
            'Node2_Pos': parts[4],
            'Azimuth_1_to_2': float(parts[5]),
            'Azimuth_2_to_1': float(parts[6]),
            'Elevation_1_to_2': float(parts[7]),
            'Elevation_2_to_1': float(parts[8]),
        })

    return results


SCENE_LLC_API_KEY = 'LLC-ENABLED'
SCENE_ARP_API_KEY = 'ARP-ENABLED'


def _default_scene_start_time():
    return timezone.now().replace(second=0, microsecond=0)


def _parse_scene_datetime(value, field_name):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValidationError(f'{field_name} 不能为空')
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValidationError(f'{field_name} 时间格式无效') from exc
    else:
        raise ValidationError(f'{field_name} 时间格式无效')

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _parse_scene_duration_seconds(value):
    if value in [None, '']:
        return None

    if isinstance(value, bool):
        raise ValidationError('durationSeconds 必须是正整数')

    if isinstance(value, int):
        duration_seconds = value
    elif isinstance(value, float):
        if not value.is_integer():
            raise ValidationError('durationSeconds 必须是正整数')
        duration_seconds = int(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text or not re.fullmatch(r'[+-]?\d+', text):
            raise ValidationError('durationSeconds 必须是正整数')
        duration_seconds = int(text)
    else:
        raise ValidationError('durationSeconds 必须是正整数')

    if duration_seconds <= 0:
        raise ValidationError('durationSeconds 必须大于 0')
    return duration_seconds


def _resolve_scene_time_range(start_time_value, end_time_value, duration_value, *, existing_start_time=None, existing_end_time=None):
    if start_time_value in [None, '']:
        start_time = existing_start_time or _default_scene_start_time()
    else:
        start_time = _parse_scene_datetime(start_time_value, 'startTime')

    duration_seconds = _parse_scene_duration_seconds(duration_value)

    if duration_seconds is not None:
        end_time = start_time + timedelta(seconds=duration_seconds)
    elif end_time_value not in [None, '']:
        end_time = _parse_scene_datetime(end_time_value, 'endTime')
    elif existing_start_time and existing_end_time:
        end_time = start_time + (existing_end_time - existing_start_time)
    else:
        raise ValidationError('缺少必填字段: durationSeconds')

    if end_time <= start_time:
        raise ValidationError('开始时间必须早于结束时间')

    duration_seconds = int((end_time - start_time).total_seconds())
    if duration_seconds <= 0:
        raise ValidationError('durationSeconds 必须大于 0')

    return start_time, end_time, duration_seconds

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
        duration_seconds_raw = data.get('durationSeconds')
        simulation_step = data.get('simulationStep')
        channel_count = data.get('channelCount', 0)
        channel_configs = data.get('channelConfigs', [])
        llc_enabled = _normalize_yes_no_flag(data.get(SCENE_LLC_API_KEY, data.get('llcEnabled')), SCENE_LLC_API_KEY)
        arp_enabled = _normalize_yes_no_flag(data.get(SCENE_ARP_API_KEY, data.get('arpEnabled')), SCENE_ARP_API_KEY)
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON format'
        }, status=400)
    except ValueError as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

    # 验证必要参数是否存在
    if not all([scene_name, simulation_step]) or (duration_seconds_raw in [None, ''] and end_time_str in [None, '']):
        return JsonResponse({
            'status': 'error',
            'message': 'Missing required fields: sceneName, simulationStep, durationSeconds'
        }, status=400)

    try:
        start_time, end_time, duration_seconds = _resolve_scene_time_range(
            start_time_str,
            end_time_str,
            duration_seconds_raw,
        )
    except ValidationError as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
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

    # 验证信道配置
    try:
        channel_count = int(channel_count) if channel_count else 0
        if channel_count < 0:
            return JsonResponse({
                'status': 'error',
                'message': 'channelCount must be a non-negative integer'
            }, status=400)
    except (ValueError, TypeError):
        return JsonResponse({
            'status': 'error',
            'message': 'channelCount must be an integer'
        }, status=400)

    if channel_configs and not isinstance(channel_configs, list):
        return JsonResponse({
            'status': 'error',
            'message': 'channelConfigs must be an array'
        }, status=400)

    if channel_count > 0 and len(channel_configs) != channel_count:
        return JsonResponse({
            'status': 'error',
            'message': f'channelConfigs length ({len(channel_configs)}) must match channelCount ({channel_count})'
        }, status=400)

    try:
        # 创建场景对象
        scene = Scene.objects.create(
            sceneName=scene_name,
            startTime=start_time,
            endTime=end_time,
            simulationStep=simulation_step,
            channelCount=channel_count,
            channelConfigs=channel_configs,
            llcEnabled=llc_enabled,
            arpEnabled=arp_enabled
        )

        # 创建默认子网
        default_subnet = Subnet.objects.create(
            sceneId=scene,
            subnetName=f"{scene_name} (Default)",
            subnetIp="169.0.0.0",
            subnetMask="255.255.255.0",
            subnetType='sub'
        )

        # 成功响应
        return JsonResponse({
            'status': 'success',
            'sceneId': scene.id,
            'sceneName': scene.sceneName,
            'durationSeconds': duration_seconds,
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
        scene_name = scene.sceneName  # 取场景名
        # 构造文件夹路径：项目根目录/scene_files/场景名
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scene_files')#找到当前 app 的上一级目录，再拼接
        scene_dir = os.path.join(base_dir, scene_name)
        # 删除文件夹（如果存在）
        if os.path.exists(scene_dir) and os.path.isdir(scene_dir):
            shutil.rmtree(scene_dir)
            logger.info(f"场景文件夹删除成功: {scene_dir}")  # ✅ 打印日志
        # 删除数据库记录
        scene.delete()
        return JsonResponse({'status': 'success'})
    except Scene.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '场景不存在'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


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
        new_duration_seconds = data.get('durationSeconds')
        new_simulation_step = int(data.get('simulationStep', scene.simulationStep))
        new_channel_count = data.get('channelCount', scene.channelCount)
        new_channel_configs = data.get('channelConfigs', scene.channelConfigs)
        new_llc_enabled = _normalize_yes_no_flag(
            data[SCENE_LLC_API_KEY] if SCENE_LLC_API_KEY in data else data.get('llcEnabled', scene.llcEnabled),
            SCENE_LLC_API_KEY,
            default=scene.llcEnabled,
        )
        new_arp_enabled = _normalize_yes_no_flag(
            data[SCENE_ARP_API_KEY] if SCENE_ARP_API_KEY in data else data.get('arpEnabled', scene.arpEnabled),
            SCENE_ARP_API_KEY,
            default=scene.arpEnabled,
        )

        # 验证场景名称是否重复
        if Scene.objects.exclude(id=scene_id).filter(sceneName=new_scene_name).exists():
            return JsonResponse({'status': 'error', 'message': '该场景名称已存在，请使用其他名称'}, status=400)

        try:
            new_start_time, new_end_time, duration_seconds = _resolve_scene_time_range(
                new_start_time,
                new_end_time,
                new_duration_seconds,
                existing_start_time=scene.startTime,
                existing_end_time=scene.endTime,
            )
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

        # 验证信道配置
        if new_channel_count is not None:
            try:
                new_channel_count = int(new_channel_count)
                if new_channel_count < 0:
                    return JsonResponse({'status': 'error', 'message': 'channelCount must be a non-negative integer'}, status=400)
            except (ValueError, TypeError):
                return JsonResponse({'status': 'error', 'message': 'channelCount must be an integer'}, status=400)

        if new_channel_configs is not None:
            if not isinstance(new_channel_configs, list):
                return JsonResponse({'status': 'error', 'message': 'channelConfigs must be an array'}, status=400)
            if new_channel_count is not None and len(new_channel_configs) != new_channel_count:
                return JsonResponse({'status': 'error', 'message': 'channelConfigs length must match channelCount'}, status=400)

        if new_scene_name != scene.sceneName:
            try:
                _rename_scene_directory_and_files(scene.sceneName, new_scene_name)
            except ValueError as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

        # 更新场景信息
        scene.sceneName = new_scene_name
        scene.startTime = new_start_time
        scene.endTime = new_end_time
        scene.simulationStep = new_simulation_step
        scene.channelCount = new_channel_count
        scene.channelConfigs = new_channel_configs
        scene.llcEnabled = new_llc_enabled
        scene.arpEnabled = new_arp_enabled
        scene.save()

        return JsonResponse({'status': 'success', 'durationSeconds': duration_seconds})

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
        'durationSeconds': int((scene.endTime - scene.startTime).total_seconds()),
        'simulationStep': scene.simulationStep,
        'channelCount': scene.channelCount,
        'channelConfigs': scene.channelConfigs,
        SCENE_LLC_API_KEY: scene.llcEnabled,
        SCENE_ARP_API_KEY: scene.arpEnabled
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


@require_http_methods(["GET"])
@csrf_exempt
def get_runtime_logs(request):
    requested_lines = _parse_int(request.GET.get("lines"), 80)
    lines = max(1, min(requested_lines, RUNTIME_LOG_LINE_LIMIT))

    backend_error_log = PM2_LOG_DIR / "backend-error.log"
    backend_out_log = PM2_LOG_DIR / "backend-out.log"

    return JsonResponse({
        "updatedAt": datetime.utcnow().isoformat() + "Z",
        "lines": lines,
        "logDir": str(PM2_LOG_DIR),
        "logs": {
            "backendError": _read_log_tail(backend_error_log, lines),
            "backendOut": _read_log_tail(backend_out_log, lines),
        },
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
        details = data.get('details',[])
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
        if Subnet.objects.filter(sceneId=scene, subnetIp=subnet_ip, subnetMask=subnet_mask,subnetType=Subnet.SubnetTypeChoices.SUB).exists():
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
                details = details,
                subnetType="sub"
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

                    if default_interface:  #不该是默认接口了！！
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
                        # 查找可用接口索引（0-9）
                        existing_indices = node.interfaces.values_list('interfaceIndex', flat=True)
                        for index in range(10):
                            if index not in existing_indices:
                                interface_index = index
                                break
                        else:
                            # 找不到可用接口索引
                            return JsonResponse({
                                'status': 'error',
                                'message': f'节点 {node_id} 已达到最大接口数 (10个)'
                            }, status=400)

                        Interface.objects.create(
                            node=node,
                            interfaceIp=new_ip,
                            interfaceIndex=interface_index,
                            subnetMask=subnet_mask,
                            is_default=False,
                            is_allocated=False,
                            subnet=subnet,
                            interfaceType="sub"
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

'''
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

        # 获取字段值
        subnet_name = data.get('subnetName', subnet.subnetName)
        details = data.get('details', subnet.details)

        # 验证子网名唯一性
        if 'subnetName' in data and subnet_name != subnet.subnetName:
            if Subnet.objects.filter(
                sceneId=scene,
                subnetName=subnet_name
            ).exclude(id=subnet_id).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': f'场景 \"{scene.sceneName}\" 中已存在名为 \"{subnet_name}\" 的子网'
                }, status=400)

        # 更新子网
        with transaction.atomic():
            subnet.subnetName = subnet_name
            subnet.details = details
            subnet.full_clean()
            subnet.save()

        return JsonResponse({
            'status': 'success',
            'message': '子网更新成功',
            'subnetId': subnet.id
        })

    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
'''


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
        details = data.get('details',subnet.details)
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
            if any(field in data for field in ['subnetName', 'subnetIp', 'subnetMask','details']):
                subnet.subnetName = subnet_name
                # subnet.subnetIp = subnet_ip
                subnet.subnetMask = subnet_mask
                subnet.details = details
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

                # for node_id in current_nodes:
                #     node = Node.objects.get(id=node_id, sceneId=scene)
                #     interfaces = Interface.objects.filter(
                #         node=node,
                #         subnet=subnet
                #     )
                #     interfaces.delete()

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

                # 获取 interfaceList（从 request.POST 或 request.data 中获取）
                interface_list = data.get('interfaceList', [])

                # 构建 nodeId -> 指定IP 映射
                interface_ip_map = {entry['nodeId']: entry.get('interfaceIp') for entry in interface_list if
                                    'nodeId' in entry}

                # 查询已分配 IP
                allocated_ips = set(
                    Interface.objects.filter(subnet=subnet)
                    .exclude(interfaceIp__isnull=True)
                    .values_list('interfaceIp', flat=True)
                )

                # 构建可用 IP 列表
                all_ips = [str(ip) for ip in network.hosts()]
                available_ips = [ip for ip in all_ips if ip not in allocated_ips]
                # 再去除前端已指定的 IP（避免自动分配重复）
                specified_ips = {ip for ip in interface_ip_map.values() if ip}
                available_ips = [ip for ip in available_ips if ip not in specified_ips]

                # # 检查前端传来的 IP 是否冲突
                # for node_id, ip in interface_ip_map.items():
                #     if ip and ip in allocated_ips:
                #         return JsonResponse({
                #             'status': 'error',
                #             'message': f'节点 {node_id} 指定的 IP {ip} 已被占用'
                #         }, status=400)
                #     if ip and ip not in all_ips:
                #         return JsonResponse({
                #             'status': 'error',
                #             'message': f'节点 {node_id} 指定的 IP {ip} 不在子网 {subnet.subnetIp}/{subnet.subnetMask} 范围内'
                #         }, status=400)

                # 为未指定 IP 的节点预留足够数量
                unspecified_nodes = [node_id for node_id in new_nodes if not interface_ip_map.get(node_id)]
                if len(available_ips) < len(unspecified_nodes):
                    return JsonResponse({
                        'status': 'error',
                        'message': f'子网中可用IP不足（需要 {len(unspecified_nodes)} 个，可用 {len(available_ips)} 个）'
                    }, status=400)

                ip_iter = iter(available_ips)

                for node_id in nodes_to_add:
                    try:
                        node = Node.objects.get(id=node_id, sceneId=scene)
                        specified_ip = interface_ip_map.get(node_id)
                        assigned_ip = specified_ip if specified_ip else next(ip_iter)

                        # 查找节点的默认接口
                        default_interface = node.interfaces.filter(is_default=True).first()

                        if default_interface:
                            # 更新现有默认接口：移动到当前子网
                            default_interface.subnet = subnet
                            default_interface.interfaceIp = assigned_ip
                            default_interface.subnetMask = subnet_mask
                            default_interface.is_allocated = False
                            default_interface.is_default = False
                            default_interface.save()
                        else:
                            # 没有默认接口，创建新接口作为默认接口
                            existing_indices = node.interfaces.values_list('interfaceIndex', flat=True)
                            interface_index = next((i for i in range(10) if i not in existing_indices), None)

                            if interface_index is None:
                                return JsonResponse({
                                    'status': 'error',
                                    'message': f'节点 {node_id} 已达到最大接口数 (10个)'
                                }, status=400)

                            Interface.objects.create(
                                node=node,
                                interfaceIp=assigned_ip,
                                interfaceIndex=interface_index,
                                subnetMask=subnet_mask,
                                is_default=False,
                                is_allocated=False,
                                subnet=subnet
                            )
                    except Node.DoesNotExist:
                        continue

                # === 批量处理默认子网的IP分配 ===  感觉用不到这些
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
        reorder_interfaces_by_scene(scene_id)  # 给接口排序，sub类的接口在前
        # 预取接口数据
        interface_prefetch = Prefetch(
            'interfaces',
            queryset=Interface.objects.select_related('node').only(
                'id', 'interfaceIp', 'interfaceIndex', 'subnetMask',
                'is_default', 'is_allocated', 'node__id', 'node__nodeName'
            )
        )

        # 构建基础查询集（只查询类型为 sub 的子网）
        queryset = Subnet.objects.filter(subnetType=Subnet.SubnetTypeChoices.SUB) \
            .prefetch_related(interface_prefetch) \
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
                'details': subnet.details,
                'interfaces': [],
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
            interfaceType="sub"
        )

    return interface


def _is_leo_special_type(value):
    return value in {"LEO", "近地卫星"}


def _parse_datetime_input(value, field_name):
    if isinstance(value, datetime):
        return value
    if not value:
        raise ValidationError(f"缺少必填字段: {field_name}")
    if isinstance(value, str):
        text = value.strip()
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            raise ValidationError(f"{field_name} 时间格式无效")
    raise ValidationError(f"{field_name} 时间格式无效")

def _validate_scene_datetime_bounds(scene, value, field_name):
    if scene is None or value is None:
        return
    if value < scene.startTime or value > scene.endTime:
        raise ValidationError(f'{field_name} must fall within the scene time range')


def _validate_scene_time_window(scene, start_time, end_time, start_field_name, end_field_name):
    if start_time >= end_time:
        raise ValidationError(f'{start_field_name} must be earlier than {end_field_name}')
    _validate_scene_datetime_bounds(scene, start_time, start_field_name)
    _validate_scene_datetime_bounds(scene, end_time, end_field_name)


def _normalize_via_points(scene, start_time, via_points):
    if via_points in [None, '']:
        return []
    if not isinstance(via_points, list):
        raise ValidationError('viaPoints must be a list')

    normalized_points = []
    previous_time = start_time
    for index, point in enumerate(via_points):
        if not isinstance(point, dict):
            raise ValidationError(f'viaPoints[{index}] must be an object')

        missing_keys = [key for key in ['lon', 'lat', 'alt', 'time'] if key not in point]
        if missing_keys:
            raise ValidationError(f'viaPoints[{index}] is missing fields: {", ".join(missing_keys)}')

        point_time = _parse_scene_datetime(point.get('time'), f'viaPoints[{index}].time')
        _validate_scene_datetime_bounds(scene, point_time, f'viaPoints[{index}].time')
        if point_time <= previous_time:
            raise ValidationError('viaPoints time must be strictly increasing and later than startTime')

        normalized_points.append({
            'lon': point.get('lon'),
            'lat': point.get('lat'),
            'alt': point.get('alt'),
            'time': point_time.isoformat(),
        })
        previous_time = point_time

    return normalized_points


def _validate_node_timeline(scene, start_time_value, via_points):
    start_time = _parse_scene_datetime(start_time_value, 'startTime')
    _validate_scene_datetime_bounds(scene, start_time, 'startTime')
    normalized_points = _normalize_via_points(scene, start_time, via_points)
    return start_time, normalized_points


def _parse_error_window(scene, start_time_value, end_time_value):
    start_time = _parse_scene_datetime(start_time_value, 'errorStartTime')
    end_time = _parse_scene_datetime(end_time_value, 'errorEndTime')
    _validate_scene_time_window(scene, start_time, end_time, 'errorStartTime', 'errorEndTime')
    return start_time, end_time



def _parse_float_input(value, field_name):
    if value in [None, '']:
        raise ValidationError(f"缺少必填字段: {field_name}")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} 必须是数字")


def _parse_int_input(value, field_name):
    if value in [None, '']:
        raise ValidationError(f"缺少必填字段: {field_name}")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} 必须是整数")


@lru_cache(maxsize=1)
def _load_orbit_math_module():
    module_path = Path(__file__).with_name("import math.py")
    spec = importlib.util.spec_from_file_location("api_import_math", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载轨道计算模块: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _calculate_leo_points(payload):
    start_dt = _parse_datetime_input(payload.get('startTime'), 'startTime')
    epoch_dt = _parse_datetime_input(payload.get('epochTime'), 'epochTime')
    step_size = _parse_float_input(payload.get('orbitStepSize'), 'orbitStepSize')
    step_count = _parse_int_input(payload.get('orbitStepCount'), 'orbitStepCount')
    inclination = _parse_float_input(payload.get('orbitInclination'), 'orbitInclination')
    arg_perigee = _parse_float_input(payload.get('orbitArgPerigee'), 'orbitArgPerigee')
    raan = _parse_float_input(payload.get('orbitRaan'), 'orbitRaan')
    mean_anomaly = _parse_float_input(payload.get('orbitMeanAnomaly'), 'orbitMeanAnomaly')
    altitude = _parse_float_input(payload.get('orbitAltitude'), 'orbitAltitude')

    if step_size <= 0:
        raise ValidationError("orbitStepSize 必须大于 0")
    if step_count <= 0:
        raise ValidationError("orbitStepCount 必须大于 0")

    orbit_math_module = _load_orbit_math_module()
    elements = {
        'a': 6378137 + altitude * 1000.0,
        'e': 0.0,
        'i': math.radians(inclination),
        'Omega': math.radians(raan),
        'omega': math.radians(arg_perigee),
        'M0': math.radians(mean_anomaly),
        'epoch': epoch_dt.isoformat(),
    }
    calculated_points = orbit_math_module.calculate_orbit_positions(
        elements=elements,
        start_time_str=start_dt.isoformat(),
        step_size_sec=step_size,
        num_steps=step_count,
    )
    if not calculated_points:
        raise ValidationError("未计算出任何轨道点")

    start_point = calculated_points[0]
    via_points = calculated_points[1:]
    orbit_payload = {
        'epochTime': epoch_dt,
        'orbitStepSize': step_size,
        'orbitStepCount': step_count,
        'orbitInclination': inclination,
        'orbitArgPerigee': arg_perigee,
        'orbitRaan': raan,
        'orbitMeanAnomaly': mean_anomaly,
        'orbitAltitude': altitude,
    }
    return start_dt, start_point, via_points, orbit_payload


@csrf_exempt
@require_http_methods(["POST"])
def calculate_leo_via_points(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        start_dt, start_point, via_points, orbit_payload = _calculate_leo_points(data)
        return JsonResponse({
            'status': 'success',
            'startTime': start_dt.isoformat(),
            'startPoint': start_point,
            'viaPoints': via_points,
            'orbit': {
                'epochTime': orbit_payload['epochTime'].isoformat(),
                'orbitStepSize': orbit_payload['orbitStepSize'],
                'orbitStepCount': orbit_payload['orbitStepCount'],
                'orbitInclination': orbit_payload['orbitInclination'],
                'orbitArgPerigee': orbit_payload['orbitArgPerigee'],
                'orbitRaan': orbit_payload['orbitRaan'],
                'orbitMeanAnomaly': orbit_payload['orbitMeanAnomaly'],
                'orbitAltitude': orbit_payload['orbitAltitude'],
            }
        }, json_dumps_params={'ensure_ascii': False})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': '无效的JSON格式'}, status=400)
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'轨道计算失败: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def add_node_list(request):
    try:
        try:
            body_unicode = request.body.decode('utf-8')
            data = json.loads(body_unicode)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            return JsonResponse({'status': 'error', 'message': f'Invalid JSON format: {str(e)}'}, status=400)

        required_fields = ['nodeName', 'nodeType']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return JsonResponse({'status': 'error', 'message': f'Missing required fields: {", ".join(missing_fields)}'}, status=400)

        scene_id = data.get('sceneId')
        scene = None
        if scene_id:
            try:
                scene = Scene.objects.get(id=scene_id)
            except Scene.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': f'Scene ID {scene_id} does not exist'}, status=404)

        with transaction.atomic():
            node = Node(
                sceneId=scene,
                nodeName=data['nodeName'],
                nodeImage=data.get('nodeImage'),
                nodeType=data['nodeType'],
                details=data.get('details'),
                specialType=data.get('specialType')
            )

            if node.nodeType == 'satellite':
                required_fields = ['eccentricity', 'argPerigee', 'inclination', 'meanAnomaly', 'meanMotion', 'raan', 'startTime']
                for field in required_fields:
                    if field not in data:
                        raise ValidationError(f'Missing satellite field: {field}')
                    if field != 'startTime':
                        setattr(node, field, data[field])
                node.startTime, _ = _validate_node_timeline(scene, data.get('startTime'), [])
            elif node.nodeType == 'normalNode':
                if _is_leo_special_type(node.specialType):
                    start_dt, start_point, via_points, orbit_payload = _calculate_leo_points(data)
                    start_dt, via_points = _validate_node_timeline(scene, start_dt, via_points)
                    node.startTime = start_dt
                    node.lon = start_point.get('lon')
                    node.lat = start_point.get('lat')
                    node.alt = start_point.get('alt')
                    node.viaPoints = via_points
                    node.epochTime = orbit_payload['epochTime']
                    node.orbitStepSize = orbit_payload['orbitStepSize']
                    node.orbitStepCount = orbit_payload['orbitStepCount']
                    node.orbitInclination = orbit_payload['orbitInclination']
                    node.orbitArgPerigee = orbit_payload['orbitArgPerigee']
                    node.orbitRaan = orbit_payload['orbitRaan']
                    node.orbitMeanAnomaly = orbit_payload['orbitMeanAnomaly']
                    node.orbitAltitude = orbit_payload['orbitAltitude']
                else:
                    required_fields = ['lon', 'lat', 'alt', 'startTime']
                    for field in required_fields:
                        if field not in data:
                            raise ValidationError(f'Missing normal node field: {field}')
                    start_dt, via_points = _validate_node_timeline(scene, data.get('startTime'), data.get('viaPoints'))
                    node.lon = data.get('lon')
                    node.lat = data.get('lat')
                    node.alt = data.get('alt')
                    node.startTime = start_dt
                    node.viaPoints = via_points
            else:
                raise ValidationError('Invalid node type')

            node.full_clean()
            node.save()

            if scene_id:
                try:
                    create_default_interface(node)
                except Exception as e:
                    raise ValidationError(f'Failed to create default interface: {str(e)}')

        return JsonResponse({'status': 'success'})
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
@require_http_methods(["GET"])
@csrf_exempt
def get_node_list(request):
    try:
        # 获取查询参数
        scene_id = request.GET.get('sceneId', '')
        node_type = request.GET.get('nodeType', '')
        node_name = request.GET.get('nodeName', '')
        try:
            page_size = int(request.GET.get('size', 10) or 10)
        except ValueError:
            page_size = 10

        try:
            page_number = int(request.GET.get('page', 1) or 1)
        except ValueError:
            page_number = 1
        # 构建查询条件
        query = Q()
        if scene_id:
            query &= Q(sceneId__id=scene_id)
        if node_type:
            query &= Q(nodeType=node_type)
        if node_name:
            query &= Q(nodeName__icontains=node_name)

        # 获取查询结果并分页
        nodes = Node.objects.filter(query).order_by('id')
        paginator = Paginator(nodes, page_size)
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            return JsonResponse({'status': 'error', 'message': '页码必须是整数'}, status=400)
        except EmptyPage:
            return JsonResponse({'status': 'error', 'message': '页码超出范围'}, status=400)
        if scene_id:
            reorder_interfaces_by_scene(scene_id)#给接口排序，sub类的接口在前
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
                    # 添加 isHideEnable 字段
                    detail_obj["isHideEnable"] = (interface.interfaceType == Interface.InterfaceTypeChoices.LINK)
                    detail_obj.setdefault("Network", {})
                    detail_obj['Network']['IPv4Address'] = interface.interfaceIp
                    detail_obj['Network']['IPv4SubnetMask'] = interface.subnetMask
                    # 获取所属链路信息
                    links = interface.links
                    if links:
                        link = links[0]
                        # 原始类型（可能是中文）
                        db_type = getattr(link, "linkType", None)
                        # 中英文映射
                        type_map = {
                            "有线": "wired",
                            "无线": "wireless"
                        }
                        detail_obj["linkType"] = type_map.get(db_type, db_type)  # 如果不是有线/无线，保持原值
                        # linkConfig 原样写入
                        detail_obj["linkConfig"] = getattr(link, "linkConfig", None)
                    else:
                        detail_obj["linkConfig"] = None
                        detail_obj["linkType"] = None

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
                'epochTime': node.epochTime.isoformat() if node.epochTime else None,
                'orbitStepSize': node.orbitStepSize,
                'orbitStepCount': node.orbitStepCount,
                'orbitInclination': node.orbitInclination,
                'orbitArgPerigee': node.orbitArgPerigee,
                'orbitRaan': node.orbitRaan,
                'orbitMeanAnomaly': node.orbitMeanAnomaly,
                'orbitAltitude': node.orbitAltitude,
                'viaPoints': node.viaPoints if node.viaPoints else [],
                'specialType':node.specialType,
                # 'details':node.details
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
        node.nodeName = data.get('nodeName', node.nodeName)
        node.nodeImage = data.get('nodeImage', node.nodeImage)
        node.nodeType = data.get('nodeType', node.nodeType)
        node.specialType = data.get('specialType', node.specialType)

        scene_id = data.get('sceneId')
        if scene_id is not None:
            try:
                scene = Scene.objects.get(id=scene_id)
                node.sceneId = scene
            except Scene.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Scene not found'}, status=404)
        scene = node.sceneId

        if node.nodeType == 'satellite':
            node.eccentricity = data.get('eccentricity', node.eccentricity)
            node.argPerigee = data.get('argPerigee', node.argPerigee)
            node.inclination = data.get('inclination', node.inclination)
            node.meanAnomaly = data.get('meanAnomaly', node.meanAnomaly)
            node.meanMotion = data.get('meanMotion', node.meanMotion)
            node.raan = data.get('raan', node.raan)
            start_time_value = data.get('startTime', node.startTime.isoformat() if isinstance(node.startTime, datetime) else node.startTime)
            node.startTime, _ = _validate_node_timeline(scene, start_time_value, [])
        elif node.nodeType == 'normalNode':
            if _is_leo_special_type(node.specialType):
                calc_payload = {
                    'startTime': data.get('startTime', node.startTime.isoformat() if isinstance(node.startTime, datetime) else node.startTime),
                    'epochTime': data.get('epochTime', node.epochTime.isoformat() if isinstance(node.epochTime, datetime) else node.epochTime),
                    'orbitStepSize': data.get('orbitStepSize', node.orbitStepSize),
                    'orbitStepCount': data.get('orbitStepCount', node.orbitStepCount),
                    'orbitInclination': data.get('orbitInclination', node.orbitInclination),
                    'orbitArgPerigee': data.get('orbitArgPerigee', node.orbitArgPerigee),
                    'orbitRaan': data.get('orbitRaan', node.orbitRaan),
                    'orbitMeanAnomaly': data.get('orbitMeanAnomaly', node.orbitMeanAnomaly),
                    'orbitAltitude': data.get('orbitAltitude', node.orbitAltitude),
                }
                start_dt, start_point, via_points, orbit_payload = _calculate_leo_points(calc_payload)
                start_dt, via_points = _validate_node_timeline(scene, start_dt, via_points)
                node.startTime = start_dt
                node.lon = start_point.get('lon')
                node.lat = start_point.get('lat')
                node.alt = start_point.get('alt')
                node.viaPoints = via_points
                node.epochTime = orbit_payload['epochTime']
                node.orbitStepSize = orbit_payload['orbitStepSize']
                node.orbitStepCount = orbit_payload['orbitStepCount']
                node.orbitInclination = orbit_payload['orbitInclination']
                node.orbitArgPerigee = orbit_payload['orbitArgPerigee']
                node.orbitRaan = orbit_payload['orbitRaan']
                node.orbitMeanAnomaly = orbit_payload['orbitMeanAnomaly']
                node.orbitAltitude = orbit_payload['orbitAltitude']
            else:
                lon = data.get('lon', node.lon)
                lat = data.get('lat', node.lat)
                alt = data.get('alt', node.alt)
                start_time_value = data.get('startTime', node.startTime.isoformat() if isinstance(node.startTime, datetime) else node.startTime)
                via_points_value = data['viaPoints'] if 'viaPoints' in data else node.viaPoints
                start_dt, via_points = _validate_node_timeline(scene, start_time_value, via_points_value)
                node.lon = lon
                node.lat = lat
                node.alt = alt
                node.startTime = start_dt
                node.viaPoints = via_points
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid node type'}, status=400)

        if 'details' in data:
            details = data['details']
            if not isinstance(details, list):
                return JsonResponse({'status': 'error', 'message': 'details must be a list'}, status=400)
            interfaces = list(node.interfaces.all().order_by('interfaceIndex'))
            if len(details) != len(interfaces):
                return JsonResponse({'status': 'error', 'message': f'details count ({len(details)}) does not match interface count ({len(interfaces)})'}, status=400)
            for i, interface in enumerate(interfaces):
                interface.detail = details[i]
                interface.save(update_fields=['detail'])
            node.details = details

        node.save()
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format'}, status=400)
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
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
@csrf_exempt  # 可选：如果你前端不使用 CSRF token，可保留；使用了就可以删掉
def add_configuration_list(request):
    """
    新建业务配置（支持 CBR/FTP/TRAFFIC-GEN/HTTP 类型）
    """
    serializer = ConfigurationSerializer(data=request.data)
    if serializer.is_valid():
        config = serializer.save()
        return Response({
            "message": "创建成功",
            "data": ConfigurationSerializer(config).data
        }, status=status.HTTP_201_CREATED)
    return Response({
        "message": "参数错误",
        "errors": serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@require_http_methods(["GET"])
def get_configuration_list(request):
    page_size = int(request.GET.get('size', 10))
    page_number = int(request.GET.get('page', 1))
    business_name = request.GET.get('businessName', '')
    source_node_name = request.GET.get('sourceNodeName', '')
    destination_node_name = request.GET.get('destinationNodeName', '')
    business_type = request.GET.get('businessType', '')
    normalized_business_type = normalize_business_type(business_type)
    scene_id = request.GET.get('sceneId', '')

    # 构建查询条件
    query = Q()
    if business_name:
        query &= Q(businessName__icontains=business_name)
    if source_node_name:
        query &= Q(sourceNodeId__nodeName__icontains=source_node_name)
    if destination_node_name:
        query &= Q(destinationNodeId__nodeName__icontains=destination_node_name)
    if business_type:
        query &= (
            Q(businessType__icontains=business_type) |
            Q(businessType__icontains=normalized_business_type)
        )
    if scene_id:
        query &= Q(sceneId=scene_id)

    # 获取查询结果并分页
    configurations = Configuration.objects.filter(query).order_by('businessName')
    paginator = Paginator(configurations, page_size)
    page_obj = paginator.get_page(page_number)

    # 准备要返回的数据
    configuration_list = [{
        'sceneId': config.sceneId.id,
        'id': config.id,
        'businessName': config.businessName,
        'sourceNodeId': config.sourceNodeId.id if config.sourceNodeId else None,
        'sourceNodeName': config.sourceNodeId.nodeName if config.sourceNodeId else '',
        'destinationNodeId': config.destinationNodeId.id if config.destinationNodeId else None,
        'destinationNodeName': config.destinationNodeId.nodeName if config.destinationNodeId else '',
        'cbrStartTime': config.cbrStartTime,
        'cbrEndTime': config.cbrEndTime,
        'cbrSendInterval': config.cbrSendInterval,
        'cbrPacketSize': config.cbrPacketSize,
        'cbrPrecedence': config.cbrPrecedence,
        'TransferType': config.TransferType,
        'ftpStartTime': config.ftpStartTime,
        'ftpPacketCount': config.ftpPacketCount,
        'tgStartTime': config.tgStartTime,
        'tgDurationTime': config.tgDurationTime,
        'tgPacketSize': config.tgPacketSize,
        'tgSendInterval': config.tgSendInterval,
        'clientId': config.clientId.id if config.clientId else None,
        'clientName': config.clientId.nodeName if config.clientId else '',
        'serverList': config.serverList,
        'httpStartTime': config.httpStartTime,
        'httpThreshTime': config.httpThreshTime,
        'poissonStartTime': config.poissonStartTime,
        'poissonEndTime': config.poissonEndTime,
        'poissonMeanInterval': config.poissonMeanInterval,
        'poissonPacketSize': config.poissonPacketSize,
        'broadcastDest': config.broadcastDest,
        'broadcastTransportType': config.broadcastTransportType,
        'broadcastAppType': config.broadcastAppType,
        'broadcastLifeTime': config.broadcastLifeTime,
        'broadcastStartTime': config.broadcastStartTime,
        'broadcastInterval': config.broadcastInterval,
        'broadcastFragmentSize': config.broadcastFragmentSize,
        'broadcastFragmentNum': config.broadcastFragmentNum,
        'multicastDestination': config.multicastDestination,
        'multicastItemsToSend': config.multicastItemsToSend,
        'multicastItemSize': config.multicastItemSize,
        'multicastInterval': config.multicastInterval,
        'multicastStartTime': config.multicastStartTime,
        'multicastEndTime': config.multicastEndTime,
        'businessType': normalize_business_type(config.businessType)
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

    data = json.loads(request.body)

    # 更新通用字段
    if 'businessName' in data:
        config.businessName = data.get('businessName', config.businessName)

    if 'sourceNodeId' in data:
        source_node_id = data.get('sourceNodeId')
        config.sourceNodeId = Node.objects.get(id=source_node_id) if source_node_id else None

    if 'destinationNodeId' in data:
        destination_node_id = data.get('destinationNodeId')
        config.destinationNodeId = Node.objects.get(id=destination_node_id) if destination_node_id else None

    # 不允许修改 businessType，只使用原有值判断更新内容
    business_type = normalize_business_type(config.businessType)

    if business_type == 'CBR':
        if 'cbrStartTime' in data:
            config.cbrStartTime = data.get('cbrStartTime')
        if 'cbrEndTime' in data:
            config.cbrEndTime = data.get('cbrEndTime')
        if 'cbrSendInterval' in data:
            config.cbrSendInterval = data.get('cbrSendInterval')
        if 'cbrPacketSize' in data:
            config.cbrPacketSize = data.get('cbrPacketSize')
        if 'cbrPrecedence' in data:
            config.cbrPrecedence = data.get('cbrPrecedence')
        if 'TransferType' in data:
            config.TransferType = data.get('TransferType')
    elif business_type == 'FTP':
        if 'ftpStartTime' in data:
            config.ftpStartTime = data.get('ftpStartTime')
        if 'ftpPacketCount' in data:
            config.ftpPacketCount = data.get('ftpPacketCount')

    elif business_type == 'TRAFFIC-GEN':
        if 'tgStartTime' in data:
            config.tgStartTime = data.get('tgStartTime')
        if 'tgDurationTime' in data:
            config.tgDurationTime = data.get('tgDurationTime')
        if 'tgPacketSize' in data:
            config.tgPacketSize = data.get('tgPacketSize')
        if 'tgSendInterval' in data:
            config.tgSendInterval = data.get('tgSendInterval')

    elif business_type == 'HTTP':
        if 'clientId' in data:
            client_id = data.get('clientId')
            config.clientId = Node.objects.get(id=client_id) if client_id else None
        if 'serverList' in data:
            config.serverList = data.get('serverList')
        if 'httpStartTime' in data:
            config.httpStartTime = data.get('httpStartTime')
        if 'httpThreshTime' in data:
            config.httpThreshTime = data.get('httpThreshTime')

    elif business_type == 'POISSON':
        if 'poissonStartTime' in data:
            config.poissonStartTime = data.get('poissonStartTime')
        if 'poissonEndTime' in data:
            config.poissonEndTime = data.get('poissonEndTime')
        if 'poissonMeanInterval' in data:
            config.poissonMeanInterval = data.get('poissonMeanInterval')
        if 'poissonPacketSize' in data:
            config.poissonPacketSize = data.get('poissonPacketSize')

    elif business_type == 'BROADCAST':
        if 'broadcastDest' in data:
            config.broadcastDest = data.get('broadcastDest')
        if 'broadcastTransportType' in data:
            config.broadcastTransportType = data.get('broadcastTransportType')
        if 'broadcastAppType' in data:
            config.broadcastAppType = data.get('broadcastAppType')
        if 'broadcastLifeTime' in data:
            config.broadcastLifeTime = data.get('broadcastLifeTime')
        if 'broadcastStartTime' in data:
            config.broadcastStartTime = data.get('broadcastStartTime')
        if 'broadcastInterval' in data:
            config.broadcastInterval = data.get('broadcastInterval')
        if 'broadcastFragmentSize' in data:
            config.broadcastFragmentSize = data.get('broadcastFragmentSize')
        if 'broadcastFragmentNum' in data:
            config.broadcastFragmentNum = data.get('broadcastFragmentNum')

    elif business_type == 'MULTICAST':
        if 'multicastDestination' in data:
            config.multicastDestination = data.get('multicastDestination')
        if 'multicastItemsToSend' in data:
            config.multicastItemsToSend = data.get('multicastItemsToSend')
        if 'multicastItemSize' in data:
            config.multicastItemSize = data.get('multicastItemSize')
        if 'multicastInterval' in data:
            config.multicastInterval = data.get('multicastInterval')
        if 'multicastStartTime' in data:
            config.multicastStartTime = data.get('multicastStartTime')
        if 'multicastEndTime' in data:
            config.multicastEndTime = data.get('multicastEndTime')

    if business_type == 'CBR':
        _validate_scene_time_window(
            config.sceneId,
            _parse_datetime_input(config.cbrStartTime, 'cbrStartTime'),
            _parse_datetime_input(config.cbrEndTime, 'cbrEndTime'),
            'cbrStartTime',
            'cbrEndTime',
        )
    elif business_type == 'FTP' and config.ftpStartTime:
        _validate_scene_datetime_bounds(
            config.sceneId,
            _parse_datetime_input(config.ftpStartTime, 'ftpStartTime'),
            'ftpStartTime',
        )
    elif business_type == 'TRAFFIC-GEN' and config.tgStartTime:
        _validate_scene_datetime_bounds(
            config.sceneId,
            _parse_datetime_input(config.tgStartTime, 'tgStartTime'),
            'tgStartTime',
        )
    elif business_type == 'HTTP' and config.httpStartTime:
        _validate_scene_datetime_bounds(
            config.sceneId,
            _parse_datetime_input(config.httpStartTime, 'httpStartTime'),
            'httpStartTime',
        )

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
        bandwidth = data.get('bandwidth',0)
        bandwidth = float(bandwidth) if bandwidth not in [None, ""] else 0.0
        bandwidth = bandwidth * 10 ** 6
        packet_header_size = data.get('packetHeaderSize')
        link_name = data.get('linkName') or f"{source_node_name}到{dest_node_name}({link_type})"
        subnet_ip = data.get('subnetIp')
        subnet_mask = data.get('subnetMask')
        link_config = data.get("linkConfig")
        if link_config is None:
            link_config = True
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
                transmissionSpeed=transmission_speed if link_type == '无线' else None,
                linkConfig = link_config
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
        page_size = int(request.GET.get('size', 40))
        reorder_interfaces_by_scene(scene_id)  # 给接口排序，sub类的接口在前
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
                'bandwidth': link.bandwidth / 10 ** 6,
                'packetHeaderSize': link.packetHeaderSize,
                'transmissionDelay': link.transmissionDelay,
                'packetLossRate': link.packetLossRate,
                'transmissionSpeed': link.transmissionSpeed,
                'linkConfig':link.linkConfig,
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
            link_Config = data.get('linkConfig',link.linkConfig)
            # 新增：根据链路类型获取特有属性
            bandwidth = data.get('bandwidth')
            bandwidth = bandwidth * 10 ** 6
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

            #注释掉子网及接口修改，不允许修改。
            # 处理子网变更
            # subnet = link.subnet
            # subnet_changed = False
            #
            # # 如果前端传了子网信息
            # if subnet_ip and subnet_mask:
            #     # 检查子网是否已存在
            #     subnet, created = Subnet.objects.get_or_create(
            #         sceneId=scene,
            #         subnetIp=subnet_ip,
            #         subnetMask=subnet_mask,
            #         defaults={'subnetName': f"子网 {subnet_ip}/{subnet_mask}"},
            #         subnetType="link"
            #     )
            #     # 如果子网是新创建的或不同于原来的子网
            #     if created or subnet != link.subnet:
            #         subnet_changed = True
            # else:
            #     # 如果没有传递子网信息，使用原来的子网
            #     subnet = link.subnet
            #     subnet_ip = subnet.subnetIp
            #     subnet_mask = subnet.subnetMask
            #
            # # 记录节点是否变更
            # nodes_changed = link.sourceNodeId != source_node or link.destinationNodeId != dest_node

            # 更新核心字段
            link.sceneId = scene
            link.linkName = link_name
            link.linkType = link_type
            link.bandwidth = bandwidth
            link.packetHeaderSize = packet_header_size
            link.transmissionDelay = transmission_delay
            link.packetLossRate = packet_loss_rate
            link.transmissionSpeed = transmission_speed
            # link.subnetIp = subnet_ip
            # link.subnetMask = subnet_mask
            # link.sourceNodeId = source_node
            # link.destinationNodeId = dest_node
            # link.subnet = subnet
            link.linkConfig = link_Config #判断是否需要从接口单独配置参数。

            # # 处理接口变更
            # interface_update_needed = subnet_changed or nodes_changed
            #
            # # 如果前端传了接口IP
            # if source_interface_ip or dest_interface_ip:
            #     # 验证源接口IP
            #     if source_interface_ip:
            #         # 检查IP是否已被占用（排除当前接口）
            #         if Interface.objects.filter(
            #                 interfaceIp=source_interface_ip,
            #                 subnetMask=subnet_mask,
            #
            #         ).exclude(id=link.sourceInterface.id).exists():
            #             return JsonResponse(
            #                 {'status': 'error', 'message': f'源IP地址 {source_interface_ip} 已被占用'},
            #                 status=400
            #             )
            #
            #         # 验证IP是否在子网内
            #         try:
            #             network = ipaddress.IPv4Network(f"{subnet_ip}/{subnet_mask}", strict=False)
            #             ip_address = ipaddress.IPv4Address(source_interface_ip)
            #             if ip_address not in network:
            #                 return JsonResponse(
            #                     {'status': 'error',
            #                      'message': f'源IP地址 {source_interface_ip} 不在子网 {subnet_ip}/{subnet_mask} 内'},
            #                     status=400
            #                 )
            #         except ValueError:
            #             return JsonResponse(
            #                 {'status': 'error', 'message': '无效的子网配置'},
            #                 status=400
            #             )
            #
            #         link.sourceInterface.interfaceIp = source_interface_ip
            #         interface_update_needed = True
            #
            #     # 验证目的接口IP
            #     if dest_interface_ip:
            #         # 检查IP是否已被占用（排除当前接口）
            #         if Interface.objects.filter(
            #                 interfaceIp=dest_interface_ip,
            #                 subnetMask=subnet_mask
            #         ).exclude(id=link.destinationInterface.id).exists():
            #             return JsonResponse(
            #                 {'status': 'error', 'message': f'目的IP地址 {dest_interface_ip} 已被占用'},
            #                 status=400
            #             )
            #
            #         # 验证IP是否在子网内
            #         try:
            #             network = ipaddress.IPv4Network(f"{subnet_ip}/{subnet_mask}", strict=False)
            #             ip_address = ipaddress.IPv4Address(dest_interface_ip)
            #             if ip_address not in network:
            #                 return JsonResponse(
            #                     {'status': 'error',
            #                      'message': f'目的IP地址 {dest_interface_ip} 不在子网 {subnet_ip}/{subnet_mask} 内'},
            #                     status=400
            #                 )
            #         except ValueError:
            #             return JsonResponse(
            #                 {'status': 'error', 'message': '无效的子网配置'},
            #                 status=400
            #             )
            #
            #         link.destinationInterface.interfaceIp = dest_interface_ip
            #         interface_update_needed = True
            #
            # # 如果没有传接口IP且需要更新接口
            # elif interface_update_needed:
            #     # 获取子网中已分配的IP地址
            #     allocated_ips = set(
            #         Interface.objects.filter(subnet=subnet)
            #         .exclude(interfaceIp__isnull=True)
            #         .values_list('interfaceIp', flat=True)
            #     )
            #
            #     # 排除当前链路的接口IP
            #     if link.sourceInterface.interfaceIp:
            #         allocated_ips.discard(link.sourceInterface.interfaceIp)
            #     if link.destinationInterface.interfaceIp:
            #         allocated_ips.discard(link.destinationInterface.interfaceIp)
            #
            #     # 创建网络对象
            #     try:
            #         network = ipaddress.IPv4Network(f"{subnet_ip}/{subnet_mask}", strict=False)
            #     except ValueError as e:
            #         return JsonResponse(
            #             {'status': 'error', 'message': f'无效的子网参数: {str(e)}'},
            #             status=400
            #         )
            #
            #     # 找出两个可用的最小IP
            #     available_ips = []
            #     for ip in network.hosts():
            #         ip_str = str(ip)
            #         if ip_str not in allocated_ips:
            #             available_ips.append(ip_str)
            #             if len(available_ips) == 2:
            #                 break
            #
            #     if len(available_ips) < 2:
            #         return JsonResponse(
            #             {'status': 'error', 'message': f'子网 {subnet_ip}/{subnet_mask} 中没有足够的可用IP地址'},
            #             status=400
            #         )
            #
            #     source_ip = available_ips[0]
            #     dest_ip = available_ips[1]
            #
            #     link.sourceInterface.interfaceIp = source_ip
            #     link.destinationInterface.interfaceIp = dest_ip
            #
            # # 更新接口的其他属性
            # if interface_update_needed:
            #     link.sourceInterface.node = source_node
            #     link.sourceInterface.subnet = subnet
            #     link.sourceInterface.subnetMask = subnet_mask
            #     link.sourceInterface.interfaceType = "link"
            #     link.sourceInterface.save()
            #
            #     link.destinationInterface.node = dest_node
            #     link.destinationInterface.subnet = subnet
            #     link.destinationInterface.subnetMask = subnet_mask
            #     link.destinationInterface.interfaceType = "link"
            #     link.destinationInterface.save()

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
                # interfaces = list(node.interfaces.order_by('id'))
                # Interface.objects.bulk_update(
                #     [Interface(id=i.id, interfaceIndex=idx) for idx, i in enumerate(interfaces)],
                #     ['interfaceIndex']
                # )
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


'''
节点故障表
'''


@require_http_methods(["POST"])
def add_node_error_list(request):
    data = json.loads(request.body)
    scene_id = data.get('sceneId')
    node_id = data.get('nodeId')
    error_start_time = data.get('errorStartTime')
    error_end_time = data.get('errorEndTime')
    interface_index = data.get('interfaceIndex')

    try:
        scene = Scene.objects.get(id=scene_id)
    except Scene.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Scene not found'}, status=404)

    try:
        node = Node.objects.get(id=node_id)
    except Node.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Node not found'}, status=404)

    if node.sceneId_id != scene.id:
        return JsonResponse({'status': 'error', 'message': 'nodeId does not belong to the selected scene'}, status=400)

    interface = None
    if interface_index is not None:
        try:
            interface = Interface.objects.get(node_id=node_id, interfaceIndex=interface_index)
        except Interface.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'Interface index {interface_index} does not exist on the node'}, status=404)

    try:
        error_start_time, error_end_time = _parse_error_window(scene, error_start_time, error_end_time)
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    form = ErrorForm({
        'sceneId': scene_id,
        'nodeId': node_id,
        'interfaceId': interface.id if interface else None,
        'errorStartTime': error_start_time,
        'errorEndTime': error_end_time,
    })

    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'success'})
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
    node_id = request.GET.get('nodeId', '')  # 节点ID查询参数
    interface_index = request.GET.get('interfaceIndex', '')  # 接口序号查询参数
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
    if node_id:  # 节点ID过滤条件
        query &= Q(nodeId__id=node_id)
    if interface_index:  # 接口序号过滤条件
        query &= Q(interfaceId__interfaceIndex=interface_index)

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
        'errorEndTime': error.errorEndTime,
        'interfaceIndex': error.interfaceId.interfaceIndex if error.interfaceId else None,
        'interfaceIp': str(error.interfaceId.interfaceIp) if error.interfaceId and error.interfaceId.interfaceIp else None,
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


@require_http_methods(["GET"])
def get_channel_names(request):
    scene_id = request.GET.get('sceneId')
    if not scene_id:
        return JsonResponse({'status': 'error', 'message': 'Missing sceneId'}, status=400)

    try:
        scene = Scene.objects.get(id=scene_id)
    except Scene.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Scene not found'}, status=404)

    _, channel_names, _ = _get_scene_channel_data(scene)
    return JsonResponse({
        'status': 'success',
        'channelNames': channel_names,
        'channelCount': len(channel_names)
    })


@require_http_methods(["POST"])
@csrf_exempt
def add_link_error_list(request):
    data = json.loads(request.body)
    scene_id = data.get('sceneId')
    link_id = data.get('linkId')
    error_start_time = data.get('errorStartTime')
    error_end_time = data.get('errorEndTime')

    try:
        scene = Scene.objects.get(id=scene_id)
    except Scene.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Scene not found'}, status=404)

    try:
        link = Link.objects.get(id=link_id)
    except Link.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Link not found'}, status=404)

    if link.sceneId_id != scene.id:
        return JsonResponse({'status': 'error', 'message': 'linkId does not belong to the selected scene'}, status=400)

    try:
        error_start_time, error_end_time = _parse_error_window(scene, error_start_time, error_end_time)
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    form = LinkErrorForm({
        'sceneId': scene.id,
        'linkId': link.id,
        'errorStartTime': error_start_time,
        'errorEndTime': error_end_time,
    })

    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


@require_http_methods(["GET"])
def get_link_error_list(request):
    try:
        page_size = int(request.GET.get('size', 10))
        page_number = int(request.GET.get('page', 1))
        link_name = request.GET.get('linkName', '')
        source_node_name = request.GET.get('sourceNodeName', '')
        destination_node_name = request.GET.get('destinationNodeName', '')
        scene_id = request.GET.get('sceneId', '')

        query = Q()
        if scene_id:
            try:
                scene = Scene.objects.get(id=scene_id)
                query &= Q(sceneId=scene)
            except Scene.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': f'Scene ID {scene_id} does not exist'}, status=400)
        if link_name:
            query &= Q(linkId__linkName__icontains=link_name)
        if source_node_name:
            query &= Q(linkId__sourceNodeId__nodeName__icontains=source_node_name)
        if destination_node_name:
            query &= Q(linkId__destinationNodeId__nodeName__icontains=destination_node_name)

        link_errors = LinkError.objects.filter(query).select_related(
            'linkId__sourceNodeId',
            'linkId__destinationNodeId',
            'sceneId'
        ).order_by('-errorStartTime')

        paginator = Paginator(link_errors, page_size)
        page_obj = paginator.get_page(page_number)
        link_error_list = [
            {
                'id': error.id,
                'sceneId': error.sceneId.id,
                'sceneName': error.sceneId.sceneName,
                'linkId': error.linkId.id,
                'linkName': error.linkId.linkName,
                'sourceNodeId': error.linkId.sourceNodeId.id,
                'sourceNodeName': error.linkId.sourceNodeId.nodeName,
                'destinationNodeId': error.linkId.destinationNodeId.id,
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
        return JsonResponse({'status': 'error', 'message': f'Parameter error: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Server error: {str(e)}'}, status=500)


@require_http_methods(["DELETE"])
def delete_link_error_list(request, link_error_id):
    try:
        link_error = LinkError.objects.get(id=link_error_id)
        link_error.delete()
        return JsonResponse({'status': 'success'})
    except LinkError.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Link error not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["PUT"])
def edit_link_error_list(request, link_error_id):
    data = json.loads(request.body)
    link_id = data.get('linkId')
    error_start_time = data.get('errorStartTime')
    error_end_time = data.get('errorEndTime')

    try:
        link_error = LinkError.objects.get(id=link_error_id)
    except LinkError.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Link error not found'}, status=404)

    scene = link_error.sceneId
    if link_id:
        try:
            link = Link.objects.get(id=link_id)
        except Link.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Link not found'}, status=404)
        if link.sceneId_id != scene.id:
            return JsonResponse({'status': 'error', 'message': 'linkId does not belong to this scene'}, status=400)
        link_error.linkId = link

    start_value = error_start_time if error_start_time is not None else link_error.errorStartTime
    end_value = error_end_time if error_end_time is not None else link_error.errorEndTime
    try:
        parsed_start_time, parsed_end_time = _parse_error_window(scene, start_value, end_value)
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    link_error.errorStartTime = parsed_start_time
    link_error.errorEndTime = parsed_end_time
    link_error.save()
    return JsonResponse({'status': 'success'})


@csrf_exempt
@require_http_methods(["PUT"])
def edit_node_error_list(request, node_error_id):
    data = json.loads(request.body)
    node_id = data.get('nodeId')
    error_start_time = data.get('errorStartTime')
    error_end_time = data.get('errorEndTime')
    interface_index = data.get('interfaceIndex')

    try:
        node_error = Error.objects.get(id=node_error_id)
    except Error.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Node error not found'}, status=404)

    scene = node_error.sceneId
    if node_id:
        try:
            node = Node.objects.get(id=node_id)
        except Node.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Node not found'}, status=404)
        if node.sceneId_id != scene.id:
            return JsonResponse({'status': 'error', 'message': 'nodeId does not belong to this scene'}, status=400)
        node_error.nodeId = node

    if 'interfaceIndex' in data:
        if interface_index is not None:
            try:
                interface = Interface.objects.get(node_id=node_error.nodeId_id, interfaceIndex=interface_index)
            except Interface.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': f'Interface index {interface_index} does not exist on the node'}, status=404)
            node_error.interfaceId = interface
        else:
            node_error.interfaceId = None

    start_value = error_start_time if error_start_time is not None else node_error.errorStartTime
    end_value = error_end_time if error_end_time is not None else node_error.errorEndTime
    try:
        parsed_start_time, parsed_end_time = _parse_error_window(scene, start_value, end_value)
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    node_error.errorStartTime = parsed_start_time
    node_error.errorEndTime = parsed_end_time
    node_error.save()
    return JsonResponse({'status': 'success'})


@csrf_exempt
@require_http_methods(["POST"])
def add_node_template_list(request):
    try:
        data = json.loads(request.body)
        template_name = data.get('templateName')
        template_type = data.get('templateType')
        template_info = data.get('templateInfo')

        if not template_name or not template_type or not template_info:
            return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)
        if NodeTemplate.objects.filter(templateName=template_name).exists():
            return JsonResponse({'status': 'error', 'message': 'Template name already exists'}, status=400)

        new_template = NodeTemplate(templateName=template_name, templateType=template_type, templateInfo=template_info)
        new_template.save()
        return JsonResponse({'status': 'success', 'message': 'Template added successfully'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
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
                    "is_default": interface.is_default
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
        print('interface_ip:{}', interface_ip, mapping.sceneId.id)
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

STATIC_ROUTE_PROTOCOL = 'NONE'
STATIC_ROUTE_UPLOAD_FIELD = 'STATIC-ROUTE'
STATIC_ROUTE_FOLDER_NAME = 'staticroute'
SCENE_NAMED_FILE_SUFFIXES = ('.config', '.app', '.nodes', '.fault', '.display')


def _parse_interface_detail_json(detail):
    if isinstance(detail, dict):
        return detail
    if isinstance(detail, str):
        try:
            parsed = json.loads(detail)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _get_interface_routing_protocol(interface):
    detail = _parse_interface_detail_json(interface.detail)
    routing_detail = detail.get('Routing', {})
    if not isinstance(routing_detail, dict):
        return ''

    value = routing_detail.get('ROUTING-PROTOCOL-IPv4')
    if value in (None, ''):
        value = routing_detail.get('RoutingProtocolIPv4')
    if value in (None, ''):
        return ''
    return str(value).strip()


def _resolve_scene_folder_path(scene):
    scene_root = _get_scene_files_root().resolve(strict=False)
    scene_folder = (scene_root / scene.sceneName).resolve(strict=False)

    try:
        scene_folder.relative_to(scene_root)
    except ValueError as exc:
        raise ValueError(f'非法场景目录: {scene.sceneName}') from exc

    return scene_folder


def _resolve_scene_folder_by_name(scene_name):
    scene_root = _get_scene_files_root().resolve(strict=False)
    scene_folder = (scene_root / scene_name).resolve(strict=False)

    try:
        scene_folder.relative_to(scene_root)
    except ValueError as exc:
        raise ValueError(f'非法场景目录: {scene_name}') from exc

    return scene_root, scene_folder


def _rename_scene_directory_and_files(old_scene_name, new_scene_name):
    if old_scene_name == new_scene_name:
        return

    scene_root, old_scene_folder = _resolve_scene_folder_by_name(old_scene_name)
    _, new_scene_folder = _resolve_scene_folder_by_name(new_scene_name)

    if not old_scene_folder.exists():
        return

    if not old_scene_folder.is_dir():
        raise ValueError(f'原场景目录不是文件夹: {old_scene_name}')

    if new_scene_folder.exists():
        raise ValueError(f'目标场景目录已存在: {new_scene_name}')

    renamed_files = []
    directory_renamed = False

    try:
        old_scene_folder.rename(new_scene_folder)
        directory_renamed = True

        for suffix in SCENE_NAMED_FILE_SUFFIXES:
            old_file = (new_scene_folder / f'{old_scene_name}{suffix}').resolve(strict=False)
            new_file = (new_scene_folder / f'{new_scene_name}{suffix}').resolve(strict=False)

            try:
                old_file.relative_to(new_scene_folder)
                new_file.relative_to(new_scene_folder)
            except ValueError as exc:
                raise ValueError(f'场景文件路径非法: {suffix}') from exc

            if not old_file.exists():
                continue

            if new_file.exists():
                raise ValueError(f'目标场景文件已存在: {new_file.name}')

            old_file.rename(new_file)
            renamed_files.append((old_file, new_file))

    except Exception as exc:
        for old_file, new_file in reversed(renamed_files):
            if new_file.exists() and not old_file.exists():
                new_file.rename(old_file)

        if directory_renamed and new_scene_folder.exists() and not old_scene_folder.exists():
            new_scene_folder.rename(old_scene_folder)

        raise ValueError(f'场景改名失败: {exc}') from exc


def _resolve_static_route_directory(scene, create=False):
    scene_folder = _resolve_scene_folder_path(scene)
    static_route_dir = (scene_folder / STATIC_ROUTE_FOLDER_NAME).resolve(strict=False)

    try:
        static_route_dir.relative_to(scene_folder)
    except ValueError as exc:
        raise ValueError(f'非法静态路由目录: {scene.sceneName}') from exc

    if create:
        static_route_dir.mkdir(parents=True, exist_ok=True)

    return static_route_dir


def _resolve_static_route_file(scene, require_exists=False):
    static_route_dir = _resolve_static_route_directory(scene, create=False)
    if not static_route_dir.exists() or not static_route_dir.is_dir():
        if require_exists:
            raise FileNotFoundError(f'场景 {scene.sceneName} 未上传静态路由文件')
        return None

    matched_files = sorted(
        path.resolve(strict=False)
        for path in static_route_dir.iterdir()
        if path.is_file()
    )

    if not matched_files:
        if require_exists:
            raise FileNotFoundError(f'场景 {scene.sceneName} 未上传静态路由文件')
        return None

    if len(matched_files) > 1:
        raise ValueError(f'场景 {scene.sceneName} 的静态路由目录下存在多个文件，请仅保留一份')

    return matched_files[0]


def _build_static_route_export_data(scene, nodes, node_id_map):
    static_route_node_ids = []
    mixed_protocol_nodes = []

    for node in nodes:
        interfaces = list(node.interfaces.all())
        if not interfaces:
            continue

        effective_protocols = set()
        for interface in interfaces:
            routing_protocol = _get_interface_routing_protocol(interface)
            normalized_protocol = routing_protocol.upper() if routing_protocol else 'BELLMANFORD'
            effective_protocols.add(normalized_protocol)

        if STATIC_ROUTE_PROTOCOL in effective_protocols:
            if len(effective_protocols) > 1:
                mixed_protocol_nodes.append(node.nodeName or str(node.id))
                continue
            static_route_node_ids.append(node.id)

    if mixed_protocol_nodes:
        raise ValueError(
            '以下节点同时存在 NONE 和其他路由协议，无法按节点级输出 STATIC-ROUTE: '
            + ', '.join(mixed_protocol_nodes)
        )

    if not static_route_node_ids:
        return [], None

    static_route_file = _resolve_static_route_file(scene, require_exists=True)
    exported_node_ids = sorted(node_id_map[node_id] for node_id in static_route_node_ids)
    return exported_node_ids, static_route_file.resolve(strict=False).as_posix()


@lru_cache(maxsize=1)
def _get_exata_template_environment():
    template_dir = Path(__file__).resolve().parent / 'templates'
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        lstrip_blocks=True,
    )


def _build_sequential_id_map(objects):
    return {obj.id: idx + 1 for idx, obj in enumerate(objects)}


def _build_export_context(scene):
    nodes = list(Node.objects.filter(sceneId=scene).order_by('id').prefetch_related('interfaces'))
    links = Link.objects.filter(sceneId=scene).order_by('id').select_related(
        'sourceInterface',
        'destinationInterface',
        'sourceNodeId',
        'destinationNodeId',
        'subnet',
    )
    all_subnets = Subnet.objects.filter(
        sceneId=scene,
        subnetType=Subnet.SubnetTypeChoices.SUB,
    ).order_by('id').prefetch_related('interfaces__node')
    default_subnet = all_subnets.first()
    subnets = all_subnets.exclude(id=default_subnet.id) if default_subnet else all_subnets

    isolated_node_ids = []
    if default_subnet:
        isolated_node_ids = list(
            Node.objects.filter(sceneId=scene, interfaces__subnet=default_subnet)
            .order_by('id')
            .distinct()
            .values_list('id', flat=True)
        )

    node_id_map = _build_sequential_id_map(nodes)
    link_id_map = _build_sequential_id_map(list(links))
    subnet_id_map = _build_sequential_id_map(list(all_subnets))
    channel_configs, _, primary_channel_name = _get_scene_channel_data(scene)
    errors = Error.objects.filter(sceneId=scene).order_by('id')
    has_app_data = Configuration.objects.filter(sceneId=scene).exists()
    has_fault_data = LinkError.objects.filter(sceneId=scene).exists() or errors.exists()
    static_route_nodes, static_route_file_path = _build_static_route_export_data(scene, nodes, node_id_map)

    return {
        'scene': scene,
        'simulation_duration': int((scene.endTime - scene.startTime).total_seconds()),
        'num_nodes': len(nodes),
        'llc_enabled': scene.llcEnabled == 'YES',
        'arp_enabled': scene.arpEnabled == 'YES',
        'nodes': nodes,
        'links': links,
        'satellites': Node.objects.filter(sceneId=scene, nodeType='satellite').order_by('id'),
        'normal_nodes': Node.objects.filter(sceneId=scene, nodeType='normalNode').order_by('id'),
        'errors': errors,
        'default_subnet': default_subnet,
        'subnets': subnets,
        'node_id_map': node_id_map,
        'link_id_map': link_id_map,
        'subnet_id_map': subnet_id_map,
        'isolated_node_ids': [node_id_map[node_id] for node_id in isolated_node_ids],
        'include_app_config': has_app_data,
        'include_fault_config': has_fault_data,
        'channel_configs': channel_configs,
        'primary_channel_name': primary_channel_name,
        'static_route_nodes': static_route_nodes,
        'static_route_file_path': static_route_file_path,
        'exata_service_port': EXATA_SERVICE_PORT,
    }


def _render_exata_config_content(export_context):
    template = _get_exata_template_environment().get_template('exata/exata_config.template')
    return template.render(export_context)


def _build_link_txt_lines(links, node_id_map, link_id_map):
    link_content = []
    for link in links:
        source_interface_ip = link.sourceInterface.interfaceIp if link.sourceInterface else ""
        destination_interface_ip = link.destinationInterface.interfaceIp if link.destinationInterface else ""
        line = (
            f"{link_id_map[link.id]} -1 "
            f"{node_id_map[link.sourceNodeId.id]} {node_id_map[link.destinationNodeId.id]} "
            f"{link.sourceInterface.interfaceIndex if link.sourceInterface else ''} "
            f"{link.destinationInterface.interfaceIndex if link.destinationInterface else ''} "
            f"{source_interface_ip} {destination_interface_ip} "
            f"{1 if link.linkType == '鏃犵嚎' else 2}\n"
        )
        link_content.append(line)
    return link_content


def generate_exata_config(request):
    try:
        scene_id = request.GET.get('sceneId')
        if not scene_id:
            return JsonResponse({'status': 'error', 'message': 'Missing sceneId parameter'}, status=400)

        try:
            scene = Scene.objects.get(id=scene_id)
        except Scene.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Scene not found'}, status=404)

        export_context = _build_export_context(scene)
        config_content = _render_exata_config_content(export_context)

        response = HttpResponse(config_content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{scene.sceneName}.config"'
        return response

    except (ValueError, FileNotFoundError) as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        logger.error(f'Error generating Exata config: {str(e)}', exc_info=True)
        return HttpResponse(f'Error generating Exata config: {str(e)}', status=500)


'''
生成文件
'''


def generate_link_file(request):
    try:
        # 获取查询参数
        scene_id = request.GET.get('sceneId')
        if not scene_id:
            return HttpResponse('Error: Missing sceneId parameter', status=400)

        scene = get_object_or_404(Scene, id=scene_id)
        export_context = _build_export_context(scene)
        link_content = _build_link_txt_lines(
            export_context['links'],
            export_context['node_id_map'],
            export_context['link_id_map'],
        )

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

        scene = get_object_or_404(Scene, id=scene_id)
        export_context = _build_export_context(scene)
        satellites = export_context['satellites']
        node_id_map = export_context['node_id_map']

        # 准备 orbit.txt 文件内容
        orbit_content = []
        for satellite in satellites:
            # 构建轨道数据行
            line = (
                f"{node_id_map[satellite.id]} "
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

        scene = get_object_or_404(Scene, id=scene_id)
        export_context = _build_export_context(scene)
        nodes = export_context['normal_nodes']

        # 准备 node.txt 文件内容
        node_content = _build_node_txt_lines(nodes, node_id_map=export_context['node_id_map'])

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

        export_context = _build_export_context(scene)
        fault_content = _build_fault_txt_lines(
            scene,
            export_context['errors'],
            node_id_map=export_context['node_id_map'],
        )

        # 将内容写入文件或返回给用户
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="fault.txt"'
        response.writelines(fault_content)

        return response

    except Exception as e:
        return HttpResponse(f'Error generating fault file: {str(e)}', status=500)


def _build_fault_txt_lines(scene, errors, node_id_map=None):
    if node_id_map is None:
        node_id_map = {
            node.id: idx + 1
            for idx, node in enumerate(Node.objects.filter(sceneId=scene).order_by('id'))
        }

    fault_content = []
    for error in errors:
        start_time = (error.errorStartTime - scene.startTime).total_seconds()
        end_time = (error.errorEndTime - scene.startTime).total_seconds()
        exported_node_id = node_id_map.get(error.nodeId.id, error.nodeId.id)

        # 如果指定了接口，只写该接口；否则写所有接口
        if error.interfaceId:
            # 单接口故障
            line = f"{exported_node_id} {error.interfaceId.interfaceIndex} {int(start_time)} {int(end_time)}\n"
            fault_content.append(line)
        else:
            # 整个节点故障：写所有接口
            interfaces = Interface.objects.filter(node=error.nodeId)
            if not interfaces:
                continue
            for interface in interfaces:
                line = f"{exported_node_id} {interface.interfaceIndex} {int(start_time)} {int(end_time)}\n"
                fault_content.append(line)

    return fault_content


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


def format_slot_table(node_id_map: dict, data: list) -> str:
    """
    使用数据库中的 slot_table_data，结合 node_id_map 转换为字符串
    :param node_id_map: dict, 业务名到节点ID的映射
    :param data: list, 从数据库取到的 slot 表数据
    :return: str, 格式化后的文本
    """
    if not data:
        return ""

    lines = []
    for item in data:
        head = item.get("head")
        members = item.get("member", [])

        # head 映射到 id
        head_id = node_id_map.get(head, head)

        # members 映射到 id
        member_ids = [str(node_id_map.get(m, m)) for m in members]

        lines.append(str(head_id))
        lines.append(" ".join(member_ids))
    # 拼接成字符串，并保证最后一行末尾有一个空格
    result = "\n".join(lines)
    return result + " "


@csrf_exempt
def save_slot_table(request):
    if request.method == "POST":
        try:
            scene_id = request.GET.get("sceneId")  # 从 ?sceneId=28 里取
            if not scene_id:
                return JsonResponse({"status": "error", "message": "sceneId missing"}, status=400)

            # 查找场景
            try:
                scene = Scene.objects.get(id=scene_id)
            except Scene.DoesNotExist:
                return JsonResponse({"status": "error", "message": "Scene not found"}, status=404)

            # 解析 body
            body_unicode = request.body.decode('utf-8')
            data = json.loads(body_unicode)
            print(f"前端给的数据：{data}")

            # 存数据库
            SlotTable.objects.create(scene=scene, data=data)

            return JsonResponse({"status": "success"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})
    else:
        return JsonResponse({"status": "error", "message": "POST only"})


@require_http_methods(["GET"])
@csrf_exempt
def get_slot_table(request):
    try:
        scene_id = request.GET.get("sceneId")
        if not scene_id:
            return JsonResponse({"status": "error", "message": "sceneId missing"}, status=400)

        try:
            scene = Scene.objects.get(id=scene_id)
        except Scene.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Scene not found"}, status=404)

        slot_table_obj = SlotTable.objects.filter(scene=scene).order_by('-id').first()
        if not slot_table_obj:
            return JsonResponse({"status": "error", "message": "SlotTable not found"}, status=404)

        return JsonResponse({
            "status": "success",
            "slotTableId": slot_table_obj.id,
            "sceneId": scene.id,
            "data": slot_table_obj.data
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

def _generate_scene_files(scene):
    scene_folder = _resolve_scene_folder_path(scene)
    _clear_scene_folder(scene_folder)

    time_delta = scene.endTime - scene.startTime
    simulation_duration = int(time_delta.total_seconds())

    links = Link.objects.filter(sceneId=scene).select_related('sourceInterface', 'destinationInterface')
    nodes = Node.objects.filter(sceneId=scene).prefetch_related('interfaces')
    satellites = Node.objects.filter(sceneId=scene, nodeType='satellite')
    normal_nodes = Node.objects.filter(sceneId=scene, nodeType='normalNode')
    errors = Error.objects.filter(sceneId=scene)
    num_nodes = Node.objects.filter(sceneId=scene).count()

    default_subnet = Subnet.objects.filter(sceneId=scene).first()
    isolated_nodes = Node.objects.filter(
        sceneId=scene,
        interfaces__subnet=default_subnet,
    ).distinct()
    isolated_node_ids = [node.id for node in isolated_nodes]

    all_subnets = Subnet.objects.filter(
        sceneId=scene,
        subnetType=Subnet.SubnetTypeChoices.SUB,
    ).prefetch_related('interfaces__node')
    subnets = all_subnets.exclude(id=default_subnet.id if default_subnet else None)
    has_app_data = Configuration.objects.filter(sceneId=scene).exists()
    has_fault_data = (
        LinkError.objects.filter(sceneId=scene).exists()
        or Error.objects.filter(sceneId=scene).exists()
    )
    node_id_map = {node.id: idx + 1 for idx, node in enumerate(nodes)}
    link_id_map = {link.id: idx + 1 for idx, link in enumerate(links)}
    isolated_node_ids_mapped = [node_id_map[nid] for nid in isolated_node_ids]

    exata_config_data = {
        'scene': scene,
        'num_nodes': num_nodes,
        'nodes': nodes,
        'links': links,
        'simulation_duration': simulation_duration,
        'default_subnet': default_subnet,
        'subnets': subnets,
        'isolated_node_ids': isolated_node_ids_mapped,
        "include_app_config": has_app_data,
        "include_fault_config": has_fault_data,
        "node_id_map": node_id_map,
        "link_id_map": link_id_map,
    }

    template_dir = Path(__file__).resolve().parent / 'templates'
    env = Environment(loader=FileSystemLoader(str(template_dir)), lstrip_blocks=True)
    template = env.get_template('exata/exata_config.template')
    exata_config_content = template.render(exata_config_data)

    sections: list[tuple[str, str]] = []

    config_filename = f"{scene.sceneName}.config"
    _write_scene_file(scene_folder, config_filename, exata_config_content)
    sections.append((config_filename, exata_config_content))

    if has_app_data:
        app_content = generate_scene_app_content(scene, node_id_map)
        app_filename = f"{scene.sceneName}.app"
        _write_scene_file(scene_folder, app_filename, app_content)
        sections.append((app_filename, app_content))

    nodes_content = generate_scene_nodes_content(scene, node_id_map)
    nodes_filename = f"{scene.sceneName}.nodes"
    _write_scene_file(scene_folder, nodes_filename, nodes_content)
    sections.append((nodes_filename, nodes_content))

    if has_fault_data:
        fault_content = generate_scene_fault_content(scene, node_id_map)
        fault_filename = f"{scene.sceneName}.fault"
        _write_scene_file(scene_folder, fault_filename, fault_content)
        sections.append((fault_filename, fault_content))

    display_content = generate_display_file_content(scene)
    display_filename = f"{scene.sceneName}.display"
    _write_scene_file(scene_folder, display_filename, display_content)
    sections.append((display_filename, display_content))

    type_dict = {}
    for node in scene.nodes.all():
        key = node.specialType or "Unknown"
        type_dict.setdefault(key, []).append(node.id)

    level_lines = []
    for node_type in ["GEO", "PrimaryRegion", "SecondaryRegion", "GuidedMissile", "LEO"]:
        ids = type_dict.get(node_type)
        if not ids:
            continue
        level_lines.append(f"{node_type}\n")
        id_line = " ".join(str(node_id_map[node_id]) for node_id in sorted(ids))
        level_lines.append(f"{id_line}\n")
    _write_scene_file(scene_folder, "level.txt", "".join(level_lines))

    slot_table_obj = SlotTable.objects.filter(scene=scene).order_by('-id').first()
    if slot_table_obj:
        slot_table_data = format_slot_table(node_id_map, slot_table_obj.data)
    else:
        slot_table_data = ""
        logger.warning("Scene %s has no slot table data; writing an empty slotTable.txt", scene.id)
    _write_scene_file(scene_folder, "slotTable.txt", slot_table_data)

    link_lines = []
    for link in links:
        source_interface_ip = link.sourceInterface.interfaceIp if link.sourceInterface else ""
        destination_interface_ip = link.destinationInterface.interfaceIp if link.destinationInterface else ""
        line = (
            f"{link.id} -1 "
            f"{node_id_map[link.sourceNodeId.id]} {node_id_map[link.destinationNodeId.id]} "
            f"{link.sourceInterface.interfaceIndex if link.sourceInterface else ''} "
            f"{link.destinationInterface.interfaceIndex if link.destinationInterface else ''} "
            f"{source_interface_ip} {destination_interface_ip} "
            f"{1 if link.linkType == '鏃犵嚎' else 2}\n"
        )
        link_lines.append(line)
    link_content = "".join(link_lines)
    _write_scene_file(scene_folder, "link.txt", link_content)
    sections.append(("link.txt", link_content))

    orbit_lines = []
    for satellite in satellites:
        line = (
            f"{node_id_map[satellite.id]} "
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
        orbit_lines.append(line)
    orbit_content = "".join(orbit_lines)
    _write_scene_file(scene_folder, "orbit.txt", orbit_content)
    sections.append(("orbit.txt", orbit_content))

    node_content = "".join(_build_node_txt_lines(normal_nodes.order_by('id'), node_id_map=node_id_map))
    _write_scene_file(scene_folder, "node.txt", node_content)
    sections.append(("node.txt", node_content))

    fault_txt_content = "".join(_build_fault_txt_lines(scene, errors, node_id_map=node_id_map))
    _write_scene_file(scene_folder, "fault.txt", fault_txt_content)
    sections.append(("fault.txt", fault_txt_content))

    simulation_end_time = (scene.endTime - scene.startTime).total_seconds()
    initial_content = "".join([
        f"INTERVAL {scene.simulationStep}\n",
        f"FINAL {int(simulation_end_time)}\n",
    ])
    _write_scene_file(scene_folder, "initial.txt", initial_content)
    sections.append(("initial.txt", initial_content))

    return scene_folder, sections

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
    print(scene_folder)
    os.makedirs(scene_folder, exist_ok=True)  # 确保文件夹存在

    # 清空现有文件夹内容
    for filename in os.listdir(scene_folder):
        file_path = os.path.join(scene_folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"删除文件失败 {file_path}: {e}")

    try:
        export_context = _build_export_context(scene)
    except (ValueError, FileNotFoundError) as e:
        return HttpResponse(f'Error generating export context: {str(e)}', status=400)
    links = export_context['links']
    satellites = export_context['satellites']
    normal_nodes = export_context['normal_nodes']
    errors = export_context['errors']
    node_id_map = export_context['node_id_map']
    link_id_map = export_context['link_id_map']
    subnet_id_map = export_context['subnet_id_map']
    has_app_data = export_context['include_app_config']
    has_fault_data = export_context['include_fault_config']
    print(node_id_map)
    print(link_id_map)
    print(subnet_id_map)
    exata_config_content = _render_exata_config_content(export_context)
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
    if has_app_data:
        app_content = generate_scene_app_content(scene,node_id_map)
        app_path = os.path.join(scene_folder, f"{scene.sceneName}.app")
        with open(app_path, 'w', encoding='utf-8') as f:
            f.write(app_content)

        response.write(f"[{scene.sceneName}.app]\n")
        response.write(app_content + "\n\n")

    # 生成并保存 .nodes 文件,都加入节点映射。
    nodes_content = generate_scene_nodes_content(scene,node_id_map)
    nodes_path = os.path.join(scene_folder, f"{scene.sceneName}.nodes")
    with open(nodes_path, 'w', encoding='utf-8') as f:
        f.write(nodes_content)

    response.write(f"[{scene.sceneName}.nodes]\n")
    response.write(nodes_content + "\n\n")

    if has_fault_data:
        # 生成并保存 .fault 文件
        fault_content = generate_scene_fault_content(
            scene,
            node_id_map,
            link_id_map=link_id_map,
            subnet_id_map=subnet_id_map,
        )
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

    """
    根据场景 scene 的节点 specialType 自动生成 level.txt
    保存到 scene_folder/level.txt
    """
    # 1. 获取该场景所有节点，按 specialType 分组
    nodes = scene.nodes.all()
    type_dict = {}
    for node in nodes:
        key = node.specialType or "Unknown"
        type_dict.setdefault(key, []).append(node.id)

    # 2. 按需求顺序输出，如果顺序固定，可手动定义
    type_order = [
        "GEO",
        "PrimaryRegion",
        "SecondaryRegion",
        "GuidedMissile",
        "LEO"
    ]

    link_content = []

    for t in type_order:
        ids = type_dict.get(t)
        if not ids:
            continue
        # 写 specialType
        link_content.append(f"{t}\n")
        # 写节点 id，按升序排列并空格分隔
        id_line = " ".join(str(node_id_map[i]) for i in sorted(ids))
        link_content.append(f"{id_line}\n")

    # 3. 保存文件
    level_path = os.path.join(scene_folder, "level.txt")
    with open(level_path, 'w', encoding='utf-8') as f:
        f.writelines(link_content)

    # 生成 slotTable.txt
    # 从数据库里取最新的一条 slot 表
    slot_table_obj = SlotTable.objects.filter(scene=scene).order_by('-id').first()
    if not slot_table_obj:
        raise ValueError(f"Scene {scene.id} 没有 slot 表数据")

    # 格式化
    slot_table_data = format_slot_table(node_id_map, slot_table_obj.data)
    print(f"要往文件里写的 slottable_data: {slot_table_data}")

    # 写文件
    slot_table_path = os.path.join(scene_folder, "slotTable.txt")
    with open(slot_table_path, 'w', encoding='utf-8') as f:
        f.writelines(slot_table_data)

    # 生成并保存 link.txt 文件
    link_content = _build_link_txt_lines(links, node_id_map, link_id_map)

    link_path = os.path.join(scene_folder, "link.txt")
    with open(link_path, 'w', encoding='utf-8') as f:
        f.writelines(link_content)

    response.write("[link.txt]\n")
    response.writelines(link_content)
    response.write("\n")

    # 生成并保存 orbit.txt 文件,8.29一并对orbit.txt进行了节点映射
    orbit_content = []
    for satellite in satellites:
        line = (
            f"{node_id_map[satellite.id]} "
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
    node_content = _build_node_txt_lines(normal_nodes.order_by('id'), node_id_map=node_id_map)

    node_path = os.path.join(scene_folder, "node.txt")
    with open(node_path, 'w', encoding='utf-8') as f:
        f.writelines(node_content)

    response.write("[node.txt]\n")
    response.writelines(node_content)
    response.write("\n")

    # 生成并保存 fault.txt 文件
    fault_txt_content = _build_fault_txt_lines(scene, errors, node_id_map=node_id_map)

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


def generate_scene_app_content(scene,node_id_map):
    configurations = Configuration.objects.filter(sceneId=scene)
    content = ""
    for config in configurations:
        business_type = normalize_business_type(config.businessType)

        if business_type == 'CBR':
            start_time = config.cbrStartTime
            end_time = config.cbrEndTime
            packet_size = config.cbrPacketSize
            interval = config.cbrSendInterval
            precedence = config.cbrPrecedence

            time_offset = (start_time - scene.startTime).total_seconds() if start_time else 0
            end_time_offset = (end_time - scene.startTime).total_seconds() if end_time else 0

            config_line = (
                f"{config.businessType} {node_id_map[config.sourceNodeId.id]} "
                f"{node_id_map[config.destinationNodeId.id]} 5000 {packet_size} {interval} "
                f"{int(time_offset)} {int(end_time_offset)}"
            )
            if precedence is not None:
                config_line += f" PRECEDENCE {precedence}"
            config_line += f" {config.TransferType}"
            config_line += "\n"
            content += config_line

        elif business_type == 'FTP':
            start_time = config.ftpStartTime
            time_offset = (start_time - scene.startTime).total_seconds() if start_time else 0
            packet_count = config.ftpPacketCount

            config_line = f"{config.businessType} {node_id_map[config.sourceNodeId.id]} {node_id_map[config.destinationNodeId.id]} {packet_count} {int(time_offset)}\n"
            content += config_line

        elif business_type == 'TRAFFIC-GEN':
            config_line = f"{config.businessType} {node_id_map[config.sourceNodeId.id]} {node_id_map[config.destinationNodeId.id]} DET {config.tgStartTime} DET {config.tgDurationTime} RND DET {config.tgPacketSize} DET {config.tgSendInterval} 1.0 NOLB\n"
            content += config_line

        elif business_type == 'HTTP':
            num_servers = len(config.serverList) if config.serverList else 0
            server_ids_str = ' '.join(str(node_id_map[sid]) for sid in config.serverList) if config.serverList else ''
            config_line = f"{config.businessType} {node_id_map[config.clientId.id]} {num_servers} {server_ids_str} {config.httpStartTime} {config.httpThreshTime}\n"
            content += config_line

            # 多个 HTTPD 行
            if config.serverList:
                for server_id in config.serverList:
                    content += f"HTTPD {node_id_map[server_id]}\n"

        elif business_type == 'POISSON':
            config_line = (
                f"VBR {node_id_map[config.sourceNodeId.id]} "
                f"{node_id_map[config.destinationNodeId.id]} {config.poissonPacketSize} "
                f"{config.poissonMeanInterval} {config.poissonStartTime} {config.poissonEndTime}\n"
            )
            content += config_line

        elif business_type == 'BROADCAST':
            config_line = (
                f"MESSENGER-APP {node_id_map[config.sourceNodeId.id]} {config.broadcastDest} "
                f"{config.broadcastTransportType} {config.broadcastAppType} "
                f"{config.broadcastLifeTime} {config.broadcastStartTime} "
                f"{config.broadcastInterval} {config.broadcastFragmentSize} "
                f"{config.broadcastFragmentNum}\n"
            )
            content += config_line

        elif business_type == 'MULTICAST':
            config_line = (
                f"MCBR {node_id_map[config.sourceNodeId.id]} {config.multicastDestination} "
                f"{config.multicastItemsToSend} {config.multicastItemSize} "
                f"{config.multicastInterval} {config.multicastStartTime} "
                f"{config.multicastEndTime}\n"
            )
            content += config_line

    return content


def _parse_node_point_time(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def _build_node_timeline_rows(node, exported_node_id):
    rows = []
    base_lat = float(node.lat) if node.lat is not None else 0.0
    base_lon = float(node.lon) if node.lon is not None else 0.0
    base_alt = float(node.alt) if node.alt is not None else 0.0
    rows.append((int(0), base_lat, base_lon, base_alt))

    start_time = _parse_node_point_time(node.startTime)
    via_points = node.viaPoints if isinstance(node.viaPoints, list) else []
    for point in via_points:
        if not isinstance(point, dict):
            continue
        point_time = _parse_node_point_time(point.get('time'))
        if point_time is None or start_time is None:
            continue
        if start_time.tzinfo is not None and point_time.tzinfo is None:
            point_time = point_time.replace(tzinfo=start_time.tzinfo)
        elif start_time.tzinfo is None and point_time.tzinfo is not None:
            point_time = point_time.replace(tzinfo=None)
        seconds = int((point_time - start_time).total_seconds())
        if seconds < 0:
            continue
        rows.append(
            (
                seconds,
                float(point.get('lat', 0.0) or 0.0),
                float(point.get('lon', 0.0) or 0.0),
                float(point.get('alt', 0.0) or 0.0),
            )
        )

    rows.sort(key=lambda item: item[0])
    return [
        {
            'node_id': exported_node_id,
            'time_s': time_s,
            'lat': lat,
            'lon': lon,
            'alt': alt,
            'node_image': node.nodeImage,
            'node_name': node.nodeName,
        }
        for time_s, lat, lon, alt in rows
    ]


def _build_node_txt_lines(nodes, node_id_map=None):
    lines = []
    for node in nodes:
        exported_node_id = node_id_map[node.id] if node_id_map else node.id
        for row in _build_node_timeline_rows(node, exported_node_id):
            lines.append(
                f"{row['node_id']} {row['time_s']} {row['lat']} {row['lon']} {row['alt']} {row['node_image']} {row['node_name']}\n"
            )
    return lines


def generate_scene_nodes_content(scene,node_id_map):
    nodes = Node.objects.filter(Q(sceneId=scene)).order_by('id')
    content = ""
    for node in nodes:
        if node.nodeType == 'normalNode':
            for row in _build_node_timeline_rows(node, node_id_map[node.id]):
                content += f"{row['node_id']} {row['time_s']} ({row['lat']} {row['lon']} {row['alt']}) 0 0 0\n"
        else:
            content += f"{node_id_map[node.id]} 0 (0 0 0) 0 0 0\n"
    return content


def generate_scene_fault_content(scene, node_id_map, link_id_map=None, subnet_id_map=None):
    result = []

    if link_id_map is None:
        ordered_links = list(Link.objects.filter(sceneId=scene).order_by('id'))
        link_id_map = _build_sequential_id_map(ordered_links)

    if subnet_id_map is None:
        ordered_subnets = list(
            Subnet.objects.filter(
                sceneId=scene,
                subnetType=Subnet.SubnetTypeChoices.SUB,
            ).order_by('id')
        )
        subnet_id_map = _build_sequential_id_map(ordered_subnets)

    def seconds_since_scene_start(time_point):
        if not time_point:
            return "0S"
        return f"{int((time_point - scene.startTime).total_seconds())}S"

    def get_interface_export_id(iface):
        iface_type = iface.interfaceType.upper()
        if iface_type == "SUB":
            subnet_export_id = subnet_id_map.get(iface.subnet.id) if iface.subnet else None
            return f"SUB{subnet_export_id or 0}"
        if iface_type == "LINK":
            link = Link.objects.filter(
                Q(sourceInterface=iface) | Q(destinationInterface=iface)
            ).first()
            link_export_id = link_id_map.get(link.id) if link else None
            return f"LINK{link_export_id or 0}"
        return "UNKNOWN"

    # 节点故障：根据是否指定接口来决定故障范围
    node_errors = Error.objects.filter(sceneId=scene)
    for error in node_errors:
        node = error.nodeId
        start_time = seconds_since_scene_start(error.errorStartTime)
        end_time = seconds_since_scene_start(error.errorEndTime)

        # 如果指定了接口，只写该接口的故障；否则写所有接口的故障
        if error.interfaceId:
            # 单接口故障
            iface = error.interfaceId
            iface_index = iface.interfaceIndex
            id_part = get_interface_export_id(iface)

            line = f"INTERFACE-FAULT {id_part}/{node_id_map[node.id]}/{iface_index} {start_time} {end_time} NO"
            result.append(line)
        else:
            # 整个节点故障：写所有接口的故障
            interfaces = Interface.objects.filter(node=node)
            for iface in interfaces:
                iface_index = iface.interfaceIndex
                id_part = get_interface_export_id(iface)

                line = f"INTERFACE-FAULT {id_part}/{node_id_map[node.id]}/{iface_index} {start_time} {end_time} NO"
                result.append(line)

    # 链路故障：只写链路的 sourceInterface 和 destinationInterface
    # 使用链路 id 替代 subnet_id
    link_errors = LinkError.objects.filter(sceneId=scene)
    for link_error in link_errors:
        link = link_error.linkId
        start_time = seconds_since_scene_start(link_error.errorStartTime)
        end_time = seconds_since_scene_start(link_error.errorEndTime)

        for iface in [link.sourceInterface, link.destinationInterface]:
            if iface is None:
                continue  # 避免空接口导致报错
            node = iface.node
            iface_type = iface.interfaceType.upper()
            iface_index = iface.interfaceIndex
            link_id = link_id_map.get(link.id, link.id)
            mapped_node_id = node_id_map.get(node.id, node.id)
            line = f"INTERFACE-FAULT {iface_type}{link_id}/{mapped_node_id}/{iface_index} {start_time} {end_time} NO"
            result.append(line)
    return "\n".join(result)


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
                        results_received.append(
                            ['bar', business_id, info["start_node"] + '-' + info["end_node"], received])

                    # 获取业务丢包率
                    drop = 1 - received / sent
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
                        results_throughput.append(
                            ['bar', business_id, info["start_node"] + '-' + info["end_node"], throughput])

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
            print(json_results_sent)
            return json_results_sent, json_results_received, json_results_drop, json_results_delay, json_results_jitter, json_results_throughput

        except Exception as e:
            print(f"读取文件时发生错误: {e}")


def analyze_exata_by_node_multi_flat(stat_file_path: str):
    """
    按节点ID解析业务数据
    每个指标保存为 list[dict]，允许节点重复出现
    """
    path = Path(stat_file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {stat_file_path}")

    results_sent = []
    results_received = []
    results_delay = []
    results_jitter = []
    results_throughput = []
    results_time_range = []  # 新增：收包时间范围

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        first_time = None
        last_time = None
        current_node = None

        for line in f:
            fields = [field.strip() for field in line.split(',')]
            if len(fields) < 5:
                continue

            node_id = fields[0].strip()  # 节点ID
            current_node = node_id

            # 发包
            if "Total Unicast Fragments Sent" in line:
                m = re.search(r"= ([\d\.]+)", line)
                if m:
                    results_sent.append({node_id: float(m.group(1))})

            # 收包
            if "Total Unicast Fragments Received" in line:
                m = re.search(r"= ([\d\.]+)", line)
                if m:
                    results_received.append({node_id: float(m.group(1))})

            # 时延
            if "Average Unicast End-to-End Delay" in line:
                m = re.search(r"= ([\d\.]+)", line)
                if m:
                    results_delay.append({node_id: float(m.group(1))})

            # 抖动
            if "Average Unicast Jitter" in line:
                m = re.search(r"= ([\d\.]+)", line)
                if m:
                    results_jitter.append({node_id: float(m.group(1))})

            # 吞吐量
            if "Unicast Received Throughput" in line:
                m = re.search(r"= ([\d\.]+)", line)
                if m:
                    results_throughput.append({node_id: float(m.group(1))})

            # 收包始末时间
            if "First Unicast Fragment Received" in line:
                m = re.search(r"= ([\d\.]+)", line)
                if m:
                    first_time = float(m.group(1))

            if "Last Unicast Fragment Received" in line:
                m = re.search(r"= ([\d\.]+)", line)
                if m:
                    last_time = float(m.group(1))
                    # 一旦拿到 last_time，说明一组完整的时间范围记录可以存储
                    if first_time is not None:
                        results_time_range.append({
                            node_id: {
                                "first": first_time,
                                "last": last_time
                            }
                        })
                        first_time = None
                        last_time = None

    # 拼接成大JSON
    big_json = {
        "sent": results_sent,
        "received": results_received,
        "delay": results_delay,
        "jitter": results_jitter,
        "throughput": results_throughput,
        "time_range": results_time_range  # 新增
    }

    return big_json
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

        # 获取分析结果
        results = analyze_exata_by_node_multi_flat(full_path)

        # 组织响应数据
        return JsonResponse({
            "status": "success",
            "data": results
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


def _get_scene_files_root():
    if getattr(settings, 'MEDIA_ROOT', ''):
        return Path(settings.MEDIA_ROOT) / 'scene_files'
    return Path(settings.BASE_DIR) / 'scene_files'


def _resolve_scene_runtime_context(scene_id):
    try:
        normalized_scene_id = int(scene_id)
    except (TypeError, ValueError):
        return None, None, None, JsonResponse({
            'status': 'error',
            'message': 'sceneId 必须是整数'
        }, status=400)

    try:
        scene = Scene.objects.get(id=normalized_scene_id)
    except Scene.DoesNotExist:
        return None, None, None, JsonResponse({
            'status': 'error',
            'message': f'场景ID {normalized_scene_id} 不存在'
        }, status=404)

    scene_root = _get_scene_files_root().resolve(strict=False)
    scene_folder = (scene_root / scene.sceneName).resolve(strict=False)

    try:
        scene_folder.relative_to(scene_root)
    except ValueError:
        return None, None, None, JsonResponse({
            'status': 'error',
            'message': '场景目录非法'
        }, status=400)

    return normalized_scene_id, scene, scene_folder, None


def _read_scene_text_file(scene_id, file_name):
    try:
        scene = Scene.objects.get(id=scene_id)
    except Scene.DoesNotExist:
        return None, JsonResponse({
            'status': 'error',
            'message': f'场景ID {scene_id} 不存在'
        }, status=404)

    scene_folder = (_get_scene_files_root() / scene.sceneName).resolve(strict=False)
    scene_root = _get_scene_files_root().resolve(strict=False)

    try:
        scene_folder.relative_to(scene_root)
    except ValueError:
        return None, JsonResponse({
            'status': 'error',
            'message': '场景目录非法'
        }, status=400)

    if not scene_folder.exists() or not scene_folder.is_dir():
        return None, JsonResponse({
            'status': 'error',
            'message': f'场景文件夹不存在: {scene.sceneName}'
        }, status=404)

    file_path = (scene_folder / file_name).resolve(strict=False)
    try:
        file_path.relative_to(scene_folder)
    except ValueError:
        return None, JsonResponse({
            'status': 'error',
            'message': '文件路径非法'
        }, status=400)

    if not file_path.exists() or not file_path.is_file():
        return None, JsonResponse({
            'status': 'error',
            'message': f'文件不存在: {file_name}'
        }, status=404)

    try:
        content = file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        content = file_path.read_text(encoding='utf-8', errors='replace')

    return {
        'status': 'success',
        'sceneId': scene.id,
        'sceneName': scene.sceneName,
        'fileName': file_name,
        'content': content
    }, None


def _get_scene_folder(scene_id):
    try:
        scene = Scene.objects.get(id=scene_id)
    except Scene.DoesNotExist:
        return None, None, JsonResponse({
            'status': 'error',
            'message': f'场景ID {scene_id} 不存在'
        }, status=404)

    scene_folder = (_get_scene_files_root() / scene.sceneName).resolve(strict=False)
    scene_root = _get_scene_files_root().resolve(strict=False)

    try:
        scene_folder.relative_to(scene_root)
    except ValueError:
        return None, None, JsonResponse({
            'status': 'error',
            'message': '场景目录非法'
        }, status=400)

    if not scene_folder.exists() or not scene_folder.is_dir():
        return None, None, JsonResponse({
            'status': 'error',
            'message': f'场景文件夹不存在: {scene.sceneName}'
        }, status=404)

    return scene, scene_folder, None


def _resolve_scene_data_file(scene_folder, scene_name, suffix):
    preferred_file = (scene_folder / f'{scene_name}{suffix}').resolve(strict=False)
    if preferred_file.exists() and preferred_file.is_file():
        return preferred_file, None

    matched_files = sorted(
        path.resolve(strict=False)
        for path in scene_folder.glob(f'*{suffix}')
        if path.is_file()
    )

    if not matched_files:
        return None, JsonResponse({
            'status': 'error',
            'message': f'未找到 {suffix} 文件'
        }, status=404)

    if len(matched_files) > 1:
        return None, JsonResponse({
            'status': 'error',
            'message': f'场景目录下存在多个 {suffix} 文件，请保留唯一文件后再重试'
        }, status=400)

    return matched_files[0], None


@require_http_methods(["POST"])
@csrf_exempt
def upload_scene_static_route(request):
    scene_id = request.POST.get('sceneId') or request.GET.get('sceneId')
    if not scene_id:
        return JsonResponse({
            'status': 'error',
            'message': '缺少 sceneId 参数'
        }, status=400)

    uploaded_file = request.FILES.get(STATIC_ROUTE_UPLOAD_FIELD)
    if uploaded_file is None:
        return JsonResponse({
            'status': 'error',
            'message': f'缺少上传文件字段 {STATIC_ROUTE_UPLOAD_FIELD}'
        }, status=400)

    try:
        scene = Scene.objects.get(id=scene_id)
    except Scene.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': f'场景ID {scene_id} 不存在'
        }, status=404)

    try:
        scene_folder = _resolve_scene_folder_path(scene)
        scene_folder.mkdir(parents=True, exist_ok=True)
        static_route_dir = _resolve_static_route_directory(scene, create=True)
    except ValueError as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

    safe_file_name = Path(uploaded_file.name).name.strip()
    if not safe_file_name:
        return JsonResponse({
            'status': 'error',
            'message': '上传文件名不能为空'
        }, status=400)

    for existing_file in static_route_dir.iterdir():
        if existing_file.is_file() or existing_file.is_symlink():
            existing_file.unlink()

    target_file = (static_route_dir / safe_file_name).resolve(strict=False)
    try:
        target_file.relative_to(static_route_dir)
    except ValueError:
        return JsonResponse({
            'status': 'error',
            'message': '静态路由文件路径非法'
        }, status=400)

    with target_file.open('wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)

    return JsonResponse({
        'status': 'success',
        'sceneId': scene.id,
        'sceneName': scene.sceneName,
        'fileName': target_file.name,
        'relativePath': f'{STATIC_ROUTE_FOLDER_NAME}/{target_file.name}',
        'absolutePath': target_file.as_posix(),
    }, json_dumps_params={'ensure_ascii': False})


@require_http_methods(["GET"])
@csrf_exempt
def get_rx_power_log(request):
    scene_id = request.GET.get('sceneId')
    if not scene_id:
        return JsonResponse({
            'status': 'error',
            'message': '缺少 sceneId 参数'
        }, status=400)

    result, error_response = _read_scene_text_file(scene_id, 'rx_power_log.txt')
    if error_response:
        return error_response
    return JsonResponse(result, json_dumps_params={'ensure_ascii': False})


@require_http_methods(["GET"])
@csrf_exempt
def get_ospf_detected(request):
    scene_id = request.GET.get('sceneId')
    if not scene_id:
        return JsonResponse({
            'status': 'error',
            'message': '缺少 sceneId 参数'
        }, status=400)

    result, error_response = _read_scene_text_file(scene_id, 'ospf_detected.txt')
    if error_response:
        return error_response
    return JsonResponse(result, json_dumps_params={'ensure_ascii': False})


@require_http_methods(["GET"])
@csrf_exempt
def get_physical_layer_data(request):
    scene_id = request.GET.get('sceneId')
    if not scene_id:
        return JsonResponse({
            'status': 'error',
            'message': '缺少 sceneId 参数'
        }, status=400)

    scene, scene_folder, error_response = _get_scene_folder(scene_id)
    if error_response:
        return error_response

    config_file, error_response = _resolve_scene_data_file(scene_folder, scene.sceneName, '.config')
    if error_response:
        return error_response

    try:
        result = extract_config_parameters(str(config_file))
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'物理层数据采集失败: {str(e)}'
        }, status=500)

    return JsonResponse({
        'status': 'success',
        'sceneId': scene.id,
        'sceneName': scene.sceneName,
        'configFile': config_file.name,
        'data': result
    }, json_dumps_params={'ensure_ascii': False})


@require_http_methods(["GET"])
@csrf_exempt
def get_link_layer_data(request):
    scene_id = request.GET.get('sceneId')
    if not scene_id:
        return JsonResponse({
            'status': 'error',
            'message': '缺少 sceneId 参数'
        }, status=400)

    scene, scene_folder, error_response = _get_scene_folder(scene_id)
    if error_response:
        return error_response

    link_relationships_file = scene_folder / 'link_relationships.txt'
    if link_relationships_file.exists() and link_relationships_file.is_file():
        try:
            file_result = _parse_link_relationships_file(link_relationships_file)
            if file_result:
                return JsonResponse({
                    'status': 'success',
                    'sceneId': scene.id,
                    'sceneName': scene.sceneName,
                    'dataFile': link_relationships_file.name,
                    'dataSource': 'link_relationships.txt',
                    'data': file_result
                }, json_dumps_params={'ensure_ascii': False})
        except Exception:
            pass

    config_file, error_response = _resolve_scene_data_file(scene_folder, scene.sceneName, '.config')
    if error_response:
        return error_response

    nodes_file, error_response = _resolve_scene_data_file(scene_folder, scene.sceneName, '.nodes')
    if error_response:
        return error_response

    try:
        result = process_link_relationships(str(config_file), str(nodes_file))
        if not result:
            result = _build_link_layer_data(config_file, nodes_file)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'链路层数据采集失败: {str(e)}'
        }, status=500)

    return JsonResponse({
        'status': 'success',
        'sceneId': scene.id,
        'sceneName': scene.sceneName,
        'configFile': config_file.name,
        'nodesFile': nodes_file.name,
        'dataSource': 'generated',
        'data': result
    }, json_dumps_params={'ensure_ascii': False})


@require_http_methods(["GET"])
@csrf_exempt
def get_network_layer_data(request):
    scene_id = request.GET.get('sceneId')
    if not scene_id:
        return JsonResponse({
            'status': 'error',
            'message': '缺少 sceneId 参数'
        }, status=400)

    scene, scene_folder, error_response = _get_scene_folder(scene_id)
    if error_response:
        return error_response

    node_files = find_bellmanford_files(scene_folder)
    if not node_files:
        return JsonResponse({
            'status': 'error',
            'message': '未找到 bellmanford_node_*.txt 文件'
        }, status=404)

    data = []
    for node_id, file_path in node_files:
        parsed = parse_bellmanford_file(file_path)
        data.append({
            'nodeId': node_id,
            'nodeName': parsed['nodeLabel'],
            'times': [block['simTime'] for block in parsed['blocks']],
        })

    return JsonResponse({
        'status': 'success',
        'sceneId': scene.id,
        'sceneName': scene.sceneName,
        'data': data
    }, json_dumps_params={'ensure_ascii': False})


@require_http_methods(["GET"])
@csrf_exempt
def get_network_layer_block(request):
    scene_id = request.GET.get('sceneId')
    node_id = request.GET.get('nodeId')
    sim_time = request.GET.get('simTime')

    if not scene_id:
        return JsonResponse({
            'status': 'error',
            'message': '缺少 sceneId 参数'
        }, status=400)

    if not node_id:
        return JsonResponse({
            'status': 'error',
            'message': '缺少 nodeId 参数'
        }, status=400)

    if not sim_time:
        return JsonResponse({
            'status': 'error',
            'message': '缺少 simTime 参数'
        }, status=400)

    try:
        node_id = int(node_id)
    except (TypeError, ValueError):
        return JsonResponse({
            'status': 'error',
            'message': 'nodeId 参数格式错误'
        }, status=400)

    scene, scene_folder, error_response = _get_scene_folder(scene_id)
    if error_response:
        return error_response

    node_files = dict(find_bellmanford_files(scene_folder))
    file_path = node_files.get(node_id)
    if file_path is None:
        return JsonResponse({
            'status': 'error',
            'message': f'未找到节点{node_id}对应的 bellmanford 文件'
        }, status=404)

    result = get_block_by_sim_time(file_path, sim_time)
    if result is None:
        return JsonResponse({
            'status': 'error',
            'message': f'节点{node_id}下未找到 simTime={sim_time} 的数据块'
        }, status=404)

    block = result['block']
    return JsonResponse({
        'status': 'success',
        'sceneId': scene.id,
        'sceneName': scene.sceneName,
        'nodeId': result['nodeId'],
        'nodeName': result['nodeLabel'],
        'simTime': block['simTime'],
        'block': block['rawBlock']
    }, json_dumps_params={'ensure_ascii': False})


selected_scene_name = None


@require_http_methods(["POST"])
@csrf_exempt
def start_simulation(request):
    global absolute_path
    global selected_scene_name
    try:
        data = json.loads(request.body)
        scene_id = data.get('sceneId')

        if not scene_id:
            return JsonResponse({
                'status': 'error',
                'message': '缺少场景ID参数'
            }, status=400)

        _, scene, scene_folder, error_response = _resolve_scene_runtime_context(scene_id)
        if error_response:
            return error_response

        selected_scene_name = scene.sceneName
        absolute_path = scene_folder
        print(type(absolute_path))
        print(f"场景文件夹绝对路径: {absolute_path}")
        return JsonResponse({
            'status': 'success',
            'sceneId': scene.id,
            'sceneName': scene.sceneName,
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


def extract_node_from_filename(filename):
    """从文件名提取节点编号，如queuesize_node1.txt → 1"""
    match = re.search(r'node(\d+)', filename)
    return int(match.group(1)) if match else 1  # 默认返回1如果未匹配到


def find_queue_files(folder_path: str) -> List[str]:
    """查找文件夹中所有符合 queuesize_node*.txt 格式的文件"""
    pattern = os.path.join(folder_path, "queuesize_node*.txt")
    return sorted(glob.glob(pattern), key=lambda x: extract_node_from_filename(x))


def read_and_parse_files(file_paths: List[str]) -> Dict[str, Dict[str, List[int]]]:
    """读取并解析多个文件的数据，返回格式为 {'node几': {VCID: [数值]}}"""
    all_data = {}

    for file_path in file_paths:
        file_name = os.path.basename(file_path)
        node_num = extract_node_from_filename(file_name)

        try:
            with open(file_path, 'r', encoding='gbk') as f:
                lines = f.readlines()

            # 动态构建正则模式（根据节点号变化）
            pattern = fr'SID:{node_num}, VCID:(\d+)-(\d+)'

            file_data = {}
            for line_num, line in enumerate(lines, 1):
                matches = re.findall(pattern, line)
                #if not matches and line.strip():  # 非空行但未匹配时警告
                    #print(f"line  {line_num}  no match: {line.strip()}")

                for vcid, value in matches:
                    key = f"VCID:{vcid}"
                    file_data.setdefault(key, []).append(int(value))

            # 使用 "node几" 作为键
            node_key = f"node{node_num}"
            all_data[node_key] = file_data

        except Exception as e:
            print(f"wrong with processing {file_name} : {str(e)}")

    return all_data



def analyze_queue_data(request):
    scene_id = request.GET.get('sceneId')
    try:
        scene = Scene.objects.get(pk=scene_id)
    except Scene.DoesNotExist:
        return HttpResponse('Error: Scene not found', status=404)
    # 构造文件夹路径
    scene_folder = os.path.join(settings.MEDIA_ROOT, 'scene_files', scene.sceneName, 'outfile')
    file_paths = find_queue_files(scene_folder)
    if not file_paths:
        print(f"在文件夹 {file_paths} 中未找到 queuesize_node*.txt 文件")


    try:
        data = read_and_parse_files(file_paths)
        return JsonResponse({'data': data}, safe=False)
    except FileNotFoundError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Internal error: {str(e)}'}, status=500)

def extract_node_number(file_path):
    """从文件名中提取节点编号"""
    filename = os.path.basename(file_path)
    digits = ''.join(filter(str.isdigit, filename))
    return int(digits) if digits else 0


def read_slot_stats(file_path):
    """
    读取单个文件，返回周期列表和每个接口的带宽利用率百分比字典
    返回: (cycles, {interface_id: [percentages]})
    """
    raw_data = {}  # period -> {interface_id: value}
    periods = set()

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split(',')
            if len(parts) != 2:
                continue

            period_part, interface_part = parts

            # 提取周期编号
            if not period_part.startswith('period'):
                continue
            try:
                period_num = int(period_part.replace('period', ''))
            except ValueError:
                continue

            # 提取接口数据
            if '::' not in interface_part:
                continue

            interface_name, value_str = interface_part.split('::', 1)
            if not interface_name.startswith('interface'):
                continue

            try:
                interface_id = int(interface_name.replace('interface', ''))
                value = float(value_str) * 100.0  # 转换为百分比
            except ValueError:
                continue

            periods.add(period_num)
            if period_num not in raw_data:
                raw_data[period_num] = {}
            raw_data[period_num][interface_id] = value

    # 按周期排序
    sorted_periods = sorted(periods)
    cycles = [p * 12 for p in sorted_periods]  # 转换为时间轴

    # 收集所有接口
    all_interfaces = set()
    for period_data in raw_data.values():
        all_interfaces.update(period_data.keys())
    all_interfaces = sorted(all_interfaces)

    # 为每个接口创建数据序列
    interface_data = {}
    for interface_id in all_interfaces:
        interface_data[interface_id] = [raw_data.get(p, {}).get(interface_id, 0.0) for p in sorted_periods]

    return cycles, interface_data


def collect_bandwidth_data(folder_path):
    """
    收集所有节点的带宽和业务带宽数据，按照接口分开保存
    {
      "Node1": {
        "time": [...],
        "total_interfaces": {
          "interface0": [...],
          "interface8": [...]
        },
        "bus_interfaces": {
          "interface0": [...],
          "interface8": [...]
        }
      },
      ...
    }
    """
    result = {}

    # 所有节点的 total
    total_files = sorted(
        glob.glob(os.path.join(folder_path, "slot_stats_node*.txt")),
        key=extract_node_number
    )
    # 所有节点的 bus
    bus_files = sorted(
        glob.glob(os.path.join(folder_path, "busslot_stats_node*.txt")),
        key=extract_node_number
    )

    # 然后收集数据
    # 遍历 total 文件
    for file_path in total_files:
        node_num = extract_node_number(file_path)
        cycles, interface_data = read_slot_stats(file_path)

        node_key = f"Node{node_num}"
        result[node_key] = {
            "total_interfaces": {},
            "bus_interfaces": {}  # 先留空
        }

        # 保存每个接口的数据
        for interface_id, values in interface_data.items():
            result[node_key]["total_interfaces"][f"interface{interface_id}"] = values

    # 遍历 bus 文件，补充 bus_interfaces
    for file_path in bus_files:
        node_num = extract_node_number(file_path)
        cycles, interface_data = read_slot_stats(file_path)

        node_key = f"Node{node_num}"
        if node_key not in result:
            result[node_key] = {
                "time": cycles,
                "total_interfaces": {},
                "bus_interfaces": {}
            }

        # 保存每个接口的数据
        for interface_id, values in interface_data.items():
            result[node_key]["bus_interfaces"][f"interface{interface_id}"] = values

    return result


def save_to_json(data, output_file):
    """将数据保存为JSON文件"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_slot_stats_data(request):
    scene_id = request.GET.get('sceneId')

    try:
        scene = Scene.objects.get(pk=scene_id)
    except Scene.DoesNotExist:
        return HttpResponse('Error: Scene not found', status=404)

    # 构造文件夹路径
    scene_folder = os.path.join(settings.MEDIA_ROOT, 'scene_files', scene.sceneName, 'outfile')

    try:
        node_data = collect_bandwidth_data(scene_folder)
        return JsonResponse({'data': node_data}, safe=False)

    except FileNotFoundError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Internal error: {str(e)}'}, status=500)






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

    # print(f"已发送消息：{message_json}")
    #发送给前端的

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
        file = open(absolute_path / 'config.txt', 'w', encoding='utf-8')
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
    startSign = False
    link_x = 1
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
    receive_link_state = []
    time_receive_link_state = []  #包含上个时间片内的全部链路数据包消息
    update_links = []
    json_list = []
    message_prefixes = ['16000000000000', '07000000000000', '000000000000000a', '0e01000000', ]

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
                    f"LAT {float(info['lat'])} "
                    f"LON {float(info['lon'])} "
                    f"ALT {float(info['alt'])} "
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

            server_address = EXATA_SERVICE_HOST
            server_port = EXATA_SERVICE_PORT
            SocketView.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            SocketView.client_socket.connect((server_address, server_port))
            SocketView.receive_thread = threading.Thread(target=self.receive_message,
                                                         daemon=True).start()  # 不要加括号
            SocketView.handle_thread = threading.Thread(target=self.handle_message,
                                                        daemon=True).start()  # 不要加括号
            print(f"成功连接: {SocketView.client_socket}")

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

                    if split_values[5] == "0":
                        SocketView.receive_link_state.append({
                            "source_satellite_id": split_values[0],
                            "destination_satellite_id": split_values[1],
                            "source_satellite_interface": split_values[2],
                            "destination_satellite_interface": split_values[3],
                            "time": split_values[4],
                            "type": "network_layer"
                        })
                    else:
                        if split_values[0] == "4294967295":
                            print(f"str_data is :{str_data}")
                        SocketView.receive_link_state.append({
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

                    # sendlinkstatetofrontbysocket(self, SocketView.receive_link_state[-1])

                    # print(f"恢复的数字是{str_data}")
                if SocketView.handleMessage.startswith('0e'):
                    data = bytes.fromhex(SocketView.handleMessage)

                    # 2. 根据分析，字符串长度位于第11个字节 (索引为10)
                    # 0x2c 转换为十进制是 44，这就是字符串的长度
                    string_length = data[10]

                    # 3. 字符串内容从第12个字节 (索引为11) 开始
                    start_index = 11
                    end_index = start_index + string_length

                    # 4. 提取字节切片并用UTF-8解码为字符串
                    error_message = data[start_index:end_index].decode('utf-8')
                    # print(f"错误:{error_message}")
                if not SocketView.get_isStep():
                    # SocketView.handleMessage = SocketView.receive_queue[0]

                    if SocketView.handleMessage.startswith('07') and not SocketView.get_isPaused():
                        self.update_link_data()
                        SocketView.exataisidle = True
                        # print(f"SocketView.exataisidle 已经被设为true {SocketView.exataisidle}")
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

    def _dict_to_socketview(d: dict) -> "SocketView":
        sv = SocketView()
        sv.link_id = d.get("link_id")
        sv.time = d.get("time", -1)
        sv.node1 = d.get("node1")
        sv.node2 = d.get("node2")
        sv.interface1 = d.get("interface1")
        sv.interface2 = d.get("interface2")
        sv.ip1 = d.get("ip1", 0)
        sv.ip2 = d.get("ip2", 0)
        sv.link_type = d.get("link_type", "application_layer")
        sv.flag1 = d.get("flag1", 0)
        sv.flag2 = d.get("flag2", 0)
        sv.active_time1 = d.get("active_time1", 0)
        sv.active_time2 = d.get("active_time2", 0)
        sv.application_from_direction1 = d.get("application_from_direction1", 0)
        sv.application_from_direction2 = d.get("application_from_direction2", 0)
        sv.app_id1 = d.get("app_id1")
        sv.app_source_id1 = d.get("app_source_id1")
        sv.app_des_id1 = d.get("app_des_id1")
        sv.app_id2 = d.get("app_id2")
        sv.app_source_id2 = d.get("app_source_id2")
        sv.app_des_id2 = d.get("app_des_id2")
        sv.app_1 = d.get("app_1")
        sv.app_2 = d.get("app_2")
        return sv

    def update_link_data(self):
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
            # flag1和flag2判断网络层两个方向的通断
            update_link.flag1 = 0
            update_link.flag2 = 0
            # activetime记录连通的时间
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
            # app_1是一个三维的json数组
            update_link.app_1 = None
            update_link.app_2 = None
        # 遍历 receive_link_state 和 update_links，进行匹配并更新 update_link 对象
        applications = []
        with open("debug_log.txt", "a", encoding="utf-8") as f:
            f.write(str(SocketView.receive_link_state) + "\n\n\n")
        for receive_link_state_obj in SocketView.receive_link_state:
            # 这个if判断网络层是不是通的，
            if receive_link_state_obj["type"] == "network_layer":
                source_satellite_id = int(receive_link_state_obj["source_satellite_id"])
                destination_satellite_id = int(receive_link_state_obj["destination_satellite_id"])
                source_satellite_interface = int(receive_link_state_obj["source_satellite_interface"])
                destination_satellite_interface = int(receive_link_state_obj["destination_satellite_interface"])
                time = int(receive_link_state_obj["time"])
                # print(f"更新对象2")
                # 遍历 update_links，检查是否有匹配的 link
                for update_link in SocketView.update_links:
                    node1 = int(update_link.node1)
                    node2 = int(update_link.node2)
                    interface1 = int(update_link.interface1)
                    interface2 = int(update_link.interface2)
                    # print(
                    #     f"receive_link_state -> source_satellite_id: {source_satellite_id}, destination_satellite_id: {destination_satellite_id}, "
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
            if receive_link_state_obj["type"] == "application_layer":
                source_satellite_id = int(receive_link_state_obj["source_satellite_id"])
                destination_satellite_id = int(receive_link_state_obj["destination_satellite_id"])
                source_satellite_interface = int(receive_link_state_obj["source_satellite_interface"])
                destination_satellite_interface = int(receive_link_state_obj["destination_satellite_interface"])
                time = int(receive_link_state_obj["time"])
                linkstate_used = 0
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

                        linkstate_used = 1
                        update_link.application_from_direction1 += 1

                        # 合并 app_id1, app_source_id1, app_des_id1 为 app_1
                        new_app_id = str(receive_link_state_obj["app_id"])
                        new_app_source_id = str(receive_link_state_obj["app_source_id"])
                        new_app_des_id = str(receive_link_state_obj["app_des_id"])

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
                    elif (node1 == destination_satellite_id and
                            node2 == source_satellite_id and
                            interface1 == destination_satellite_interface and
                            interface2 == source_satellite_interface):
                        linkstate_used = 1
                        update_link.application_from_direction2 += 1

                        # 合并 app_id2, app_source_id2, app_des_id2 为 app_2
                        new_app_id = str(receive_link_state_obj["app_id"])
                        new_app_source_id = str(receive_link_state_obj["app_source_id"])
                        new_app_des_id = str(receive_link_state_obj["app_des_id"])

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
                    #     f"receive_link_state -> source_satellite_id: {source_satellite_id}, destination_satellite_id: {destination_satellite_id}, "
                    #     f"source_satellite_interface: {source_satellite_interface}, destination_satellite_interface: {destination_satellite_interface}")
                    # print(f"update_link -> node1: {node1}, node2: {node2}, "
                    #       f"interface1: {interface1}, interface2: {interface2}")

                    # 如果两个节点之间存在业务，就默认网络层是通的
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
                # if linkstate_used == 0:
                #     # 计算新的 link_id
                #     if SocketView.update_links:
                #         last_item = SocketView.update_links[-1]
                #         if isinstance(last_item, dict):
                #             new_link_id = last_item["link_id"] + 1
                #         else:  # SocketView 对象
                #             new_link_id = last_item.link_id + 1
                #     else:
                #         new_link_id = 1  # 如果列表为空，从 1 开始
                #
                #     # 创建新字典
                #     extra_dict = {
                #         "link_id": new_link_id,
                #         "time": int(-1),
                #         "node1": source_satellite_id,
                #         "node2": destination_satellite_id,
                #         "interface1": source_satellite_interface,
                #         "interface2": destination_satellite_interface,
                #         "ip1": 0,
                #         "ip2": 0,
                #         "link_type": 1,
                #         "flag1": 0,
                #         "flag2": 0,
                #         "active_time1": 0,
                #         "active_time2": 0,
                #         "application_from_direction1": 10,
                #         "application_from_direction2": 0,
                #         "app_id1": None,
                #         "app_source_id1": None,
                #         "app_des_id1": None,
                #         "app_id2": None,
                #         "app_source_id2": None,
                #         "app_des_id2": None,
                #         "app_1": None,
                #         "app_2": None
                #     }

                    # 转成 SocketView 再 append，避免类型报错
                    # SocketView.update_links.append(SocketView._dict_to_socketview(extra_dict))
                    # print(extra_dict)

                    # 构造 app_1_info
                    # new_app_id = str(receive_link_state_obj["app_id"])
                    # new_app_source_id = str(receive_link_state_obj["app_source_id"])
                    # new_app_des_id = str(receive_link_state_obj["app_des_id"])
                    # app_1_info = {
                    #     "app_id": new_app_id + new_app_source_id,
                    #     "app_source_id": new_app_source_id,
                    #     "app_des_id": new_app_des_id
                    # }
                    #
                    # # 获取刚刚 append 的最后一个 SocketView 对象
                    # last_link = SocketView.update_links[-1]
                    # if last_link.app_1:
                    #     if not any(
                    #             app["app_id"] == app_1_info["app_id"]
                    #             and app["app_source_id"] == app_1_info["app_source_id"]
                    #             and app["app_des_id"] == app_1_info["app_des_id"]
                    #             for app in last_link.app_1
                    #     ):
                    #         last_link.app_1.append(app_1_info)
                    # else:
                    #     last_link.app_1 = [app_1_info]

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
        SocketView.receive_link_state = []

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
                    link = "无线链路"
                elif update_link.link_type == "2":
                    link = "有线链路"
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
                response_data = SocketView.client_socket.recv(10000000)  # 假设响应不超过 1024 字节
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

    def _handle_connect_request(self, scene_id=None):
        global absolute_path
        global selected_scene_name

        if scene_id not in (None, ''):
            _, scene, scene_folder, error_response = _resolve_scene_runtime_context(scene_id)
            if error_response:
                return error_response
            selected_scene_name = scene.sceneName
            absolute_path = scene_folder

        SocketView.startSign = False
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

        if not selected_scene_name:
            return JsonResponse({
                "status": "error",
                "message": "\u672a\u9009\u62e9\u573a\u666f\uff0c\u8bf7\u5148\u5728\u573a\u666f\u5217\u8868\u4e2d\u9009\u62e9\u573a\u666f\u5e76\u8fdb\u5165\u4eff\u771f\u9875\u9762\u3002"
            }, status=400)

        scene_path = absolute_path.resolve(strict=False)
        required_files = [
            scene_path / "orbit.txt",
            scene_path / "node.txt",
            scene_path / "initial.txt",
        ]
        missing_files = [file_path.name for file_path in required_files if not file_path.exists()]
        if missing_files:
            return JsonResponse({
                "status": "error",
                "message": (
                    f"\u521d\u59cb\u5316\u5931\u8d25\uff0c\u7f3a\u5c11\u573a\u666f\u6587\u4ef6: {', '.join(missing_files)}\u3002"
                    f"\u5f53\u524d\u573a\u666f\u76ee\u5f55: {scene_path}"
                )
            }, status=400)

        try:
            sat_init()
        except FileNotFoundError as exc:
            missing_name = Path(exc.filename).name if exc.filename else str(exc)
            return JsonResponse({
                "status": "error",
                "message": (
                    f"\u521d\u59cb\u5316\u5931\u8d25\uff0c\u7f3a\u5c11\u5fc5\u8981\u6587\u4ef6: {missing_name}\u3002"
                    f"\u5f53\u524d\u573a\u666f\u76ee\u5f55: {scene_path}"
                )
            }, status=400)
        except Exception as exc:
            logger.error("Scene initialization failed during sat_init: %s", exc, exc_info=True)
            return JsonResponse({
                "status": "error",
                "message": f"\u521d\u59cb\u5316\u5931\u8d25\uff0c\u573a\u666f\u6587\u4ef6\u89e3\u6790\u51fa\u9519: {exc}"
            }, status=500)

        if not EXATA_MANAGED_EXTERNALLY:
            exata = create_exata_simulator(
                working_directory=absolute_path,
                config_file=f"{selected_scene_name}.config",
            )
            exata.stop_simulation()
            exata.run_simulation()
            time.sleep(3)

        try:
            self.connect_to_server()
        except ConnectionRefusedError:
            return JsonResponse({
                "status": "error",
                "message": (
                    f"\u521d\u59cb\u5316\u5931\u8d25\uff0c\u65e0\u6cd5\u8fde\u63a5 EXATA \u670d\u52a1 {EXATA_SERVICE_HOST}:{EXATA_SERVICE_PORT}\u3002"
                    "\u8bf7\u786e\u8ba4 EXATA \u5df2\u542f\u52a8\uff0c\u4e14\u5957\u63a5\u5b57\u7aef\u53e3\u53ef\u7528\u3002"
                )
            }, status=502)
        except OSError as exc:
            logger.error("Scene initialization OS error: %s", exc, exc_info=True)
            return JsonResponse({
                "status": "error",
                "message": f"\u521d\u59cb\u5316\u5931\u8d25\uff0c\u8fde\u63a5 EXATA \u65f6\u53d1\u751f\u7cfb\u7edf\u9519\u8bef: {exc}"
            }, status=500)

        SocketView.simulation_running = True
        SocketView.message_indexStep = 0
        SocketView.message_indexContinue = 0
        SocketView.send_start_message(self)
        SocketView.send_next_message(self)

        if SocketView.startSign:
            return JsonResponse({
                "status": "success",
                "message": "\u521d\u59cb\u5316\u6210\u529f"
            })

        return JsonResponse({
            "status": "error",
            "message": "\u521d\u59cb\u5316\u5b8c\u6210\uff0c\u4f46\u672a\u6536\u5230\u542f\u52a8\u786e\u8ba4\u3002"
        }, status=500)

    @csrf_exempt
    def post(self, request):
        global absolute_path
        global selected_scene_name
        content_type = request.META.get('CONTENT_TYPE')
        if content_type == 'application/json':
            data = json.loads(request.body)
            if 'connect' in data:
                return self._handle_connect_request(data.get('sceneId'))
                SocketView.startSign = False
                # 在仿真开始时，把消息队列设置为空
                # sendtofrontbysocket(request, "web socket 已经建立", "", "")

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
                if not selected_scene_name:
                    return JsonResponse({
                        "status": "error",
                        "message": "未选择场景，请先在场景列表中选择场景并进入仿真页面。"
                    }, status=400)

                scene_path = absolute_path.resolve(strict=False)
                required_files = [
                    scene_path / "orbit.txt",
                    scene_path / "node.txt",
                    scene_path / "initial.txt",
                ]
                missing_files = [file_path.name for file_path in required_files if not file_path.exists()]
                if missing_files:
                    return JsonResponse({
                        "status": "error",
                        "message": (
                            f"初始化失败，缺少场景文件: {', '.join(missing_files)}。"
                            f"当前场景目录: {scene_path}"
                        )
                    }, status=400)

                sat_init()  # 初始化各个卫星
                print(f"chushihua场景文件夹绝对路径: {absolute_path}")
                if not EXATA_MANAGED_EXTERNALLY:
                    exata = create_exata_simulator(
                        working_directory=absolute_path,
                        config_file=f"{selected_scene_name}.config",
                    )
                    exata.stop_simulation()
                #
                    exata.run_simulation()
                    time.sleep(3)
                try:
                    self.connect_to_server()
                except ConnectionRefusedError:
                    return JsonResponse({
                        "status": "error",
                        "message": (
                            f"初始化失败，无法连接 EXATA 服务 {EXATA_SERVICE_HOST}:{EXATA_SERVICE_PORT}。"
                            "请确认 EXATA 已启动并监听该端口。"
                        )
                    }, status=502)
                except OSError as exc:
                    logger.error("Scene initialization OS error: %s", exc, exc_info=True)
                    return JsonResponse({
                        "status": "error",
                        "message": f"初始化失败，系统错误: {exc}"
                    }, status=500)
                print(f"连接中")
                SocketView.simulation_running = True
                SocketView.message_indexStep = 0  # 当前发送的消息索引
                SocketView.message_indexContinue = 0  # 当前发送的消息索引
                SocketView.send_start_message(self)
                SocketView.send_next_message(self)
                if SocketView.startSign:
                    return JsonResponse({"status": "success", "message": "初始化成功"})
                else:
                    return JsonResponse({
                        "status": "error",
                        "message": "初始化完成，但未收到启动确认。"
                    }, status=500)

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
                time.sleep(4)
                y = self.pause_simulation()
                return JsonResponse(y)
            elif 'continuesimulation' in data:

                y = self.continue_simulation()
                return JsonResponse(y)
            elif 'stepsimulation' in data:

                y = self.step_simulation()
                return JsonResponse(y)
            elif 'stopsimulation' in data:
                # subprocess.Popen(['daphne', '-b', '0.0.0.0', '-p', '8001', 'mytest.asgi:application'])
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

        SocketView.startSign = False
        # 在仿真开始时，把消息队列设置为空
        # sendtofrontbysocket(request, "web socket 已经建立", "", "")
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
        if EXATA_MANAGED_EXTERNALLY:
            return {"status": "仿真已停止，EXATA 由外部宿主机管理"}
        exata = create_exata_simulator(
            working_directory=absolute_path,
            config_file=f"{selected_scene_name}.config",
        )
        exata.stop_simulation()
        script_path = EXATA_RESTART_SCRIPT

        if not os.path.exists(script_path):
            print(f"错误：重启脚本 '{script_path}' 未找到。无法重启服务。")
            # 即使重启失败，仿真停止的指令也已完成
            return {"status": "停止仿真但重启失败"}

        try:
            # 使用 Popen 启动一个独立的进程来执行重启脚本。
            # 这一步和之前一样。
            print(f"正在启动外部重启脚本: {script_path}")
            subprocess.Popen([script_path], shell=True)

            # 【关键步骤】
            # 在发出重启命令后，当前进程的使命已经完成。
            # 我们必须在这里让它干净地退出，以便 .bat 脚本可以顺利地杀死它。
            print("重启命令已发出，当前服务进程将立即退出。")

            # 使用 sys.exit() 来请求一个干净的退出。
            # .bat 中的 taskkill 会确保它被强制终止。
            sys.exit(0)

        except Exception as e:
            print(f"错误：执行重启脚本时发生异常: {e}")
            # 即使重启失败，仿真停止的指令也已完成
            return {"status": "停止仿真但重启失败"}

        # 这之后的代码理论上不会被执行，因为 sys.exit() 了
        # 但为了函数完整性，可以保留一个返回值
        return {"status": "停止仿真，重启中..."}


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
                SocketView.read_node_file(self)  #每次都会读取节点的信息
                self.read_message_file(current_path)  # 读取消息文件并初始化队列
                response = self.send_next_message()

    def read_initial_config(self, initial_file):
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
                        # print("intinalintinalintinalintinalintinal" + SocketView.interval)
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

    def read_message_file(self, current_path):
        """读取消息文件并将符合条件的消息加入队列"""
        SocketView.config_file = current_path / "config_no_move.txt"
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
                                    # print(f"hex_altitude: {hex_altitude}")
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

                            if SocketView.initial_k == 1:
                                # SocketView.satellites.append({
                                #     "satellite_id": "satellite_" + command_parts[1],
                                #     "lat": command_parts[4],
                                #     "lon": command_parts[6],
                                #     "alt": command_parts[8],
                                #     "type": None,
                                #     "name": None,
                                #     "error_interface": None,
                                #     "print_link": None,
                                # })
                                # print('SocketView.send_queue.append(final_command)')
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
                                    # print(f"hex_altitude: {hex_altitude}")
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


    def rename_stat_file_to_current_time(folder_path='.'):
        """
        在指定文件夹下查找 exata.stat 文件，并将其重命名为当前时间格式（YYYYMMDDHHMM.stat）。

        参数:
        folder_path (str): 要搜索的目标文件夹路径。默认为当前脚本所在的目录。
        """
        original_filename = 'exata.stat'
        # 使用 os.path.join 来正确地组合路径和文件名
        full_original_path = os.path.join(folder_path, original_filename)

        # 1. 检查文件是否存在
        if os.path.exists(full_original_path):
            # 2. 获取当前系统时间
            now = datetime.now()  # <-- 修改在这里：现在调用更简洁

            # 3. 按照 "年(4位)月(2位)日(2位)小时(2位)分钟(2位)" 的格式创建新文件名
            #    例如: 202508160247.stat
            new_filename_base = now.strftime("%Y%m%d%H%M")

            # 保留原始文件的扩展名 .stat
            file_extension = os.path.splitext(original_filename)[1]
            new_filename = f"{new_filename_base}{file_extension}"

            # 组合成完整的新文件路径
            full_new_path = os.path.join(folder_path, new_filename)

            # 4. 执行重命名操作
            try:
                os.rename(full_original_path, full_new_path)
                print(f"成功：已将文件 '{full_original_path}' 重命名为 '{full_new_path}'")
            except OSError as e:
                print(f"错误：重命名文件时发生错误。 {e}")
        else:
            # 5. 如果文件不存在，则打印提示信息
            print(f"未找到文件：在文件夹 '{os.path.abspath(folder_path)}' 中未找到 '{original_filename}'")

    def send_next_message(self):
        """发送队列中的下一条消息"""
        while True:
            if SocketView.send_queue:
                # 用于开始暂停过的仿真
                SocketView.simulation_running = True
                message = SocketView.send_queue[0]
                # print(f"发送消息队列：{SocketView.send_queue}")发送给exata的
                SocketView.send_queue.remove(SocketView.send_queue[0])
                encoded_message = bytes.fromhex(message)
                # print(f"已发送消息: {message}")
                if message.startswith('06'):
                    time.sleep(0.5)
                    # print("nihao")
                try:
                    if message == SocketView.over_controlmessage:
                        time.sleep(3)

                    if message == SocketView.controlmessage:
                        time.sleep(3)
                        SocketView.controlmessage = ""

                    SocketView.client_socket.sendall(encoded_message)
                    # time.sleep(0.5)
                    SocketView.message_indexContinue += 1
                    if message == SocketView.over_controlmessage:
                        time.sleep(3)
                        SocketView.rename_stat_file_to_current_time(absolute_path)
                        SocketView.over_controlmessage = ""
                    if message == '03 00 00 00 00 00 00 08':
                        SocketView.startSign = True
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
            print(f"if not SocketView.simulation_running:")
            SocketView.simulation_running = True  # 继续仿真
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

