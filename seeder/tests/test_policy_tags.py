import re

from seeder.seeders.policies import get_formatted_tags


def test_get_formatted_tags():
    tags = get_formatted_tags('Assessment,AuditTag, Authorization and Monitoring , , ,')
    assert len(tags) == 3
    assert tags[0] == 'Assessment'
    assert tags[1] == 'AuditTag'
    assert tags[2] == 'Authorization and Monitoring'


def test_get_formatted_tags_for_dictionary():
    tag_dict = {
        'tags': (
            'Assessment Authorization and Monitoring  ,'
            '  Assessment Authorization and Monitoring  ,'
            '  Audit and Accountability,'
            'Audit and Accountability'
        )
    }
    for tag in get_formatted_tags(tag_dict.get('tags')):
        assert tag == re.sub("\n|\r", ' ', tag).strip()
