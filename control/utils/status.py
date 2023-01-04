from control.constants import STATUS

valid_status = [STATUS.get('IMPLEMENTED'), STATUS.get('NOT IMPLEMENTED')]


def can_transition_status(old_status, new_status):
    if new_status == old_status:
        return True

    return new_status in valid_status


def get_progress(controls):
    total = 0
    for c in controls:
        if c.status == STATUS.get('IMPLEMENTED'):
            total += 1

    return {'id': 'controls', 'total': total, 'done': total}
