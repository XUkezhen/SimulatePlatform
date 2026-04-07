import math
from geopy.distance import geodesic


class StaticDynamicLinkCalculator:
    # 包含每个时间片的全部规划链路
    static_link = []

    def __init__(self, input_filename, config_filename, output_filename):
        """
        初始化文件路径和时间范围
        """
        self.input_filename = input_filename
        self.config_filename = config_filename
        self.output_filename = output_filename

    def read_static_link(self, start_time, end_time):
        """
        读取静态链接文件，检查时间是否在指定范围内。
        支持解析新的输入格式：时间 节点1 节点2 IP1 IP2
        """
        StaticDynamicLinkCalculator.static_link = []

        try:
            with open(self.input_filename, 'r') as file:
                for line in file:
                    parts = line.strip().split()
                    if len(parts) == 9:
                        # 解析时间和节点
                        link_id = int(parts[0])
                        time = int(parts[1])
                        node1 = int(parts[2])
                        node2 = int(parts[3])
                        interface1 = int(parts[4])
                        interface2 = int(parts[5])
                        # 解析 IP 地址
                        ip1 = parts[6]
                        ip2 = parts[7]
                        link_type = parts[8]
                        if start_time <= time < end_time:
                            # 将完整的记录加入列表
                            StaticDynamicLinkCalculator.static_link.append(
                                (link_id, time, node1, node2, interface1, interface2, ip1, ip2, link_type))
                        if time == -1:
                            StaticDynamicLinkCalculator.static_link.append(
                                (link_id, time, node1, node2, interface1, interface2, ip1, ip2, link_type))
                            # print(static_link)

        except FileNotFoundError:
            print(f"Error: File '{self.input_filename}' not found.")
        except Exception as e:
            print(f"Unexpected error: {e}")


    def read_platform_data(self):
        """
        从 config.txt 中读取平台节点的纬度、经度和高度信息。
        """
        platform_data = []

        try:
            with open(self.config_filename, 'r') as file:
                for line in file:
                    # 匹配 CREATEPLATFORM 和 UPDATEPLATFORM 格式
                    if "CREATEPLATFORM" in line or "UPDATEPLATFORM" in line:
                        parts = line.strip().split()
                        try:
                            platform_id = int(parts[1][4:])  # 提取 PLAT 后的编号
                            lat_index = parts.index("LAT") + 1
                            lon_index = parts.index("LON") + 1
                            alt_index = parts.index("ALT") + 1
                            lat = float(parts[lat_index])
                            lon = float(parts[lon_index])
                            alt = float(parts[alt_index])
                            platform_data.append((platform_id, lat, lon, alt))
                        except (ValueError, IndexError):
                            continue
        except FileNotFoundError:
            print(f"Error: File '{self.config_filename}' not found.")
        except Exception as e:
            print(f"Unexpected error: {e}")

        return platform_data

    @staticmethod
    def compute_orientation(lat1, lon1, alt1, lat2, lon2, alt2):
        """
        计算方位角和俯仰角。
        """
        # 使用 geopy 计算地表距离（忽略高度）
        surface_distance = geodesic((lat1, lon1), (lat2, lon2)).meters

        # 高度差
        height_difference = alt2 - alt1

        # 计算俯仰角
        elevation = int(math.degrees(math.atan2(height_difference, surface_distance)))

        # 计算方位角
        dlon = math.radians(lon2 - lon1)
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)

        x = math.sin(dlon) * math.cos(lat2_rad)
        y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
        azimuth = int((math.degrees(math.atan2(x, y)) + 360) % 360)  # 转为 [0, 360) 范围
        azimuth -= 90
        azimuth = (azimuth + 360) % 360  # 确保非负数

        return azimuth, elevation

    def append_orientation_to_file(self, start_time, end_time):
        """
        根据静态链路和平台数据，计算节点间的方位角和俯仰角，并写入文件。
        """
        self.read_static_link(start_time, end_time)
        platform_data = self.read_platform_data()
        # 将 platform_data 转换为字典，方便查找
        platform_dict = {entry[0]: entry[1:] for entry in platform_data}

        with open(self.output_filename, 'a') as file:
            for link_id, time, node1, node2, interface1, interface2, ip1, ip2, link_type in StaticDynamicLinkCalculator.static_link:
                if time != -1:
                    if node1 in platform_dict and node2 in platform_dict:
                        # 获取节点经纬度和高度信息
                        lat1, lon1, alt1 = platform_dict[node1]
                        lat2, lon2, alt2 = platform_dict[node2]

                        # 计算节点1指向节点2的方位角和俯仰角
                        azimuth1, elevation1 = self.compute_orientation(lat1, lon1, alt1, lat2, lon2, alt2)

                        # 计算节点2指向节点1的方位角和俯仰角
                        azimuth2, elevation2 = self.compute_orientation(lat2, lon2, alt2, lat1, lon1, alt1)

                        # 写入文件，分别写 AZIMUTH 和 ELEVATION
                        file.write(
                            f"Write {time} PATH /platform/PLAT{node1}/interface/{ip1}/PHY-ABSTRACT-AZIMUTH ARGS {azimuth1} {node2} {ip2} {link_id} \n")
                        file.write(
                            f"Write {time} PATH /platform/PLAT{node1}/interface/{ip1}/PHY-ABSTRACT-ELEVATION ARGS {elevation1} {node2} {ip2} false \n")
                        file.write(
                            f"Write {time} PATH /platform/PLAT{node2}/interface/{ip2}/PHY-ABSTRACT-AZIMUTH ARGS {azimuth2} {node1} {ip1} false \n")
                        file.write(
                            f"Write {time} PATH /platform/PLAT{node2}/interface/{ip2}/PHY-ABSTRACT-ELEVATION ARGS {elevation2} {node1} {ip1} false \n")


# 测试代码
if __name__ == "__main__":
    # 配置文件路径和时间范围
    calculator = StaticDynamicLinkCalculator(
        input_filename='linksshort.txt',
        config_filename='config.txt',
        output_filename='config.txt',
    )
    calculator.append_orientation_to_file(0, 60)
