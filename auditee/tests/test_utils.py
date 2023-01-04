import base64
import io

from django.core.files import File

from fieldwork.utils import add_evidence_attachment


def create_evidence_attachment(
    organization, evidence, attachment_name='attachment', sample_id=None
):
    txt_file = 'This is a simple attachment'
    base64_file_bytes = base64.b64encode(txt_file.encode('ascii'))
    base64_file_message = base64_file_bytes.decode('ascii')
    message_encode = base64_file_message.encode('ascii')
    uploaded_files = [
        File(name=attachment_name, file=io.BytesIO(base64.b64decode(message_encode)))
    ]
    policies = []
    documents = []
    officers = []
    teams = []
    objects_ids = []
    monitors = []
    vendors = []
    trainings = []

    return add_evidence_attachment(
        evidence,
        policies,
        uploaded_files,
        documents,
        officers,
        teams,
        objects_ids,
        monitors,
        vendors,
        trainings,
        organization=organization,
        sample_id=sample_id,
        time_zone=None,
    )


def create_data_file():
    txt_file = 'This is a simple attachment'
    base64_file_bytes = base64.b64encode(txt_file.encode('ascii'))
    base64_file_message = base64_file_bytes.decode('ascii')
    message_encode = base64_file_message.encode('ascii')
    data_file = File(
        name='attachment', file=io.BytesIO(base64.b64decode(message_encode))
    )

    return data_file
