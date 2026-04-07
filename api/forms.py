from django import forms
from .models import *
from django.core.exceptions import ValidationError
class SceneForm(forms.ModelForm):
    class Meta:
        model = Scene
        fields = ['sceneName', 'startTime', 'endTime','simulationStep']

    def clean(self):
        # 调用父类的 clean 方法，确保其他字段的验证逻辑正常执行
        cleaned_data = super().clean()

        # 获取 startTime 和 endTime
        start_time = cleaned_data.get('startTime')
        end_time = cleaned_data.get('endTime')
        simulationStep = cleaned_data.get('simulationStep')

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
        fields = ['sceneId' , 'nodeId',  'errorEndTime','errorStartTime']



class LinkErrorForm(forms.ModelForm):
    class Meta:
        model = LinkError
        fields = ['sceneId','linkId','errorStartTime', 'errorEndTime']

# class NodeTemplateForm(forms.ModelForm):
#     class Meta:
#         model = NodeTemplate
#         fields = '__all__'