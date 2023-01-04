import uuid

from django.contrib.postgres.indexes import HashIndex
from django.db import models
from django.utils import timezone

from alert.constants import ALERT_TYPES
from comment.models import Comment
from laika.constants import CATEGORIES
from laika.storage import PrivateMediaStorage
from laika.utils.strings import random_string
from library.search import searchable_library_model
from organization.models import Organization
from policy.constants import ONBOARDING_POLICIES, POLICY_ATTRIBUTES
from policy.utils import launchpad
from search.search import launchpad_model
from tag.models import Tag
from user.models import User

CONTROL_PILLAR_MODEL = 'control.ControlPillar'


def published_policy_file_directory_path(instance, filename):
    return (
        f'{instance.policy.organization.id}/policies/'
        + f'{instance.policy.name}/versions/{instance.version}'
    )


def policy_file_directory_path(instance, filename):
    return f'{instance.organization.id}/policies/{instance.name}/{filename}'


def policy_embedding_file_directory_path(instance, filename):
    return (
        f'{instance.policy.organization.id}/policies/'
        + f'{instance.policy.name}/{filename}'
    )


def filter_policies(user, model):
    organization = user.organization
    filter = {'organization': organization, 'is_published': True}

    return model.objects.filter(**filter)


class PolicyTypes(models.TextChoices):
    POLICY = 'Policy', 'Policy'
    PROCEDURE = 'Procedure', 'Procedure'


@searchable_library_model(type='policy', qs=filter_policies, fields=['policy_text'])
@launchpad_model(context='policy', mapper=launchpad.launchpad_mapper)
class Policy(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    display_id = models.IntegerField(default=1)
    name = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='policies'
    )
    administrator = models.ForeignKey(
        User,
        related_name='policy_managed',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    owner = models.ForeignKey(
        User,
        related_name='policy_owned',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    approver = models.ForeignKey(
        User,
        related_name='policy_approver',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    category = models.CharField(
        max_length=100, choices=CATEGORIES, default='', blank=True
    )
    draft = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=policy_file_directory_path,
        blank=True,
        max_length=1024,
    )
    draft_key = models.CharField(max_length=20)
    tags = models.ManyToManyField(Tag, related_name='policies', through='PolicyTag')
    comments = models.ManyToManyField(
        Comment, related_name='policies', through='PolicyComment'
    )
    #   This is for policies search purpose
    policy_text = models.TextField(blank=True, null=True)
    is_visible_in_dataroom = models.BooleanField(default=True)
    is_required = models.BooleanField(default=False)
    action_items = models.ManyToManyField(
        'action_item.ActionItem', related_name='policies', blank=True
    )
    control_family = models.ForeignKey(
        CONTROL_PILLAR_MODEL,
        related_name='policy',
        on_delete=models.SET_NULL,
        null=True,
        default=None,
    )
    policy_type = models.CharField(
        max_length=255, choices=PolicyTypes.choices, default=PolicyTypes.POLICY
    )
    is_draft_edited = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'policies'
        indexes = [
            models.Index(fields=['draft_key']),
            HashIndex(fields=['policy_text']),
        ]

    def __str__(self):
        return self.name

    def _increment_display_id(self):
        # Get the maximum display_id value from the database
        last_id = Policy.objects.filter(organization=self.organization).aggregate(
            largest=models.Max('display_id')
        )['largest']

        if last_id is not None:
            self.display_id = last_id + 1

    def _generate_draft_key(self):
        self.draft_key = random_string()

    @classmethod
    def get_attribute_type_by_name(cls, name):
        return POLICY_ATTRIBUTES[name]

    def save(self, *args, **kwargs):
        generate_key = kwargs.get('generate_key')
        if generate_key:
            del kwargs['generate_key']
            self._generate_draft_key()

        if self._state.adding:
            self._generate_draft_key()
            self._increment_display_id()

        super(Policy, self).save(*args, **kwargs)


class PolicyCommentManager(models.Manager):
    def custom_create(
        self, organization, owner, content, policy_id, tagged_users, action_id
    ):
        comment = Comment.objects.create(
            owner=owner, content=content, action_id=action_id
        )

        policy = Policy.objects.get(organization=organization, id=policy_id)

        policy_comment = super().create(policy=policy, comment=comment)

        mentions = comment.add_mentions(tagged_users)
        if mentions:
            for mention in mentions:
                room_id = mention.user.organization.id
                alert = mention.create_mention_alert(
                    room_id, ALERT_TYPES['POLICY_MENTION']
                )
                if alert:
                    policy_message_data = mention.get_mention_policy_message_data()
                    alert.send_comment_policy_alert_email(
                        policy_message_data=policy_message_data
                    )
        return policy_comment.comment


class PolicyComment(models.Model):
    policy = models.ForeignKey(
        Policy, on_delete=models.CASCADE, related_name='policy_comments'
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name='policy_comments'
    )

    objects = PolicyCommentManager()


class PolicyProxy(Policy):
    class Meta:
        proxy = True
        verbose_name = 'Deleted Policy'
        verbose_name_plural = 'Deleted Policies'


class PublishedPolicy(models.Model):
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    published_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='published_policies', null=True
    )
    owned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='published_owned_policies',
        null=True,
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='published_approved_policies',
        null=True,
    )
    policy = models.ForeignKey(
        Policy, on_delete=models.CASCADE, related_name='versions'
    )
    contents = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=published_policy_file_directory_path,
        max_length=1024,
    )
    embedding = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=policy_embedding_file_directory_path,
        blank=True,
    )
    comment = models.TextField(blank=True)
    published_key = models.CharField(max_length=20)

    class Meta:
        verbose_name = 'published policy'
        verbose_name_plural = 'published policies'
        unique_together = (
            'version',
            'policy',
        )

    def _increment_version(self):
        last_version = PublishedPolicy.objects.filter(policy=self.policy).aggregate(
            largest=models.Max('version')
        )['largest']

        if last_version is not None:
            self.version = last_version + 1

    def _generate_published_key(self):
        self.published_key = random_string()

    def save(self, *args, **kwargs):
        self._generate_published_key()
        if self._state.adding:
            self._increment_version()

        super(PublishedPolicy, self).save(*args, **kwargs)

    def __str__(self):
        return f'Version: {self.version}'


class PolicyTag(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    policy = models.ForeignKey(
        Policy, on_delete=models.CASCADE, related_name='policy_tags'
    )

    def __str__(self):
        return str(self.tag)


class OnboardingPolicy(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='onboarding_policies'
    )
    description = models.CharField(max_length=512, choices=ONBOARDING_POLICIES)
    use_laika_template = models.BooleanField(default=True)
    file = models.ForeignKey(
        'evidence.Evidence',
        on_delete=models.SET_NULL,
        related_name='onboarding_policy',
        null=True,
    )
