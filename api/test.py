from pathlib import Path

import matplotlib.pyplot as plt
import os
import glob
import re
import math

"""带宽利用率：读取所有文件，绘制时间与带宽利用率的图"""
def extract_node_number(filename):
    """从文件名中提取节点编号"""
    match = re.search(r'node(\d+)', filename)
    return int(match.group(1)) if match else 0


def read_slot_stats(file_path):
    """读取单个slot_stats文件"""
    cycles = []
    percentages = []
    with open(file_path, 'r', encoding='utf-8-sig') as f:  # 添加编码参数
        for line in f:
            line = line.strip()
            if ',' in line:
                parts = line.split(',')
                # 更健壮的周期数提取方式
                cycle_str = parts[0].replace('period', '').strip()  # 移除"周期"文字
                try:
                    cycle_num = int(cycle_str)*12 #周期*3=时间
                    value = float(parts[1])
                    cycles.append(cycle_num)
                    percentages.append(value * 100)  # 转换为百分比
                except (ValueError, IndexError) as e:
                    print(f"警告: 文件 {os.path.basename(file_path)} 中跳过无效行: {line} ({str(e)})")
    return cycles, percentages


def plot_all_nodes_subplots(folder_path):
    """绘制所有节点的全部包数据，每个节点一个子图"""
    # 创建第一个图形窗口
    fig1 = plt.figure(1, figsize=(15, 10))

    # 查找所有slot_stats_node*.txt文件
    file_pattern = os.path.join(folder_path, "slot_stats_node*.txt")
    file_paths = sorted(glob.glob(file_pattern), key=extract_node_number)

    if not file_paths:
        print(f"在文件夹 {folder_path} 中未找到 slot_stats_node*.txt 文件")
        return

    # 计算需要的行数和列数（每行最多3个子图）
    num_nodes = len(file_paths)
    cols = min(3, num_nodes)
    rows = math.ceil(num_nodes / cols)

    for i, file_path in enumerate(file_paths):
        node_num = extract_node_number(file_path)
        cycles, percentages = read_slot_stats(file_path)

        # 在当前图形中添加子图
        ax = fig1.add_subplot(rows, cols, i + 1)

        ax.plot(
            cycles, percentages,
            color='tab:blue',
            marker='o',
            markersize=1,
            linewidth=1
        )

        ax.set_title(f'Node {node_num}', pad=5, fontsize=8)
        ax.set_xlabel('Time')
        ax.set_ylabel('Bandwidth Usage(%)')
        ax.set_ylim(0, 50)
        ax.grid(True, linestyle=':', alpha=0.6)

    # 为第一个图形设置总标题和布局
    fig1.suptitle('Total Bandwidth Usage', fontsize=16, y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.96])  # 为总标题留出空间

    return fig1


def plot_bus_nodes_subplots(folder_path):
    """绘制所有节点的业务包数据，每个节点一个子图"""
    # 创建第二个图形窗口
    fig2 = plt.figure(2, figsize=(15, 10))

    # 查找所有slot_stats_node*.txt文件
    file_pattern = os.path.join(folder_path, "busslot_stats_node*.txt")
    file_paths = sorted(glob.glob(file_pattern), key=extract_node_number)

    if not file_paths:
        print(f"在文件夹 {folder_path} 中未找到 busslot_stats_node*.txt 文件")
        return

    # 计算需要的行数和列数（每行最多3个子图）
    num_nodes = len(file_paths)
    cols = min(3, num_nodes)
    rows = math.ceil(num_nodes / cols)

    for i, file_path in enumerate(file_paths):
        node_num = extract_node_number(file_path)
        cycles, percentages = read_slot_stats(file_path)

        # 在当前图形中添加子图
        ax = fig2.add_subplot(rows, cols, i + 1)

        ax.plot(
            cycles, percentages,
            color='tab:red',
            marker='o',
            markersize=1,
            linewidth=1
        )

        ax.set_title(f'Node {node_num}', pad=5, fontsize=8)
        ax.set_xlabel('Time')
        ax.set_ylabel('Bus-Bandwidth Usage(%)')
        ax.set_ylim(0, 20)
        ax.grid(True, linestyle=':', alpha=0.6)

    # 为第二个图形设置总标题和布局
    fig2.suptitle('Bus Bandwidth Usage', fontsize=16, y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.96])  # 为总标题留出空间

    return fig2

# 使用示例
if __name__ == "__main__":
    folder_path = Path(r"D:\Code\exata\815\mytestdjango_five8_29\scene_files\xkztest\outfile")
    # 使用默认模式
    fig1=plot_all_nodes_subplots(folder_path)
    # 使用自定义模式
    fig2=plot_bus_nodes_subplots(folder_path)
    plt.show()