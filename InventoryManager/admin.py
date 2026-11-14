from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(Category)
admin.site.register(Employee)
admin.site.register(Device)

admin.site.register(DeviceLease)
admin.site.register(DeviceRepair)
admin.site.register(ParameterModel)

admin.site.register(DeviceLocation)

