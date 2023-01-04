import django.utils.timezone as timezone
from django.db import models
from django.db.models import Q

from alert.models import Alert
from dataroom.models import Dataroom
from laika.storage import PrivateMediaStorage
from laika.utils.soft_delete import SoftDeleteManager, SoftDeleteModel
from library.constants import (
    CATEGORIES,
    FETCH_STATUS,
    NOT_RAN,
    RESULT_FOUND,
    RESULT_FOUND_UPDATED,
    TASK_DEFAULT_STATUS,
    TASK_STATUS,
)
from library.search import searchable_library_model
from organization.models import Organization
from user.models import User


def filter_library_entries(user, model):
    filter = Q(
        Q(organization=user.organization)
        & Q(question__deleted_at__isnull=True)
        & Q(
            Q(question__questionnaires__isnull=True)
            | Q(question__questionnaires__completed=True)
        )
    )
    return model.objects.filter(filter)


def filter_questions(user, model):
    filter = Q(
        Q(library_entry__organization=user.organization)
        & Q(deleted_at__isnull=True)
        & Q(Q(questionnaires__isnull=True) | Q(questionnaires__completed=True))
    )
    return model.objects.filter(filter)


def question_embedding_file_directory_path(instance, filename):
    return (
        f'{instance.library_entry.organization.id}/questions/'
        + f'{instance.id}/{filename}'
    )


@searchable_library_model(
    type='library_entry', qs=filter_library_entries, fields=['answer_text']
)
class LibraryEntry(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='library_entries',
        null=True,
    )
    category = models.CharField(max_length=200, choices=CATEGORIES, default='')
    display_id = models.IntegerField(default=1)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='user_library_entry',
        null=True,
        blank=True,
    )

    answer_text = models.TextField(default='', blank=True)
    short_answer_text = models.TextField(default='', blank=True)

    class Meta:
        verbose_name_plural = 'library entries'
        permissions = [
            ('bulk_upload_library', 'Can bulk upload library'),
        ]

    def _increment_display_id(self):
        # Get the maximum display_id value from the database
        last_id = LibraryEntry.objects.filter(organization=self.organization).aggregate(
            largest=models.Max('display_id')
        )['largest']

        if last_id is not None:
            self.display_id = last_id + 1

    def save(self, *args, **kwargs):
        if self._state.adding:
            self._increment_display_id()

        super(LibraryEntry, self).save(*args, **kwargs)

    def __str__(self):
        return f'{self.display_id}'


@searchable_library_model(type='question', qs=filter_questions, fields=['text'])
class Question(SoftDeleteModel):
    objects = SoftDeleteManager()
    all_objects = SoftDeleteManager(alive_only=False)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    text = models.TextField()
    default = models.BooleanField()
    library_entry = models.OneToOneField(
        LibraryEntry,
        related_name='question',
        on_delete=models.CASCADE,
    )
    completed = models.BooleanField(default=False)
    fetch_status = models.CharField(
        max_length=21, choices=FETCH_STATUS, default=NOT_RAN
    )
    metadata = models.JSONField(blank=True, default=dict)
    user_assigned = models.ForeignKey(
        User,
        related_name='library_questions',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    equivalent_questions = models.ManyToManyField(
        'Question', related_name='questions', blank=True
    )
    equivalent_suggestions = models.ManyToManyField(
        'Question', related_name='suggestions', blank=True
    )
    completed = models.BooleanField(default=False)
    embedding = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=question_embedding_file_directory_path,
        blank=True,
    )

    @property
    def default_question(self):
        if self.default:
            return self
        else:
            return Question.objects.get(default=True, equivalent_questions__id=self.id)

    class Meta:
        verbose_name_plural = 'questions'
        indexes = [
            models.Index(fields=['text']),
        ]

    def __str__(self):
        return self.text

    def reconcile_equivalent_questions(self):
        if not (self.default):
            self.default_question.equivalent_questions.remove(self)
            self.default = True
            if self.fetch_status == RESULT_FOUND:
                self.fetch_status = RESULT_FOUND_UPDATED
            self.save()
        else:
            equivalent_questions = self.equivalent_questions
            original_equivalent_questions_count = equivalent_questions.count()

            if original_equivalent_questions_count == 0:
                return
            equivalent_questions_in_progress_questionnaire_count = (
                equivalent_questions.filter(questionnaires__completed=False).count()
            )
            if (
                original_equivalent_questions_count
                == equivalent_questions_in_progress_questionnaire_count
            ):
                equivalent_questions.update(default=True)
            else:
                new_default_question = (
                    equivalent_questions.filter(
                        Q(
                            Q(questionnaires__isnull=True)
                            | Q(questionnaires__completed=True)
                        )
                    )
                    .order_by('-library_entry__updated_at')
                    .first()
                )

                new_equivalent_questions = equivalent_questions.exclude(
                    id=new_default_question.id
                )
                new_default_question.default = True
                new_default_question.equivalent_questions.set(new_equivalent_questions)
                new_default_question.save()
            self.equivalent_questions.clear()


class Questionnaire(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'organization'],
                name='unique_name_questionnaire_organization',
            )
        ]

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    name = models.CharField(max_length=255, blank=False)
    completed = models.BooleanField(default=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='questionnaires'
    )
    dataroom = models.ForeignKey(
        Dataroom,
        on_delete=models.SET_NULL,
        related_name='questionnaires',
        null=True,
        blank=True,
    )
    questions = models.ManyToManyField(
        Question, related_name='questionnaires', blank=True
    )

    def __str__(self):
        return self.name


class LibraryTask(models.Model):
    created_by = models.ForeignKey(
        User,
        related_name='library_task',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20, choices=TASK_STATUS, default=TASK_DEFAULT_STATUS
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)


class QuestionnaireAlertManager(models.Manager):
    def custom_create(self, questionnaire, sender, receiver, alert_type):
        alert = Alert.objects.custom_create(
            sender=sender, receiver=receiver, alert_type=alert_type
        )
        questionnaire_alert = super().create(alert=alert, questionnaire=questionnaire)
        return questionnaire_alert


class QuestionnaireAlert(models.Model):
    alert = models.ForeignKey(
        Alert, related_name='questionnaire_alert', on_delete=models.CASCADE
    )
    questionnaire = models.ForeignKey(
        Questionnaire,
        related_name='alerts',
        on_delete=models.CASCADE,
    )
    objects = QuestionnaireAlertManager()


class LibraryEntrySuggestionsAlertManager(models.Manager):
    def custom_create(
        self,
        quantity: int,
        organization: Organization,
        sender: User,
        receiver: User,
        alert_type: str,
    ):
        alert = Alert.objects.custom_create(
            sender=sender, receiver=receiver, alert_type=alert_type
        )
        library_entry_suggestions_alert = super().create(
            alert=alert, quantity=quantity, organization=organization
        )
        return library_entry_suggestions_alert


class LibraryEntrySuggestionsAlert(models.Model):
    alert = models.ForeignKey(
        Alert, related_name='library_entry_suggestions_alert', on_delete=models.CASCADE
    )
    organization = models.ForeignKey(
        Organization,
        related_name='library_entry_suggestions_organization',
        on_delete=models.CASCADE,
    )
    quantity = models.IntegerField()
    objects = LibraryEntrySuggestionsAlertManager()
