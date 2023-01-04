POPULATION_STATUS = (
    ('open', 'Open'),
    ('submitted', 'Submitted'),
    ('accepted', 'Accepted'),
)

POPULATION_TYPE = (
    ('vendor', 'vendor'),
    ('laika_object', 'laika_object'),
    ('people', 'people'),
)

POPULATION_SOURCE = (('manual', 'manual'), ('laika_source', 'laika_source'))
POPULATION_SOURCE_DICT = dict(POPULATION_SOURCE)

POPULATION_STATUS_DICT = dict((key, value) for value, key in POPULATION_STATUS)

COMPLETENESS_AND_ACCURACY_MAX_FILES_AMOUNT = 5
ZIP_FILE_EXTENSION = '.zip'

POPULATION_DEFAULT_SOURCE = (('People', 'People'),)

POPULATION_DEFAULT_SOURCE_DICT = dict(POPULATION_DEFAULT_SOURCE)
(PEOPLE_SOURCE,) = POPULATION_DEFAULT_SOURCE_DICT.values()

POPULATION_DISPLAY_IDS = {'POP-1': 'POP-1', 'POP-2': 'POP-2'}

POP_1, POP_2 = POPULATION_DISPLAY_IDS.values()
