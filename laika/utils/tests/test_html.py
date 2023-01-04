from laika.utils.html import CustomHTMLParser


def test_add_data_attribute_successful():
    html = (
        'Perform an** **initial <a href="https://app.heylaika.com/pentest"'
        ' target="blank">penetration test</a>.\n<br>\n<br>\n**_<b><i>Did you'
        ' know?</i></b> _**_<i>Laika offers an add-on pentest solution that makes it'
        ' easy to find a vetted pentest vendor and speed up your compliance'
        ' journey.</i> _<a'
        ' href="https://help.heylaika.com/en/articles/test"'
        ' target="blank">Learn More</a>'
    )
    html_parser = CustomHTMLParser()
    data_attr_value = 'ai-AI-M-10'
    html_updated = html_parser.add_data_attribute(
        'a',
        html,
        'testid',
        data_attr_value,
        {'Learn More': True},
    )

    assert html_updated.find(data_attr_value) != -1


def test_add_data_attribute_incorrect():
    html = (
        'Perform an** **initial <a '
        ' href="https://help.heylaika.com/en/test"'
        ' target="blank">Learn More</a>'
    )
    html_parser = CustomHTMLParser()
    data_attr_value = 'ai-AI-M-10'
    html_updated = html_parser.add_data_attribute(
        'a',
        html,
        'testid',
        data_attr_value,
        {'Learn': True},
    )

    assert html_updated.find(data_attr_value) == -1
