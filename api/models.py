import ipaddress

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError



# 3.7号下午   本版本修改了node模型，接口模型未设置，链路模型没改。。
# 3.9晚上9点，新建了接口模型，链路模型一并修改。
#3.11 下午 views 添加get 函数
#3.13 凌晨 修改完映射表
#3.15xiu该链路表
#4.30 完成.app的调试。未完成。postman出错yin
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
    channelCount = models.IntegerField(default=0, verbose_name="信道数量")
    channelConfigs = models.JSONField(null=True, blank=True, default=list, verbose_name="信道配置列表")
    COORDINATE_CHOICES = [
        ('CARTESIAN', 'Cartesian'),#大写是写入数据库的，小写是展示用的
        ('LATLONALT', 'LatLonAlt'),
    ]
    coordinateSystem = models.CharField(
        max_length=20,
        choices=COORDINATE_CHOICES,
        default='LATLONALT',
    )
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
    #外键，第一个参数是指向哪个模型（和谁关联），on_delete是指删除，级联、受保护等等。字符类
    sceneId = models.ForeignKey('Scene', on_delete=models.CASCADE, related_name='nodes', null=True, blank=True)
    nodeName = models.CharField(max_length=255)
    nodeImage = models.CharField(max_length=255)
    nodeType = models.CharField(max_length=50, choices=NODE_TYPES)

    # normalNode 特有字段
    lon = models.FloatField(null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    alt = models.FloatField(null=True, blank=True)
    startTime = models.DateTimeField(null=True, blank=True)
    # 新增字段
    specialType = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        default=None,
        verbose_name="特殊节点类型"
    )
    epochTime = models.DateTimeField(null=True, blank=True, verbose_name="历元时间")
    orbitStepSize = models.FloatField(null=True, blank=True, verbose_name="轨道计算步长")
    orbitStepCount = models.IntegerField(null=True, blank=True, verbose_name="轨道计算步数")
    orbitInclination = models.FloatField(null=True, blank=True, verbose_name="轨道倾角")
    orbitArgPerigee = models.FloatField(null=True, blank=True, verbose_name="近地点幅角")
    orbitRaan = models.FloatField(null=True, blank=True, verbose_name="升交点赤经")
    orbitMeanAnomaly = models.FloatField(null=True, blank=True, verbose_name="平近点角")
    orbitAltitude = models.FloatField(null=True, blank=True, verbose_name="轨道高度")
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
            required_fields = [
                self.eccentricity, self.argPerigee, self.inclination,
                self.meanAnomaly, self.meanMotion, self.raan, self.startTime
            ]
            if any(field is None for field in required_fields):
                raise ValidationError("Satellite nodes require all orbital elements and startTime.")

        elif self.nodeType == 'normalNode':
            is_leo = self.specialType in {'LEO', '近地卫星'}
            if is_leo:
                required_fields = [
                    self.startTime,
                    self.epochTime,
                    self.orbitStepSize,
                    self.orbitStepCount,
                    self.orbitInclination,
                    self.orbitArgPerigee,
                    self.orbitRaan,
                    self.orbitMeanAnomaly,
                    self.orbitAltitude,
                ]
                if any(field is None for field in required_fields):
                    raise ValidationError("LEO normal nodes require startTime, epochTime, step size/count and orbit parameters.")
            else:
                required_fields = [self.lon, self.lat, self.alt, self.startTime]
                if any(field is None for field in required_fields):
                    raise ValidationError("Normal nodes require lon, lat, alt, and startTime.")

            if self.viaPoints:
                try:
                    if not isinstance(self.viaPoints, list):
                        raise ValidationError("viaPoints must be a JSON list of points.")
                    for point in self.viaPoints:
                        if not isinstance(point, dict):
                            raise ValidationError("Each viaPoint must be a dictionary.")
                        if any(k not in point for k in ['lon', 'lat', 'alt', 'time']):
                            raise ValidationError("Each viaPoint must contain 'lon', 'lat', 'alt', and 'time'.")
                except (TypeError, ValueError):
                    raise ValidationError("viaPoints must be valid JSON.")


class Configuration(models.Model):
    BUSINESS_TYPE_CHOICES = (
        ('CBR', 'CBR'),
        ('FTP', 'FTP'),
        ('TRAFFIC-GEN', 'TRAFFIC-GEN'),
        ('HTTP', 'HTTP'),
    )

    sceneId = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name='configurations', default=12)
    businessType = models.CharField(max_length=20, choices=BUSINESS_TYPE_CHOICES, default='CBR')
    businessName = models.CharField(max_length=255)

    # 通用的源/目的节点，仅适用于非 HTTP 类型
    sourceNodeId = models.ForeignKey(
        Node,
        on_delete=models.CASCADE,
        related_name='source_configurations',
        null=True, blank=True
    )
    destinationNodeId = models.ForeignKey(
        Node,
        on_delete=models.CASCADE,
        related_name='destination_configurations',
        null=True, blank=True
    )

    # ========== CBR 配置 ==========
    cbrStartTime = models.DateTimeField(null=True, blank=True, verbose_name='CBR开始时间')
    cbrEndTime = models.DateTimeField(null=True, blank=True, verbose_name='CBR结束时间')
    cbrSendInterval = models.IntegerField(null=True, blank=True, verbose_name='CBR发送间隔（ms）')
    cbrPacketSize = models.IntegerField(null=True, blank=True, verbose_name='CBR包大小（Bytes）')
    cbrPrecedence = models.IntegerField(null=True, blank=True, verbose_name='CBR优先级')
    TransferType = models.CharField(null = True,blank= True,default= 'ID',max_length= 2)
    # ========== FTP 配置 ==========
    ftpStartTime = models.DateTimeField(null=True, blank=True, verbose_name='FTP开始时间')
    ftpPacketCount = models.IntegerField(null=True, blank=True, verbose_name='FTP包数量')

    # ========== TRAFFIC-GEN 配置 ==========
    tgStartTime = models.FloatField(null=True, blank=True, verbose_name='Traffic-Gen开始时间（s）')
    tgDurationTime = models.FloatField(null=True, blank=True, verbose_name='Traffic-Gen持续时间（s）')
    tgPacketSize = models.IntegerField(null=True, blank=True, verbose_name='Traffic-Gen包大小（Bytes）')
    tgSendInterval = models.FloatField(null=True, blank=True, verbose_name='Traffic-Gen发送间隔（s）')

    # ========== HTTP 配置 ==========
    clientId = models.ForeignKey(
        Node,
        on_delete=models.CASCADE,
        related_name='http_clients',
        null=True, blank=True,
        verbose_name='HTTP客户端节点'
    )
    serverList = models.JSONField(
        null=True, blank=True,
        verbose_name='HTTP服务器节点列表（节点ID列表）'
    )
    httpStartTime = models.FloatField(null=True, blank=True, verbose_name='HTTP开始时间（s）')
    httpThreshTime = models.FloatField(null=True, blank=True, verbose_name='HTTP阈值时间（s）')

    def __str__(self):
        return f'{self.businessType} - {self.businessName}'



class Subnet(models.Model):
    class SubnetTypeChoices(models.TextChoices):
        SUB = 'sub', '子网（sub）'
        LINK = 'link', '链路（link）'

    sceneId = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name='subnets', default=12)
    subnetName = models.CharField(max_length=255)
    subnetIp = models.GenericIPAddressField()
    subnetMask = models.GenericIPAddressField()
    details = models.JSONField(null= True,blank= True)
    subnetType = models.CharField(
        max_length=10,
        choices=SubnetTypeChoices.choices,
        default=SubnetTypeChoices.SUB,
        verbose_name="子网类型"
    )

    def __str__(self):
        return self.subnetName

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

    @property
    def links(self): #通过接口，直接查到它关联的链路
        result = []
        if hasattr(self, "source_link"):
            result.append(self.source_link)
        if hasattr(self, "destination_link"):
            result.append(self.destination_link)
        return result

    detail = models.JSONField(
        default=dict,
        verbose_name="Interface Detail",
        null=True,
        blank=True
    )

    class Meta:
        unique_together = ('node', 'interfaceIndex')
        ordering = ['node', 'interfaceIndex']
        verbose_name = "Network Interface"
        verbose_name_plural = "Network Interfaces"

    def __str__(self):
        return f"{self.node.nodeName} - Interface {self.interfaceIndex} ({self.interfaceIp}/{self.subnetMask})"

    def clean(self):
        if self.interfaceIndex is not None and (self.interfaceIndex < 0 ):
            # 不局限于4个
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
    bandwidth = models.FloatField(verbose_name='带宽(Mbps)', null=True, blank=True)
    packetHeaderSize = models.IntegerField(verbose_name='包头大小(Byte)', null=True, blank=True)
    transmissionDelay = models.FloatField(verbose_name='传输延迟(ms)', null=True, blank=True)
    packetLossRate = models.FloatField(verbose_name='丢包率(%)', null=True, blank=True)
    transmissionSpeed = models.FloatField(verbose_name='传输速度(Mb/s)', null=True, blank=True)
    subnetIp = models.GenericIPAddressField()
    subnetMask = models.CharField(max_length=50)
    sourceInterface = models.OneToOneField(Interface, on_delete=models.CASCADE, related_name='source_link', null=True, blank=True)
    destinationInterface = models.OneToOneField(Interface, on_delete=models.CASCADE, related_name='destination_link', null=True, blank=True)
    subnet = models.ForeignKey(Subnet, on_delete=models.CASCADE, related_name='links', null=True, blank=True)  # 关联子网
    # 新增字段
    linkConfig = models.BooleanField(default=True, null=True, blank=True,verbose_name='链路是否启用配置')##判断是否需要从接口单独配置参数。
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

class SlotTable(models.Model):
    scene = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name="slot_tables")
    data = models.JSONField()

    def __str__(self):
        return f"SlotTable {self.id} for Scene {self.scene.name}"

class Error(models.Model):
    sceneId = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name='nodeerrors', default=12)
    nodeId = models.ForeignKey(Node, on_delete=models.CASCADE, related_name='errors')
    errorStartTime = models.DateTimeField(null=True, blank=True, default=timezone.now)
    errorEndTime = models.DateTimeField(null=True, blank=True, default=timezone.now)
    interfaceId = models.ForeignKey(
        'Interface',
        on_delete=models.CASCADE,
        related_name='errors',
        null=True,
        blank=True,
        verbose_name="接口ID"
    )

class LinkError(models.Model):
    sceneId = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name='linkerrors', default=12)
    linkId = models.ForeignKey(Link, on_delete=models.CASCADE, related_name='errors')
    errorStartTime = models.DateTimeField(null=True, blank=True, default='2025-01-16T01:00:00+00:00')
    errorEndTime = models.DateTimeField(null=True, blank=True, default='2025-01-16T01:00:00+00:00')


class NodeTemplate(models.Model):
    templateInfo = models.TextField()  # 节点信息
    templateName = models.CharField(max_length=255, unique=True)  # 节点名称
    templateType = models.CharField(max_length=50)  # 节点类型

class NodeMapping(models.Model):
    sceneId = models.ForeignKey('Scene', on_delete=models.CASCADE, related_name='mappings')
    interface = models.ForeignKey(Interface, on_delete=models.CASCADE, related_name='mappings')
    mappingIp = models.GenericIPAddressField()

