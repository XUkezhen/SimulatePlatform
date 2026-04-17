from django.db import migrations, models


BUSINESS_TYPE_RENAME_MAP = {
    '泊松分布': 'POISSON',
    '广播业务': 'BROADCAST',
    '组播业务': 'MULTICAST',
}

BUSINESS_TYPE_REVERSE_MAP = {value: key for key, value in BUSINESS_TYPE_RENAME_MAP.items()}


def rename_business_types_forward(apps, schema_editor):
    Configuration = apps.get_model('api', 'Configuration')
    for old_value, new_value in BUSINESS_TYPE_RENAME_MAP.items():
        Configuration.objects.filter(businessType=old_value).update(businessType=new_value)


def rename_business_types_backward(apps, schema_editor):
    Configuration = apps.get_model('api', 'Configuration')
    for new_value, old_value in BUSINESS_TYPE_REVERSE_MAP.items():
        Configuration.objects.filter(businessType=new_value).update(businessType=old_value)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0019_scene_llcenabled_scene_arpenabled'),
    ]

    operations = [
        migrations.AlterField(
            model_name='configuration',
            name='businessType',
            field=models.CharField(
                choices=[
                    ('CBR', 'CBR'),
                    ('FTP', 'FTP'),
                    ('TRAFFIC-GEN', 'TRAFFIC-GEN'),
                    ('HTTP', 'HTTP'),
                    ('POISSON', 'POISSON'),
                    ('BROADCAST', 'BROADCAST'),
                    ('MULTICAST', 'MULTICAST'),
                ],
                default='CBR',
                max_length=20,
            ),
        ),
        migrations.RunPython(rename_business_types_forward, rename_business_types_backward),
    ]
