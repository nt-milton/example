import logging
from ast import literal_eval
from typing import Dict

import numpy as np
import openai
import pandas as pd
from django.core.files.base import ContentFile, File

from laika.utils.ai import open_ai
from laika.utils.ai.constants import OPEN_AI_FLAG
from library.constants import RESULT_FOUND
from library.models import Question
from organization.models import Organization
from policy.models import Policy

logger = logging.getLogger(__name__)

MODEL_NAME = "babbage"
COMPLETION_MODEL = 'text-davinci-002'
QUERY_EMBEDDINGS_MODEL = f"text-search-{MODEL_NAME}-query-001"
MAX_TOKENS = 250
TEMPERATURE = 0
UNKNOWN_ANSWER = 'unknown'


def get_embedding(text: str, model: str) -> list[float]:
    result = open_ai.Embedding.create(model=model, input=text)
    return result["data"][0]["embedding"]


def get_query_embedding(text: str) -> list[float]:
    return get_embedding(text, QUERY_EMBEDDINGS_MODEL)


def cosine(x, y):
    from numpy.linalg import norm

    return np.dot(x, y) / (norm(x) * norm(y))


def order_document_sections_by_query_similarity(question_embeddings, policy_embeddings):
    """
    Compare the question embedding against all the pre-calculated embeddings for the
    policy to find the most relevant sections.

    Return the list of document sections, sorted by relevance in descending order.
    """

    document_similarities = sorted(
        [
            (cosine(question_embeddings, row), index)
            for index, row in enumerate(policy_embeddings)
        ],
        reverse=True,
    )

    return document_similarities


def construct_question_prompt(question: Question, best_policy):
    index = best_policy.get('embedding_index')
    texts = best_policy.get('texts')
    index -= 1

    if index <= 2:
        chosen_sections = texts[:5]
    elif index == len(texts) - 3:
        chosen_sections = texts[-5:]
    else:
        chosen_sections = texts[index - 2 : index + 2]
    header = (
        'Answer the question as truthfully as possible '
        'using the provided context, and if the answer is not '
        f'contained within the text below, say "{UNKNOWN_ANSWER}"\n\nContext:\n'
    )
    return header + " ".join(chosen_sections) + "\n\n Q: " + question.text + "\n A:"


def can_use_answer(answer: str):
    return answer.lower() != UNKNOWN_ANSWER


def use_ai_answer(question: Question, answer: str):
    question.library_entry.answer_text = answer
    question.fetch_status = RESULT_FOUND
    question.library_entry.save()
    question.save()


def answer_question_from_policy(question: Question, best_policy: Dict):
    prompt = construct_question_prompt(question, best_policy)
    completion_answer = openai.Completion.create(
        engine=COMPLETION_MODEL,
        prompt=prompt,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
    )
    answer = completion_answer.choices[0].text.strip()
    if not can_use_answer(answer):
        return False
    use_ai_answer(question, answer)
    return True


def get_question_embedding(question: Question):
    if not question.embedding:
        question_embedding = get_embedding(question.text, QUERY_EMBEDDINGS_MODEL)
        df = pd.DataFrame(
            {
                'Id': 1,
                'Embedding': question_embedding,
            }
        )
        question.embedding = File(
            name='embedding.csv',
            file=ContentFile(df.to_csv().encode('utf-8')),
        )
        question.save()
        return question_embedding

    pd_question = pd.read_csv(question.embedding.file, index_col=0)
    return pd_question['Embedding'].values


def get_best_policy_option(organization: Organization, question_embedding):
    best_policy = None

    for policy in Policy.objects.filter(organization=organization, is_published=True):
        latest_published_policy = policy.versions.latest('version')
        policy_embedding_file = latest_published_policy.embedding
        if not policy_embedding_file:
            continue
        pd_policy = pd.read_csv(policy_embedding_file.file, index_col=0)
        policy_embeddings = pd_policy['similarity'].apply(literal_eval).values

        ordered_embeddings = order_document_sections_by_query_similarity(
            question_embedding, policy_embeddings
        )
        if len(ordered_embeddings) == 0:
            continue
        best_policy_embedding_score, index = ordered_embeddings[0]
        if not best_policy or best_policy_embedding_score > best_policy.get('score'):
            best_policy = {
                'score': best_policy_embedding_score,
                'embedding_index': index,
                'embeddings': policy_embeddings,
                'texts': pd_policy['Text'].values,
                'policy_id': policy.id,
            }
    if best_policy:
        logger.info(
            f'OPENAI - Best match {best_policy.get("policy_id")} '
            f'index: {best_policy.get("embedding_index")}'
            f'score: {best_policy.get("score")}'
        )
    return best_policy


def ai_answer_question(question: Question, organization: Organization):
    if not organization.is_flag_active(OPEN_AI_FLAG):
        return False

    try:
        question_embedding = get_question_embedding(question)
        best_policy_option = get_best_policy_option(organization, question_embedding)

        if not best_policy_option:
            return False

        return answer_question_from_policy(question, best_policy_option)
    except Exception as e:
        logger.error(f'Error trying to answer question {question.id} with AI {e}')
