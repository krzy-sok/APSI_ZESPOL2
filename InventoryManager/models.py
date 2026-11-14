from django.db import models

from django.db import models

class Category(models.Model):
    name = models.CharField()
    allowed_sub_components = models.ManyToManyField('self', symmetrical=False, blank=True)

    def __str__(self):
        return self.name

class Device(models.Model):
    name = models.CharField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    components = models.ManyToManyField('self', symmetrical=False, blank=True)
    def __str__(self):
            return self.name

class Employee(models.Model):
    name = models.CharField()
    hired_date = models.DateField()
    # placeholders
    department = models.CharField()
    address_info = models.CharField()
    def __str__(self):
            return self.name

class DeviceLease(models.Model):
    device =  models.ForeignKey(Device, on_delete=models.CASCADE)
    owner = models.ForeignKey(Employee, on_delete=models.CASCADE)
    lease_start = models.DateField()
    lease_end = models.DateField() 
    description = models.CharField()
    title = models.CharField()

class DeviceRepair(models.Model):
    device =  models.ForeignKey(Device, on_delete=models.CASCADE)
    repair_start = models.DateField()
    repair_end = models.DateField() 
    description = models.CharField()
    title = models.CharField()

class DeviceStatus(models.TextChoices):
        AVAILABLE = "AVAILABLE"
        LEASED = "LEASED"
        IN_REPAIR = "IN_REPAIR"
        BROKEN = "BROKEN"
        NOT_IN_COMPANY = "NOT_IN_COMPANY"

class ParameterModel(models.Model):
    name = models.CharField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    unit = models.CharField()
    value = models.CharField()
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    
    can_be_leased = models.BooleanField()
    can_be_repaired = models.BooleanField()
    status = DeviceStatus

class DeviceLocation(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)

    # assumed integration 
    location = models.CharField()

