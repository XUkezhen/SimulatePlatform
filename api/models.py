import ipaddress

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError



# 3.7号下午   本版本修改了node模型，接口模型未设置，链路模型没改。。
# 3.9晚上9点，新建了接口模型，链路模型一并修改。
#3.11 下午 views 添加get 函数
#3.13 凌晨 修改完映射表
#3.15xiu该链路表
#4.30 完成.app的调试。未完成。postman出错
#5.25上午修改，add_link函数。
#下午修改生成文件，改动的是单独的那个生成函数,模板文件和生成函数都变了,download也变了。
# 修改link函数。
#5.25晚 结果分析在最新版上，未完成向前端传送。
#5.26 修改了edit节点函数。image属性再看看
#5.30修改了dowmload函数，可以下载生成文件
#6.3 修改了模板文件，但是down函数还没有更新到 最新版！！！！！！！（已更新）
#6.5 上午，修改get_node函数，可以返回IP地址。继续弄结果交互。还没更新到最新版
#6.10 下午，8002已全部更新完毕，下一步，子网配置
#6.12上午，子网
class Scene(models.Model):
    sceneName = models.CharField(max_length=100)
    startTime = models.DateTimeField()
    endTime = models.DateTimeField()
    simulationStep = models.IntegerField()  # 新增仿真步长字段

    def __str__(self):
        return self.sceneName

    def clean(self):
        # 验证开始时间早于结束时间
        if self.startTime and self.endTime and self.startTime >= self.endTime:
            raise ValidationError("End time must be after start time")

        # 验证仿真步长为正整数
        if self.simulationStep <= 0:
            raise ValidationError("Simulation step must be a positive integer")

        # 验证场景名称唯一
        if Scene.objects.filter(sceneName=self.sceneName).exclude(id=self.id).exists():
            raise ValidationError("Scene name must be unique")

        return super().clean()

    def save(self, *args, **kwargs):
        self.clean()  # 在保存前执行验证
        super().save(*args, **kwargs)


class Node(models.Model):
    NODE_TYPES = [
        ('satellite', 'Satellite'),
        ('normalNode', 'Normal Node'),
    ]

    sceneId = models.ForeignKey('Scene', on_delete=models.CASCADE, related_name='nodes', null=True, blank=True)
    nodeName = models.CharField(max_length=255)
    nodeImage = models.CharField(max_length=255)
    nodeType = models.CharField(max_length=50, choices=NODE_TYPES)

    # normalNode 特有字段
    lon = models.FloatField(null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    alt = models.FloatField(null=True, blank=True)
    startTime = models.DateTimeField(null=True, blank=True)

    # satellite 特有字段
    eccentricity = models.FloatField(null=True, blank=True)  # 偏心率
    argPerigee = models.FloatField(null=True, blank=True)     # 近地点幅角
    inclination = models.FloatField(null=True, blank=True)    # 轨道倾角
    meanAnomaly = models.FloatField(null=True, blank=True)    # 平近点角
    meanMotion = models.FloatField(null=True, blank=True)     # 均运动
    raan = models.FloatField(null=True, blank=True)           # 升交点赤经

    # 途经信息
    viaPoints = models.JSONField(null=True, blank=True)  # 使用 JSONField 存储途径点
    # 新增的 details 字段
    details = models.JSONField(null=True, blank=True)  # 使用 JSONField 存储详情
    class Meta:
        unique_together = ('sceneId', 'nodeName')

    def __str__(self):
        return self.nodeName

    def clean(self):
        # 验证节点类型特定字段
        if self.nodeType == 'satellite':
            if not all([self.eccentricity, self.argPerigee, self.inclination,
                        self.meanAnomaly, self.meanMotion, self.raan, self.startTime]):
                raise ValidationError("Satellite nodes require all orbital elements and startTime.")
        elif self.nodeType == 'normalNode':
            if not all([self.lon, self.lat, self.alt, self.startTime]):
                raise ValidationError("Normal nodes require lon, lat, alt, and startTime.")
            if self.viaPoints:
                try:
                    # 验证 viaPoints 格式
                    if not isinstance(self.viaPoints, list):
                        raise ValidationError("viaPoints must be a JSON list of points.")
                    for point in self.viaPoints:
                        if not isinstance(point, dict):
                            raise ValidationError("Each viaPoint must be a dictionary.")
                        if 'lon' not in point or 'lat' not in point or 'alt' not in point or 'time' not in point:
                            raise ValidationError("Each viaPoint must contain 'lon', 'lat', 'alt', and 'time'.")
                except (TypeError, ValueError):
                    raise ValidationError("viaPoints must be valid JSON.")
class Configuration(models.Model):
    BUSINESS_TYPE_CHOICES = (
        ('CBR', 'CBR'),
        ('FTP', 'FTP'),
    )
    sceneId = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name='configurations', default=12)
    businessType = models.CharField(max_length=10, choices=BUSINESS_TYPE_CHOICES,default='CBR')
    businessName = models.CharField(max_length=255)
    sourceNodeId = models.ForeignKey(Node, on_delete=models.CASCADE, related_name='source_configurations')
    destinationNodeId = models.ForeignKey(Node, on_delete=models.CASCADE, related_name='destination_configurations')
    # CBR 业务类型的详细配置
    cbrStartTime = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    cbrEndTime = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    cbrSendInterval = models.IntegerField(null=True, blank=True, verbose_name='发送间隔')
    cbrPacketSize = models.IntegerField(null=True, blank=True, verbose_name='发送包大小')
    # FTP 业务类型的详细配置
    ftpStartTime = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    ftpPacketCount = models.IntegerField(null=True, blank=True, verbose_name='发送包的数量')


class Subnet(models.Model):
    class SubnetTypeChoices(models.TextChoices):
        SUB = 'sub', '子网（sub）'
        LINK = 'link', '链路（link）'

    sceneId = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name='subnets', default=12)
    subnetName = models.CharField(max_length=255)
    subnetIp = models.GenericIPAddressField()
    subnetMask = models.GenericIPAddressField()

    subnetType = models.CharField(
        max_length=10,
        choices=SubnetTypeChoices.choices,
        default=SubnetTypeChoices.SUB,
        verbose_name="子网类型"
    )

    def __str__(self):
        return self.subnetName

DEFAULT_INTERFACE_DETAIL = {
    "Physical": {
        "ListenableChannel": "Channel1",
        "ListeningChannel": "Channel1",
        "Radiotype": "802.11bRadio",
        "RadioOverlayID": "[Optional]",
        "EnableAutoRateFallback": "No",
        "DataRata": "2Mbps",
        "FrequencyBand": "2.4GHz",
        "CountryCode": "SpecifyWiFiCountryProfilesFileinScenarioPropertiesEditorSupplementalFiles",
        "ChannelIndexfor20MHz": "6",
        "TransmissionPowerat1Mbps": "15.0",
        "TransmissionPowerat2Mbps": "15.0",
        "TransmissionPowerat55Mbps": "15.0",
        "TransmissionPowerat11Mbps": "15.0",
        "UseLegacy80211bPHYValues": "No",
        "ReceiveSensitivityat1Mbps": "-82.0",
        "ReceiveSensitivityat2Mbps": "-80.0",
        "ReceiveSensitivityat55Mbps": "-78.0",
        "ReceiveSensitivityat11Mbps": "-76.0",
        "PacketReceptionModel": "PHY802.11aReceptionModel",
        "SpecifyAntennaModelfromFile": "No",
        "AntennaModel": "Omnidirectional",
        "AntennaGain": "0.0",
        "AntennaHeight": "1.5",
        "AntennaEfficiency": "0.8",
        "AntennaMismatchLoss": "0.3",
        "AntennaCableLoss": "0.0",
        "AntennaConnectionLoss": "0.2",
        "AntennaOrientationAzimuth": "0",
        "AntennaOrientationElevation": "0",
        "AntennaOrientationRoll": "0",
        "AntennaOrientationAzimuthSpeed": "0",
        "Temperature": "290.0",
        "NoiseFactor": "10.0",
        "EnergyModel": "None"
    },
    "MAC": {
        "MACProtocol": "802.11",
        "ShortPacketTransmitLimit": "7",
        "LongPacketTransmitLimit": "4",
        "RTSThreshold": "0",
        "StopReceivingafterHeaderMode": "No",
        "StationAssociationType": "None",
        "SecurityProtocol": "None",
        "SpecifyNetworkSecurityParameters": "No",
        "DatabaseControl": "NONE",
        "MACPropagationDelay": "1",
        "MACPropagationDelayTimeType": "microSeconds",
        "EnablePromiscuousMode": "No",
        "EnableLLC": "No",
        "ConfigureMediaType": "No",
        "ConfigureMACAddress": "No"
    },
    "Network": {
        "NetworkProtocol": "IPv4",
        "IPv4Address": "169.0.0.1",
        "IPv4SubnetMask": "255.255.255.0",
        "IPFragmentationUnit": "2048",
        "EnableExplicitCongestionNotification": "No",
        "EnableMobileIP": "No",
        "IPInputQueueSize": "150000",
        "IPOutputQueueScheduler": "StrictPriority",
        "SpecifyPerHopBehaviorFile": "No",
        "EnableIFFCertification": "No",
        "EnableEavesdropping": "No",
        "EnableARP": "No",
        "EnableDHCP": "No",
        "EnableDNS": "No",
        "PacketDropProbability": "0.0",
        "SpecifyPacketDelay": "No"
    },
    "Routing": {
        "RoutingProtocolIPv4": "BellmanFord",
        "EnableMulticast": "No",
        "EnableHSRPProtocol": "No",
        "EnableMulticastSourceDiscoveryProtocol": "No"
    },
    "Application": {
        "EnableEmulatedFTP": "Yes",
        "EnableEmulatedHTTP": "Yes",
        "EnableEmulatedTELNET": "Yes"
    },
    "File": {
        "PHYRadio": "Yes",
        "MAC": "Yes",
        "IPInputQueue": "Yes",
        "IPInputScheduler": "No",
        "IPOutputScheduler": "No",
        "IPOutputSchedulergraph": "No"
    },
    "Faults": {}
}

class Interface(models.Model):
    class InterfaceTypeChoices(models.TextChoices):
        SUB = 'sub', 'Subnet Interface'
        LINK = 'link', 'Link Interface'

    node = models.ForeignKey(
        'Node',
        on_delete=models.CASCADE,
        related_name='interfaces'
    )
    interfaceIp = models.GenericIPAddressField(verbose_name="IP Address", null=True, blank=True, default=None)
    interfaceIndex = models.IntegerField(verbose_name="Interface Index", null=True, blank=True, default=None)
    subnetMask = models.CharField(max_length=50, verbose_name="Subnet Mask", default=None)
    is_default = models.BooleanField(default=True, verbose_name="Default Gateway")
    is_allocated = models.BooleanField(default=False, verbose_name="IP Allocated")
    subnet = models.ForeignKey(
        'Subnet',
        on_delete=models.CASCADE,
        related_name='interfaces',
        null=True,
        blank=True
    )
    interfaceType = models.CharField(
        max_length=10,
        choices=InterfaceTypeChoices.choices,
        default=InterfaceTypeChoices.SUB,
        verbose_name="Interface Type"
    )

    detail = models.JSONField(
        default=DEFAULT_INTERFACE_DETAIL,
        verbose_name="Interface Detail"
    )

    class Meta:
        unique_together = ('node', 'interfaceIndex')
        ordering = ['node', 'interfaceIndex']
        verbose_name = "Network Interface"
        verbose_name_plural = "Network Interfaces"

    def __str__(self):
        return f"{self.node.nodeName} - Interface {self.interfaceIndex} ({self.interfaceIp}/{self.subnetMask})"

    def clean(self):
        if self.interfaceIndex is not None and (self.interfaceIndex < 0 or self.interfaceIndex > 3):
            raise ValidationError("Interface index must be between 0 and 3")

        if self.subnetMask:
            try:
                network = ipaddress.IPv4Network(f"0.0.0.0/{self.subnetMask}", strict=False)
                mask_value = int(network.netmask)
                bin_str = bin(mask_value)[2:].zfill(32)
                if '01' in bin_str:
                    raise ValidationError("Invalid subnet mask format")
            except (ipaddress.AddressValueError, ValueError):
                raise ValidationError("Invalid subnet mask format")

        if self.interfaceIp and self.subnetMask:
            try:
                ip_address = ipaddress.IPv4Address(self.interfaceIp)
                network = ipaddress.IPv4Network(f"{self.interfaceIp}/{self.subnetMask}", strict=False)
                if ip_address == network.network_address:
                    raise ValidationError("IP address cannot be the network address")
                if ip_address == network.broadcast_address:
                    raise ValidationError("IP address cannot be the broadcast address")
            except ipaddress.AddressValueError as e:
                raise ValidationError(f"Invalid IP or subnet mask: {str(e)}")
            except ValueError as e:
                raise ValidationError(f"IP/subnet mismatch: {str(e)}")

    def save(self, *args, **kwargs):
        self.clean()

        if self.detail:
            self.detail.setdefault('Network', {})
            self.detail['Network']['IPv4Address'] = self.interfaceIp
            self.detail['Network']['IPv4SubnetMask'] = self.subnetMask

        if self.is_default:
            Interface.objects.filter(
                node=self.node,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        node = self.node  # 先保存 node 引用
        super().delete(*args, **kwargs)
        # 删除后重排当前 node 的接口 index
        interfaces = Interface.objects.filter(node=node).order_by('interfaceIndex')
        for i, iface in enumerate(interfaces):
            if iface.interfaceIndex != i:
                iface.interfaceIndex = i
                iface.save(update_fields=['interfaceIndex'])

class Link(models.Model):
    sceneId = models.ForeignKey(Scene, on_delete=models.CASCADE)
    LINK_TYPE_CHOICES = [
        ('有线', '有线'),
        ('无线', '无线'),
    ]
    linkName = models.CharField(max_length=255)
    sourceNodeId = models.ForeignKey(Node, on_delete=models.CASCADE, related_name='source_links')
    destinationNodeId = models.ForeignKey(Node, on_delete=models.CASCADE, related_name='destination_links')
    linkType = models.CharField(max_length=50, choices=LINK_TYPE_CHOICES)
    bandwidth = models.FloatField(verbose_name='带宽(Mbps)')
    packetHeaderSize = models.IntegerField(verbose_name='包头大小(Byte)')
    transmissionDelay = models.FloatField(verbose_name='传输延迟(ms)', null=True, blank=True)
    packetLossRate = models.FloatField(verbose_name='丢包率(%)', null=True, blank=True)
    transmissionSpeed = models.FloatField(verbose_name='传输速度(Mb/s)', null=True, blank=True)
    subnetIp = models.GenericIPAddressField()
    subnetMask = models.CharField(max_length=50)
    sourceInterface = models.OneToOneField(Interface, on_delete=models.CASCADE, related_name='source_link', null=True, blank=True)
    destinationInterface = models.OneToOneField(Interface, on_delete=models.CASCADE, related_name='destination_link', null=True, blank=True)
    subnet = models.ForeignKey(Subnet, on_delete=models.CASCADE, related_name='links', null=True, blank=True)  # 关联子网

    def __str__(self):
        return f"{self.linkName} (Source: {self.sourceNodeId.nodeName}, Destination: {self.destinationNodeId.nodeName})"

    def delete(self, *args, **kwargs):
        # Step 1: 删除两个接口（如果存在）
        if self.sourceInterface:
            self.sourceInterface.delete()
        if self.destinationInterface:
            self.destinationInterface.delete()

        # Step 2: 检查子网是否还被其他接口使用
        if self.subnet:
            related_interface_count = Interface.objects.filter(subnet=self.subnet).count()
            if related_interface_count == 0:
                self.subnet.delete()

        # Step 3: 删除链路自身
        super().delete(*args, **kwargs)
class Error(models.Model):
    sceneId = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name='nodeerrors', default=12)
    nodeId = models.ForeignKey(Node, on_delete=models.CASCADE, related_name='errors')
    errorStartTime = models.DateTimeField(null=True, blank=True, default=timezone.now)
    errorEndTime = models.DateTimeField(null=True, blank=True, default=timezone.now)

class LinkError(models.Model):
    sceneId = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name='linkerrors', default=12)
    linkId = models.ForeignKey(Link, on_delete=models.CASCADE, related_name='errors')
    errorStartTime = models.DateTimeField(null=True, blank=True, default='2025-01-16T01:00:00+00:00')
    errorEndTime = models.DateTimeField(null=True, blank=True, default='2025-01-16T01:00:00+00:00')
    # linkName = models.CharField(max_length=255)
    # sourceNodeName = models.CharField(max_length=255)  # 新增字段存储源节点名称
    # destinationNodeName = models.CharField(max_length=255)  # 新增字段存储目的节点名称

class NodeTemplate(models.Model):
    templateInfo = models.TextField()  # 节点信息
    templateName = models.CharField(max_length=255, unique=True)  # 节点名称
    templateType = models.CharField(max_length=50)  # 节点类型

class NodeMapping(models.Model):
    sceneId = models.ForeignKey('Scene', on_delete=models.CASCADE, related_name='mappings')
    interface = models.ForeignKey(Interface, on_delete=models.CASCADE, related_name='mappings')
    mappingIp = models.GenericIPAddressField()

class PhysicalLayer(models.Model):
    RADIO_TYPES = [
        ('Abstract', 'Abstract'),
        ('802.11b', '802.11b'),
        # 其他无线电类型
    ]
    ANTENNA_TYPES = [
        ('Omnidirectional', 'Omnidirectional'),
        ('Patterned', 'Patterned'),
    ]
    PATTERN_TYPES = [
        ('Ascii2d', 'Ascii2d'),
        # 其他图案类型
    ]

    interface = models.OneToOneField(Interface, on_delete=models.CASCADE, related_name='physical_layer')
    radioType = models.CharField(max_length=50, choices=RADIO_TYPES)
    radioCoverageId = models.CharField(max_length=50, blank=True, null=True)
    centerFrequency = models.FloatField(blank=True, null=True)
    bandwidth = models.FloatField(blank=True, null=True)
    dataRate = models.FloatField(blank=True, null=True)
    transmitPower = models.FloatField(blank=True, null=True)
    receiveSensitivity = models.FloatField(blank=True, null=True)
    receiveThreshold = models.FloatField(blank=True, null=True)
    antennaType = models.CharField(max_length=50, choices=ANTENNA_TYPES)
    gain = models.FloatField(default=0.0)
    height = models.FloatField(default=1.5)
    efficiency = models.FloatField(default=0.8)
    mismatchLoss = models.FloatField(default=0.3)
    cableLoss = models.FloatField(default=0.0)
    connectionLoss = models.FloatField(default=0.2)
    azimuth = models.FloatField(default=0)
    elevation = models.FloatField(default=0)
    roll = models.FloatField(default=0)
    patternType = models.CharField(max_length=50, choices=PATTERN_TYPES, blank=True, null=True)
    patternNumber = models.CharField(max_length=50, blank=True, null=True)
    azimuthPatternFile = models.FileField(upload_to='antenna/azimuth/', blank=True, null=True)
    elevationPatternFile = models.FileField(upload_to='antenna/elevation/', blank=True, null=True)
    patternCoverageParameter = models.FloatField(blank=True, null=True)
    azimuthResolution = models.FloatField(blank=True, null=True)
    elevationResolution = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f"Physical Layer for {self.interface.node.nodeName} - Interface {self.interface.interface_index}"


class MacLayer(models.Model):
    MAC_PROTOCOLS = [
        ('802.11', '802.11'),
        # 其他MAC协议
    ]

    interface = models.OneToOneField(Interface, on_delete=models.CASCADE, related_name='mac_layer')
    macProtocol = models.CharField(max_length=50, choices=MAC_PROTOCOLS)
    shortPacketLimit = models.IntegerField(default=7)
    longPacketLimit = models.IntegerField(default=4)
    rtsThreshold = models.IntegerField(default=0)
    macPropagationDelay = models.FloatField(default=1)  # 微秒

    def __str__(self):
        return f"MAC Layer for {self.interface.node.nodeName} - Interface {self.interface.interface_index}"


class NetworkLayer(models.Model):
    NETWORK_PROTOCOLS = [
        ('IPv4', 'IPv4'),
        # 其他网络协议
    ]

    interface = models.OneToOneField(Interface, on_delete=models.CASCADE, related_name='network_layer')
    networkProtocol = models.CharField(max_length=50, choices=NETWORK_PROTOCOLS)
    ipv4Address = models.GenericIPAddressField()
    ipv4SubnetMask = models.GenericIPAddressField()
    ipFragmentationUnit = models.IntegerField(default=2048)

    def __str__(self):
        return f"Network Layer for {self.interface.node.nodeName} - Interface {self.interface.interface_index}"


class RoutingProtocol(models.Model):
    ROUTING_PROTOCOLS = [
        ('Bellman Ford', 'Bellman Ford'),
        # 其他路由协议
    ]

    interface = models.OneToOneField(Interface, on_delete=models.CASCADE, related_name='routing_protocol')
    routingProtocol = models.CharField(max_length=50, choices=ROUTING_PROTOCOLS)
    enableMulticast = models.BooleanField(default=False)
    enableHSRP = models.BooleanField(default=False)

    def __str__(self):
        return f"Routing Protocol for {self.interface.node.nodeName} - Interface {self.interface.interface_index}"



