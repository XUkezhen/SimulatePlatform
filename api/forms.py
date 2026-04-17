from django import forms
from .models import *
from django.core.exceptions import ValidationError
class SceneForm(forms.ModelForm):
    class Meta:
        model = Scene
        fields = ['sceneName', 'startTime', 'endTime','simulationStep', 'channelCount', 'channelConfigs', 'llcEnabled', 'arpEnabled']

    def clean(self):
        # 调用父类的 clean 方法，确保其他字段的验证逻辑正常执行
        cleaned_data = super().clean()

        # 获取 startTime 和 endTime
        start_time = cleaned_data.get('startTime')
        end_time = cleaned_data.get('endTime')
        simulationStep = cleaned_data.get('simulationStep')
        channelCount = cleaned_data.get('channelCount')
        channelConfigs = cleaned_data.get('channelConfigs')

        # 验证 startTime 是否早于 endTime
        if start_time and end_time and start_time >= end_time:
            # 如果 startTime 不早于 endTime，抛出 ValidationError
            raise ValidationError({
                'startTime': '开始时间必须早于结束时间',
                'endTime': '结束时间必须晚于开始时间'
            })
            # 验证仿真步长是否为正整数
        if simulationStep is not None and simulationStep <= 0:
            raise ValidationError({
                'simulation_step': '仿真步长必须为正整数'
            })

        # 验证信道配置
        if channelCount is not None and channelCount < 0:
            raise ValidationError({
                'channelCount': '信道数量不能为负数'
            })

        if channelConfigs:
            if not isinstance(channelConfigs, list):
                raise ValidationError({
                    'channelConfigs': '信道配置必须是数组格式'
                })
            if channelCount is not None and len(channelConfigs) != channelCount:
                raise ValidationError({
                    'channelConfigs': '信道配置数量与 channelCount 不一致'
                })

        # 返回清理后的数据
        return cleaned_data

    def clean_sceneName(self):
        # 获取提交的场景名称
        scene_name = self.cleaned_data.get('sceneName')

        # 检查数据库中是否已存在相同的场景名称
        if Scene.objects.filter(sceneName=scene_name).exists():
            raise ValidationError('该场景名称已存在，请使用其他名称')

        return scene_name





class ErrorForm(forms.ModelForm):
    class Meta:
        model = Error
        fields = ['sceneId', 'nodeId', 'interfaceId', 'errorEndTime', 'errorStartTime']

    def clean(self):
        cleaned_data = super().clean()
        node_id = cleaned_data.get('nodeId')
        interface_id = cleaned_data.get('interfaceId')

        # 验证：如果指定了接口，接口必须属于该节点
        if interface_id and node_id:
            if interface_id.node_id != node_id.id:
                raise ValidationError({
                    'interfaceId': '指定的接口不属于该节点'
                })

        return cleaned_data



class LinkErrorForm(forms.ModelForm):
    class Meta:
        model = LinkError
        fields = ['sceneId','linkId','errorStartTime', 'errorEndTime']

# class NodeTemplateForm(forms.ModelForm):
#     class Meta:
#         model = NodeTemplate
#         fields = '__all__'
