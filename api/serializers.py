from rest_framework import serializers
from .models import Configuration, normalize_business_type


def _parse_duration_seconds(value):
    if value in [None, '']:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().upper()
    if text.endswith('MS'):
        return float(text[:-2]) / 1000
    if text.endswith('S'):
        return float(text[:-1])
    return float(text)


class ConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Configuration
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['businessType'] = normalize_business_type(data.get('businessType'))
        return data

    def validate(self, data):
        business_type = normalize_business_type(data.get('businessType'))
        data['businessType'] = business_type
        business_name = data.get('businessName')

        # 防止业务名称重复（注意更新时排除自身）
        if self.instance:
            if Configuration.objects.filter(businessName=business_name).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("业务名称已存在，请使用不同的业务名称。")
        else:
            if Configuration.objects.filter(businessName=business_name).exists():
                raise serializers.ValidationError("业务名称已存在，请使用不同的业务名称。")

        # 针对不同类型业务字段校验
        if business_type == 'CBR':
            required_fields = ['cbrStartTime', 'cbrEndTime', 'cbrSendInterval', 'cbrPacketSize']
            start_time = data.get('cbrStartTime')
            end_time = data.get('cbrEndTime')
            precedence = data.get('cbrPrecedence')
            if precedence not in [None, '']:
                try:
                    precedence_value = int(precedence)
                except (TypeError, ValueError):
                    raise serializers.ValidationError("CBR 的 PRECEDENCE 必须是整数。")
                if precedence_value < 0:
                    raise serializers.ValidationError("CBR 的 PRECEDENCE 不能小于 0。")

        elif business_type == 'FTP':
            required_fields = ['ftpStartTime', 'ftpPacketCount']
            start_time = data.get('ftpStartTime')
            end_time = None

        elif business_type == 'TRAFFIC-GEN':
            required_fields = ['tgStartTime', 'tgDurationTime', 'tgPacketSize', 'tgSendInterval']
            start_time = data.get('tgStartTime')
            end_time = None  # TRAFFIC-GEN 使用持续时间，无需 end_time

            # 验证 source/destination node 必填
            if not data.get('sourceNodeId') or not data.get('destinationNodeId'):
                raise serializers.ValidationError("TRAFFIC-GEN 类型需要指定 sourceNodeId 和 destinationNodeId。")

        elif business_type == 'HTTP':
            required_fields = ['clientId', 'serverList', 'httpStartTime', 'httpThreshTime']
            start_time = data.get('httpStartTime')
            end_time = None  # HTTP 无明确结束时间

            # 不允许配置 sourceNodeId / destinationNodeId
            if data.get('sourceNodeId') or data.get('destinationNodeId'):
                raise serializers.ValidationError("HTTP 类型不能设置 sourceNodeId 或 destinationNodeId。")

            # serverList 应为非空列表
            server_list = data.get('serverList')
            if not isinstance(server_list, list) or not server_list:
                raise serializers.ValidationError("HTTP 类型必须提供非空的 serverList 列表。")

        elif business_type == 'POISSON':
            required_fields = ['sourceNodeId', 'destinationNodeId', 'poissonStartTime', 'poissonEndTime', 'poissonMeanInterval', 'poissonPacketSize']
            start_time = data.get('poissonStartTime')
            end_time = data.get('poissonEndTime')

            if not data.get('sourceNodeId') or not data.get('destinationNodeId'):
                raise serializers.ValidationError("POISSON 类型需要指定 sourceNodeId 和 destinationNodeId。")

        elif business_type == 'BROADCAST':
            required_fields = [
                'sourceNodeId',
                'broadcastDest',
                'broadcastTransportType',
                'broadcastAppType',
                'broadcastLifeTime',
                'broadcastStartTime',
                'broadcastInterval',
                'broadcastFragmentSize',
                'broadcastFragmentNum',
            ]
            start_time = data.get('broadcastStartTime')
            end_time = None

            if not data.get('sourceNodeId'):
                raise serializers.ValidationError("BROADCAST 类型需要指定 sourceNodeId。")

        elif business_type == 'MULTICAST':
            required_fields = [
                'sourceNodeId',
                'multicastDestination',
                'multicastItemsToSend',
                'multicastItemSize',
                'multicastInterval',
                'multicastStartTime',
                'multicastEndTime',
            ]
            start_time = data.get('multicastStartTime')
            end_time = data.get('multicastEndTime')

            if not data.get('sourceNodeId'):
                raise serializers.ValidationError("MULTICAST 类型需要指定 sourceNodeId。")

        else:
            raise serializers.ValidationError(f"不支持的业务类型: {business_type}")

        # 检查时间合理性（如果有结束时间）
        if start_time and end_time:
            try:
                if _parse_duration_seconds(start_time) >= _parse_duration_seconds(end_time):
                    raise serializers.ValidationError("开始时间必须早于结束时间。")
            except (TypeError, ValueError):
                if start_time >= end_time:
                    raise serializers.ValidationError("开始时间必须早于结束时间。")

        # 检查必填字段是否存在
        missing_fields = [field for field in required_fields if data.get(field) in [None, '']]
        if missing_fields:
            raise serializers.ValidationError(
                f"业务类型为 {business_type} 时，缺少字段: {', '.join(missing_fields)}")

        return data
