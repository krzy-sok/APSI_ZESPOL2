from django.contrib import admin

from .models import (
    Category,
    Device,
    DeviceLease,
    DeviceLocation,
    DeviceRepair,
    Employee,
    ParameterModel,
)

# Register your models here.
admin.site.register(Category)
admin.site.register(Employee)
admin.site.register(Device)

admin.site.register(DeviceLease)
admin.site.register(DeviceRepair)
admin.site.register(ParameterModel)

admin.site.register(DeviceLocation)
