from django.db import models
from django.forms.models import model_to_dict
from django.utils import timezone

import datetime


# Model used for the actual Submission of the form
# Needs to include the locer name, Submission timestamp,
# the data that is on the form and then it is needed to be returned readable
class Submission(models.Model):
    locker = models.ForeignKey(Locker,
        related_name="locker_submission",
        on_delete=models.PROTECT,
        )
    timestamp = models.DateTimeField(auto_now=False,
        auto_now_add=True,
        )
    data = models.CharField(max_length=250,
        blank=True,
        )


    def data_dict(self):
        return self.to_dict()


    def to_dict(self):
        return model_to_dict(self)


# Model to show the owner/user_id of an added locker
class LockerUser(models.Model):
    locker = models.ForeignKey(Locker,
        related_name="locker_user",
        on_delete=models.PROTECT,
        )
    user_id = models.ForeignKey(Locker,
        related_name="user",
        on_delete=models.PROTECT,
        )
