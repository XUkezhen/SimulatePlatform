from django.db.models import Count
from .models import Scene, Node

def get_node_count_for_scene(scene_id):
    """
    查询指定场景中包含的节点个数
    :param scene_id: 场景的 ID
    :return: 节点个数
    """
    try:
        # 查询指定场景
        scene = Scene.objects.get(id=scene_id)
        # 查询该场景中包含的节点个数
        node_count = scene.nodes.count()
        return node_count
    except Scene.DoesNotExist:
        return None

def generate_config_file():
    # 配置文件内容
    config_content = f"""
# ***** EXata Configuration File *****
    
#********************General Settings***********************************
    
VERSION 17.03
EXPERIMENT-NAME exata
EXPERIMENT-COMMENT NONE
SIMULATION-TIME 30M
SEED 1
MULTI-GUI-INTERFACE NO
GUI-CONFIG-LOCKED NO
DUMMY-GLOBAL-FILTER-ENABLE NO
NUM-NODES {get_node_count_for_scene(17)}

#*******************Parallel Settings***********************************

PARTITION-SCHEME AUTO
GESTALT-PREFER-SHARED-MEMORY YES
        """
    # 保存配置文件
    config_file_path = "config_file.txt"  # 替换为实际路径
    with open(config_file_path, 'w') as config_file:
        config_file.write(config_content)

