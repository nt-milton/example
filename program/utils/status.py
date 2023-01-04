import math


def get_progress(status, haircut=0):
    total = status.get('total')
    done = status.get('done')

    if not total:
        return 0

    progress = math.floor((done / total) * 100)

    # This one is used for locked programs progress
    if haircut:
        return max((progress - haircut, 0))

    return progress


def get_locked_progress(control_status):
    return get_progress(control_status, 10)


def get_unlocked_progress(tasks_status):
    return get_progress(tasks_status)


def get_tasks_progress(tasks):
    tasks_done = [t for t in tasks if t['status'] == 'COMPLETED']
    return {'id': 'tasks', 'total': len(tasks), 'done': len(tasks_done)}
