from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import LibraryEntry, Question, Questionnaire


class LibraryQuestionInlineAdmin(admin.TabularInline):
    model = Question


class LibraryEntryAdmin(VersionAdmin):
    model = LibraryEntry
    list_display = (
        'display_id',
        'question_text',
        'answer_text',
        'short_answer_text',
        'created_at',
        'updated_at',
    )
    ordering = ('display_id',)
    list_filter = ('organization',)
    inlines = [
        LibraryQuestionInlineAdmin,
    ]

    def question_text(self, instance):
        return instance.question.text


class QuestionnaireAdmin(VersionAdmin):
    model = Questionnaire
    list_display = ('name', 'organization', 'completed')
    list_filter = ('organization',)


admin.site.register(LibraryEntry, LibraryEntryAdmin)
admin.site.register(Questionnaire, QuestionnaireAdmin)
