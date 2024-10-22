from django.db import models


# Create your models here.
class SiteCustomConfigs(models.Model):
    bankrupt_status = models.CharField(default="Bankrupt Status", max_length=512)
    is_bankrupt = models.BooleanField(default=False)

    def __str__(self):
        return "Website Settings | Controllable from Dashboard"
