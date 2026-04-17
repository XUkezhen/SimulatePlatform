from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0018_configuration_broadcastapptype_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='scene',
            name='arpEnabled',
            field=models.CharField(choices=[('YES', 'YES'), ('NO', 'NO')], default='YES', max_length=3, verbose_name='是否启用地址解析协议'),
        ),
        migrations.AddField(
            model_name='scene',
            name='llcEnabled',
            field=models.CharField(choices=[('YES', 'YES'), ('NO', 'NO')], default='YES', max_length=3, verbose_name='是否启用逻辑链路控制'),
        ),
    ]
