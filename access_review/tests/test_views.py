import pytest

from access_review.models import AccessReviewObject
from access_review.views import write_csv


@pytest.fixture
def access_review_object(payload_for_access_review_tests):
    (
        laika_object,
        access_review_object,
        connection_account,
    ) = payload_for_access_review_tests
    laika_object.data = {
        'Roles': [{'roleName': 'Role test'}],
        'First Name': 'Test name',
        'Email': 'test@heylaika.com',
    }
    laika_object.save()
    access_review_object.review_status = AccessReviewObject.ReviewStatus.UNCHANGED
    access_review_object.is_confirmed = True
    access_review_object.notes = 'Test notes'
    access_review_object.save()
    return access_review_object


EXPECTED_ROW = (
    'Test name,testing connection account test,test@heylaika.com,'
    '"[{""roleName"": ""Role test""}]",unchanged,'
    'Reviewed,Test notes\r\n'
)

EXPECTED = (
    'Account Name,Connection,Email,Access Role/Group,Marked as,'
    'State,Notes\r\n'
    f'{EXPECTED_ROW}'.encode()
)


@pytest.mark.functional()
def test_write_csv(access_review_object: AccessReviewObject):
    response = write_csv(
        access_review_object.access_review_vendor.id, access_review_object.is_confirmed
    )
    assert response.getvalue() == EXPECTED


@pytest.mark.parametrize(
    'reviewed, excluded_result', [(False, 'Reviewed'), (True, 'In Progress')]
)
@pytest.mark.functional()
def test_write_csv_by_filter(
    reviewed, excluded_result, access_review_object: AccessReviewObject
):
    access_review_object.is_confirmed = reviewed
    access_review_object.save()
    response = write_csv(
        access_review_object.access_review_vendor.id, access_review_object.is_confirmed
    )

    assert excluded_result not in str(response.getvalue())
