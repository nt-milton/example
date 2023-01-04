def get_capitalized_name(first_name='', last_name=''):
    first_name = first_name.split(' ')[0]
    last_name = last_name.split(' ')[0]
    return first_name.lower().title() + " " + last_name.lower().title()
