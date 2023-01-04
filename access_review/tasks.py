from datetime import datetime, timedelta, timezone

from access_review.models import AccessReview, AccessReviewVendor
from access_review.mutations import get_reviewers, get_vendors_name_list
from laika.aws.ses import send_email
from laika.celery import app as celery_app
from laika.settings import DJANGO_SETTINGS, NO_REPLY_EMAIL


def get_access_review_overdues():
    return AccessReview.objects.filter(
        due_date__lt=datetime.now(timezone.utc) + timedelta(days=2),
        status=AccessReview.Status.IN_PROGRESS,
    )


def get_access_review_vendors(access_review):
    return AccessReviewVendor.objects.filter(access_review=access_review)


@celery_app.task(name='send_access_review_overdue_emails')
def send_access_review_overdue_emails():
    access_review_overdues = get_access_review_overdues()
    emails_sent = False

    for access_review in access_review_overdues:
        reviewers = get_reviewers(access_review.organization)
        emails = [reviewer.email for reviewer in reviewers]
        laika_web = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')
        access_review_url = f'{laika_web}/access-review/ongoing'
        vendors = get_access_review_vendors(access_review)
        vendors_name_list = get_vendors_name_list(vendors)
        delta = access_review.due_date - datetime.now(timezone.utc)
        subject = 'Your Access Review is overdue'

        if delta.days >= 1:
            subject = f'Your Access Review is due in {delta.days} days'

        send_email(
            subject=subject,
            from_email=NO_REPLY_EMAIL,
            to=emails,
            template='access_review_overdue.html',
            template_context={
                'subject': subject,
                'access_review_name': access_review.name,
                'access_review_url': access_review_url,
                'access_review_due_in_days': delta.days,
                'due_date': access_review.due_date.strftime("%m/%d/%Y"),
                'vendors': vendors_name_list,
                'web_url': DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT'),
            },
        )
        emails_sent = True

    return {'Success': True, 'Emails sent': emails_sent}
