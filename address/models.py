from django.db import models


class Address(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    street1 = models.CharField(max_length=255, blank=True)
    street2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=255, blank=True)
    zip_code = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return (
            f'{self.street1} - '
            + f'({self.city}, {self.state}, {self.country}, {self.zip_code})'
        )
