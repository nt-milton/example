from typing import List


def get_user_name_values(user_name: str) -> List[str]:
    first_name = ''
    last_name = ''

    if not user_name:
        return [first_name, last_name]

    names = user_name.split(' ')
    if len(names) > 2:
        first_name = names[0]
        last_name = f'{names[1]} {names[2]}'
    elif len(names) == 2:
        first_name = names[0]
        last_name = names[1]
    else:
        first_name = names[0]

    return [first_name, last_name]
