from django.db import models


# Create your models here.
class Announcement(models.Model):
    title = models.CharField(max_length=50)
    content = models.TextField()
    url = models.CharField(max_length=150)
    creation_date = models.DateTimeField(auto_now_add=True)
    publish_start_date = models.DateTimeField()
    publish_end_date = models.DateTimeField()
