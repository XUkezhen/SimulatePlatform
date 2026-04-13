from rest_framework import serializers
from .models import Configuration

class ConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Configuration
        fields = '__all__'

    def validate(self, data):
        business_type = data.get('businessType')
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

        else:
            raise serializers.ValidationError(f"不支持的业务类型: {business_type}")

        # 检查时间合理性（如果有结束时间）
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError("开始时间必须早于结束时间。")

        # 检查必填字段是否存在
        missing_fields = [field for field in required_fields if data.get(field) in [None, '']]
        if missing_fields:
            raise serializers.ValidationError(
                f"业务类型为 {business_type} 时，缺少字段: {', '.join(missing_fields)}")

        return data
