from django.forms import ModelForm

from dashboard.models import Task


class TaskForm(ModelForm):
    class Meta:
        model = Task
        fields = '__all__'
