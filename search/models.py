from django.db import models

INDEX_CHOICE_TYPES = [
    ('policy', 'policy'),
    ('question', 'question'),
]


class Index(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['key', 'type']),
        ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    type = models.CharField(max_length=100, choices=INDEX_CHOICE_TYPES)
    key = models.CharField(max_length=75, default='')

    def __str__(self):
        return f'{self.type} - {self.key}'
