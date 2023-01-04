from library.constants import (
    ANSWER_TEXT_WEIGHT,
    POLICY_TITLE_WEIGHT,
    POLICY_WEIGHT,
    QUESTION_WEIGHT,
)


def serialize_search_result(search_result, search_type, search_criteria):
    serializer = get_serializer(search_type)
    return serializer(search_result, search_criteria)


def get_default_question(alias_question):
    from library.models import Question

    return Question.objects.filter(equivalent_questions__in=[alias_question]).first()


def get_serializer(search_type):
    if search_type == 'library_entry':
        return serialize_library_entry
    elif search_type == 'question':
        return serialize_question
    elif search_type == 'policy':
        return serialize_policy


def serialize_library_entry(search_result, search_criteria):
    # Prevent circular dependencies.
    from library.models import Question

    formatted_result = []
    for library_entry in search_result:
        try:
            question = library_entry.question
            if not question.default:
                question = get_default_question(question)
            if not question:
                continue
            formatted_result.append(
                {
                    'id': question.id,
                    'type': 'question',
                    'response': question,
                    'weight': ANSWER_TEXT_WEIGHT,
                }
            )
        except Question.DoesNotExist:
            pass
    return formatted_result


def serialize_question(search_result, search_criteria):
    formatted_result = []
    for question in search_result:
        if not question.default:
            question = get_default_question(question)
        if not question:
            continue
        formatted_result.append(
            {
                'id': question.id,
                'type': 'question',
                'response': question,
                'weight': QUESTION_WEIGHT,
            }
        )

    return formatted_result


def serialize_policy(search_result, search_criteria):
    formatted_result = []
    for policy in search_result:
        weight = (
            POLICY_TITLE_WEIGHT if search_criteria in policy.name else POLICY_WEIGHT
        )
        formatted_result.append(
            {'id': policy.id, 'type': 'policy', 'response': policy, 'weight': weight}
        )

    return formatted_result
