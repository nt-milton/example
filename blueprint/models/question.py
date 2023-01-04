from django.db import models


class QuestionBlueprint(models.Model):
    class Meta:
        verbose_name_plural = 'Questions Blueprint'

    questionnaire = models.TextField(blank=False, max_length=200)
    airtable_record_id = models.CharField(blank=True, max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField()
    question_text = models.TextField(blank=False)
    answer = models.TextField(blank=False)
    short_answer = models.TextField(blank=True, default='')
    short_answer_options = models.TextField(blank=True, default='')

    def __str__(self):
        return self.question_text
