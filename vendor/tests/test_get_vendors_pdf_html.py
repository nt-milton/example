from bs4 import BeautifulSoup

from laika.utils.templates import render_template


def test_render_fallback_certification_logo():
    context = {
        'organization_name': 'My Org',
        'vendors': [
            {
                'name': 'Slack Vendor',
                'admin': 'Slack Admin',
                'risk': '----',
                'status': '----',
                'logo': '',
                'certifications': [''],
            }
        ],
    }
    html = render_template(
        template='vendors/organization_vendors.html',
        context=context,
    )
    soup = BeautifulSoup(html, 'html.parser')
    image = soup.find(alt='fallback certification logo')
    assert image is not None
    assert 'file' in image.get('src', '')
    assert 'default_certification_logo.png' in image.get('src', '')


def test_render_certification_logo():
    context = {
        'organization_name': 'My Org',
        'vendors': [
            {
                'name': 'Slack Vendor',
                'admin': 'Slack Admin',
                'risk': '----',
                'status': '----',
                'logo': '',
                'certifications': ['SGVsbG8gV29ybGQ='],
            }
        ],
    }
    html = render_template(
        template='vendors/organization_vendors.html',
        context=context,
    )
    soup = BeautifulSoup(html, 'html.parser')
    image = soup.find(src='data:;base64,SGVsbG8gV29ybGQ=')
    assert image is not None
    assert 'data:;base64,SGVsbG8gV29ybGQ=' == image.get('src', '')
