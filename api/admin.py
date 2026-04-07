from django.contrib import admin
# Register your models here.
from .models import *

admin.site.register(Scene)
admin.site.register(Subnet)
admin.site.register(Node)
admin.site.register(Link)
#注册用
