from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import List, Tuple, Union

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q

from library.ai_answer_question import ai_answer_question
from library.constants import FetchType
from library.models import Question, Questionnaire
from library.utils import (
    get_questions_annotate_for_fetch,
    validate_match_assign_answer_text,
)
from organization.models import Organization


class Fetch:
    def __init__(self, fetch_type: str) -> None:
        self.fetch_type = fetch_type
        if self.fetch_type == FetchType.EXACT.value:
            self._strategy: Strategy = FetchExactMatchStrategy()  # type:ignore
        elif self.fetch_type == FetchType.FUZZY.value:
            self._strategy: Strategy = FetchFuzzyStrategy()  # type:ignore

    @property
    def strategy(self) -> Strategy:
        return self._strategy

    @strategy.setter
    def strategy(self, strategy: Strategy) -> None:
        self._strategy = strategy

    def fetch(self, questionnaire_id: str, organization: Organization) -> Tuple:
        updated_questions, non_updated_questions = self._strategy.search_text(
            questionnaire_id, organization
        )
        return updated_questions, non_updated_questions


class Strategy(ABC):
    @abstractmethod
    def get_question_matches(
        self,
        question: Question,
        organization: Organization,
        similarity: Union[float, int],
    ):
        pass

    @abstractmethod
    def search_text(self, questionnaire_id: str, organization: Organization):
        pass


class FetchExactMatchStrategy(Strategy):
    def get_question_matches(
        self,
        question: Question,
        organization: Organization,
        similarity: Union[float, int],
    ):
        transformed_question_text = re.sub(r"[\n\t\s]*", "", question.text)
        matches = (
            get_questions_annotate_for_fetch()
            .filter(
                Q(Q(questionnaires__isnull=True) | Q(questionnaires__completed=True)),
                question_without_spaces__iexact=transformed_question_text,
                library_entry__organization=organization,
            )
            .order_by('-library_entry__updated_at')
            .exclude(Q(Q(id=question.id) | Q(library_entry__answer_text__exact='')))
        )
        return matches

    def search_text(self, questionnaire_id: str, organization: Organization) -> Tuple:
        updated_questions: List[Question] = []
        non_updated_questions: List[Question] = []
        questionnaire = Questionnaire.objects.get(
            id=questionnaire_id, organization=organization
        )
        questionnaire_questions = questionnaire.questions.filter(completed=False)
        for question in questionnaire_questions:
            exact_matches = self.get_question_matches(question, organization, 1)
            validate_match_assign_answer_text(
                exact_matches.first(),
                question,
                updated_questions,
                non_updated_questions,
            )

        return updated_questions, non_updated_questions


class FetchFuzzyStrategy(Strategy):
    def answer_from_fuzzy(self, question: Question, organization: Organization):
        fuzzy_matches = self.get_question_matches(question, organization, 0.2)
        match = fuzzy_matches.first()
        validate_match_assign_answer_text(match, question, [], [])
        return True if match else False

    def get_question_matches(
        self,
        question: Question,
        organization: Organization,
        similarity: Union[float, int],
    ):
        transformed_question_text = re.sub(r"[\n\t\s]*", "", question.text)
        matches = (
            get_questions_annotate_for_fetch()
            .annotate(
                similarity=TrigramSimilarity(
                    'question_without_spaces', transformed_question_text
                )
            )
            .filter(
                Q(Q(questionnaires__isnull=True) | Q(questionnaires__completed=True)),
                similarity__gt=similarity,
                library_entry__organization=organization,
            )
            .order_by('-similarity', 'library_entry__updated_at')
            .exclude(Q(Q(id=question.id) | Q(library_entry__answer_text__exact='')))
        )
        return matches

    def search_text(self, questionnaire_id: str, organization: Organization) -> Tuple:
        """
        When Fuzzy Spikes is made, developer must implement Fuzzy match in this
        method
        """
        fetch_context = Fetch(FetchType.EXACT.value)
        answered_questions, non_updated_questions = fetch_context.fetch(
            questionnaire_id, organization
        )
        non_answered_questions = []
        for question in non_updated_questions:
            answered = self.answer_from_fuzzy(
                question, organization
            ) or ai_answer_question(question, organization)
            if answered:
                answered_questions.append(question)
            else:
                non_answered_questions.append(question)

        return answered_questions, non_answered_questions
