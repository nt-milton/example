from user.utils.email import format_super_admin_email


def test_format_super_admin_email():
    assert (
        format_super_admin_email('test@heylaika.com', 'www.google.com')
        == 'test+google@heylaika.com'
    )

    assert (
        format_super_admin_email('test+test@heylaika.com', 'https://www.matraka.com')
        == 'test+test+matraka@heylaika.com'
    )
