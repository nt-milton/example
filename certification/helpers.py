from django.db.models import Case, Count, F, Q, Value, When

from action_item.models import ActionItemStatus


def get_certification_controls(certification_sections, certification_code):
    all_controls = []
    unique_controls = []
    for cs in certification_sections:
        all_controls.extend(cs.controls.all())
    for c in all_controls:
        if c not in unique_controls and control_certification_code_match(
            c.reference_id, certification_code
        ):
            unique_controls.append(c)
    return unique_controls


def control_certification_code_match(control_reference_id, certification_code):
    return (
        control_reference_id.endswith(certification_code)
        if control_reference_id
        else False
    )


def get_total_required_action_items(action_items) -> int:
    return len([ai for ai in action_items if ai.is_required])


def get_required_action_items_completed(action_items) -> int:
    return len(
        [
            ai
            for ai in action_items
            if ai.is_required
            and ai.status
            in [ActionItemStatus.COMPLETED, ActionItemStatus.NOT_APPLICABLE]
        ]
    )


def get_certification_progress(
    required_action_items_completed, total_required_action_items
) -> int:
    if not total_required_action_items:
        return 0
    return required_action_items_completed * 100 / total_required_action_items


def certification_action_items_per_user_query(user):
    return Q(certification__sections__controls__action_items__assignees=user)


def certification_required_action_items_query(organization_id):
    required_action_items = Q(
        certification__sections__controls__action_items__is_required=True,
        certification__sections__controls__organization__id=organization_id,
        certification__sections__controls__reference_id__endswith=F(
            'certification_code'
        ),
    )

    return required_action_items


def certification_required_action_items_completed_query():
    status_lookup = 'certification__sections__controls__action_items__status'
    completed_query = Q(**{status_lookup: ActionItemStatus.COMPLETED})
    not_applicable_query = Q(**{status_lookup: ActionItemStatus.NOT_APPLICABLE})
    return completed_query | not_applicable_query


def unlocked_certifications_progress_annotate(
    total_action_items_query: Q, completed_action_items_query: Q
):
    progress_annotate = {
        'certification_code': F('certification__code'),
        'total_required_action_items': Count(
            'certification__sections__controls__action_items',
            filter=total_action_items_query,
            distinct=True,
        ),
        'required_action_items_completed': Count(
            'certification__sections__controls__action_items',
            filter=(total_action_items_query & completed_action_items_query),
            distinct=True,
        ),
        'progress': Case(
            When(total_required_action_items=0, then=Value(0)),
            default=(
                F('required_action_items_completed')
                * 100
                / F('total_required_action_items')
            ),
        ),
    }

    return progress_annotate
