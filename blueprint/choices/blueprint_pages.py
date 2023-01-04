from django.db import models


class BlueprintPage(models.TextChoices):
    GLOBAL = 'Global'
    CONTROLS = ('Controls',)
    CERTIFICATION = ('Certification',)
    CERTIFICATION_SECTIONS = ('Certification Sections',)
    CHECKLIST = ('Checklist',)
    CONTROL_FAMILY = ('Control Family',)
    ACTION_ITEMS = ('Action Items',)
    GROUPS = ('Groups',)
    TAGS = ('Tags',)
    TEAMS = ('Teams (Charters)',)
    TRAINING = ('Files',)
    OBJECT = ('Object Types',)
    OBJECT_ATTRIBUTES = ('Object Type Attributes',)
    OFFICERS = ('Officers',)
    QUESTIONS = ('Questions',)
    GUIDES = 'Implementation Guides'
    EVIDENCES_METADATA = ('Evidences Metadata',)
