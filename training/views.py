from django.db import connection
from django.http.response import HttpResponse
from django.views.decorators.http import require_GET

from laika.auth import login_required
from laika.utils.pdf import render_template_to_pdf

from .models import Training

trainings = Training.objects.all()


@require_GET
@login_required
def export_training_log(request, training_id):
    training = Training.objects.get(pk=training_id)
    time_zone = request.GET.get('time_zone')
    pdf = render_template_to_pdf(
        template='training/export_training_log.html',
        context={
            'training': training,
            'members': training.alumni.all(),
        },
        time_zone=time_zone,
    )

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment;filename="{training.name}-log.pdf"'
    return response


@require_GET
@login_required
def export_training_exception_report(request):
    organization_id = request.user.organization_id

    query = '''
        SELECT
        O.NAME AS "ORGANIZATION",
        T.NAME AS "TRAINING NAME",
        CONCAT(INITCAP(U.FIRST_NAME), ' ', INITCAP(U.LAST_NAME))
        AS "FULL NAME",
        U.EMAIL AS "EMAIL"
        FROM PUBLIC.ORGANIZATION_ORGANIZATION O
        LEFT JOIN PUBLIC.USER_USER U ON U.ORGANIZATION_ID = O.ID
        LEFT JOIN PUBLIC.TRAINING_TRAINING T
        ON T.ORGANIZATION_ID = O.ID AND T.roles::jsonb ?& array[U."role"]
        LEFT JOIN PUBLIC.TRAINING_ALUMNI A
        ON A.TRAINING_ID = T.ID AND A.USER_ID = U.ID
        WHERE
        U.DELETED_AT IS NULL AND
        A.ID IS NULL AND O.ID = %s
        GROUP BY O.NAME, T.NAME, U.FIRST_NAME, U.LAST_NAME, U.EMAIL
        ORDER BY
        O.NAME,
        T.NAME,
        "FULL NAME";
    '''

    with connection.cursor() as cursor:
        cursor.execute(query, [organization_id])
        trainings = cursor.fetchall()

    time_zone = request.GET.get('time_zone')
    pdf = render_template_to_pdf(
        template='training/export_training_exception.html',
        context={'trainings': trainings},
        time_zone=time_zone,
    )

    response = HttpResponse(pdf, content_type='application/pdf')
    response[
        'Content-Disposition'
    ] = 'attachment;filename="training_exception_report.pdf"'
    return response


def get_training_pdf(training, time_zone):
    return render_template_to_pdf(
        template='training/export_training_log.html',
        context={
            'training': training,
            'members': training.alumni.all(),
        },
        time_zone=time_zone,
    )
