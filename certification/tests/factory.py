import tempfile

from django.core.files import File

from certification.models import (
    Certification,
    CertificationSection,
    UnlockedOrganizationCertification,
)


def unlock_certification_for_organization(organization, certification):
    unlocked_cert = UnlockedOrganizationCertification(
        organization=organization, certification=certification
    )
    unlocked_cert.save(no_cache=True)
    return unlocked_cert


def create_certification(
    organization,
    section_names=[],
    name='DefaultCertification',
    unlock_certificate=True,
    **kwargs
):
    certification = Certification.objects.filter(name=name).first()
    if certification is None:
        certification, _ = Certification.objects.get_or_create(
            name=name, logo=File(file=tempfile.TemporaryFile(), name=name), **kwargs
        )
    if unlock_certificate:
        unlock_certification_for_organization(
            organization=organization, certification=certification
        )

    for section_name in section_names:
        CertificationSection.objects.create(
            name=section_name, certification=certification
        )

    return certification


def create_certificate_sections_list(organization):
    soc2_cert_sections = create_certification(
        organization, ['cc1'], name='SOC 2 TYPE 2'
    ).sections.all()

    pci_cert_sections = create_certification(
        organization, ['pci'], name='PCI'
    ).sections.all()

    cobit_cert_sections = create_certification(
        organization, ['cobit'], name='COBIT'
    ).sections.all()

    soc1_cert_sections = create_certification(
        organization, ['soc1'], name='SOC 1 Type 1'
    ).sections.all()

    iso_27001_sections = create_certification(
        organization, ['2.3'], name='ISO 27001'
    ).sections.all()

    coso_sections = create_certification(
        organization, ['coso'], name='COSO'
    ).sections.all()

    return (
        soc2_cert_sections.union(pci_cert_sections)
        .union(cobit_cert_sections)
        .union(soc1_cert_sections)
        .union(iso_27001_sections)
        .union(coso_sections)
    )
