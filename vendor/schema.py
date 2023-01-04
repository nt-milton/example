import base64
import io
import logging
from decimal import Decimal

import graphene
import reversion
from django.core.files import File
from django.db import transaction
from django.db.models import (
    BooleanField,
    Case,
    Count,
    ExpressionWrapper,
    F,
    IntegerField,
    Q,
    TextField,
    Value,
    When,
)
from django.db.models.functions import Concat, Replace
from django.forms.models import model_to_dict
from graphene_django.types import DjangoObjectType

import evidence.constants as constants
from certification.models import Certification
from certification.types import CertificationType
from evidence.utils import get_content_id
from laika import types
from laika.auth import login_required
from laika.decorators import laika_service
from laika.types import OrderInputType, PaginationInputType, PaginationResponseType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import ServiceException, service_exception
from laika.utils.history import create_revision
from laika.utils.order_by import get_default_order_by_query, get_order_query
from laika.utils.paginator import get_paginated_result
from objects.models import LaikaObject
from objects.system_types import SERVICE_ACCOUNT, USER
from user.models import User
from user.types import UserType
from vendor.helpers import get_organization_vendor_filters, get_vendor_filters
from vendor.mutations import (
    AddVendorDocuments,
    ConfirmVendorCandidates,
    DeleteVendorDocuments,
)
from vendor.types import (
    FiltersVendorType,
    ServiceAccountType,
    VendorEvidenceType,
    VendorFiltersType,
)

from .models import (
    DISCOVERY_STATUS_IGNORED,
    DISCOVERY_STATUS_NEW,
    Category,
    OrganizationVendor,
    OrganizationVendorStakeholder,
    Vendor,
    VendorCategory,
    VendorCertification,
)

logger = logging.getLogger('vendor')


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 50


class CategoryType(DjangoObjectType):
    class Meta:
        model = Category


class VendorType(DjangoObjectType):
    class Meta:
        model = Vendor

    id = graphene.ID()
    name = graphene.String()
    logo = graphene.Field(types.FileType)
    full_logo = graphene.Field(types.FileType)
    certifications = graphene.List(CertificationType)
    is_in_organization = graphene.Boolean()
    number_of_users = graphene.Int()

    def resolve_logo(self, info):
        return self.logo or None

    def resolve_full_logo(self, info):
        return self.full_logo or None

    def resolve_certifications(self, info):
        return [
            CertificationType(**model_to_dict(c.certification), url=c.url)
            for c in self.vendor_certifications.all()
        ]

    def resolve_is_in_organization(self, info):
        return bool(self.is_in_organization)

    @staticmethod
    def resolve_number_of_users(root, info):
        vendor_candidate_loader = info.context.loaders.vendor
        return vendor_candidate_loader.vendor_candidates_by_vendor.load(root.id)


class VendorCandidateType(graphene.ObjectType):
    new = graphene.List(VendorType)
    ignored = graphene.List(VendorType)


class VendorUserType(graphene.ObjectType):
    name = graphene.String()
    email = graphene.String()
    created_at = graphene.DateTime()
    user_data = graphene.Field(UserType)


class OrganizationVendorType(DjangoObjectType):
    class Meta:
        model = OrganizationVendor

    status = graphene.String()
    operational_exposure = graphene.String()
    data_exposure = graphene.String()
    risk_rating = graphene.String()
    risk_rating_rank = graphene.Int()
    documents = graphene.List(VendorEvidenceType)
    vendor_users = graphene.List(VendorUserType)

    def resolve_status(self, info):
        return self.get_status_display()

    def resolve_operational_exposure(self, info):
        return self.get_operational_exposure_display()

    def resolve_data_exposure(self, info):
        return self.get_data_exposure_display()

    def resolve_risk_rating(self, info):
        return self.get_risk_rating_display()

    def resolve_internal_stakeholders(self, info):
        stakeholders = self.internal_organization_stakeholders.all().order_by(
            'sort_index'
        )
        return [s.stakeholder for s in stakeholders]

    def resolve_documents(self, info):
        # TODO: Exclude here the non published policies
        all_documents = self.documents.all().order_by('-created_at')
        evidence = []
        for doc in all_documents:
            if doc.type == constants.POLICY and not doc.policy.is_published:
                continue
            evidence.append(
                # This should return instances of evidence and reuse the
                # EvidenceType instead of using VendorEvidenceType.
                VendorEvidenceType(
                    id=doc.id,
                    name=doc.name,
                    link=doc.file.url
                    if doc.file
                    and doc.type in [constants.FILE, constants.TEAM, constants.OFFICER]
                    else '',
                    description=doc.description,
                    date=doc.created_at,
                    evidence_type=doc.type,
                    linkable=(
                        doc.type
                        not in (constants.FILE, constants.TEAM, constants.OFFICER)
                    ),
                    content_id=get_content_id(doc),
                )
            )
        return evidence

    def resolve_vendor_users(self, info):
        integration_users = []
        connections = self.organization.connection_accounts.filter(
            integration__vendor=self.vendor
        )
        connection_lo_users = LaikaObject.objects.filter(
            connection_account__in=connections, object_type__type_name=USER.type
        )
        sso_users = self.sso_users.all()
        # Laikaobjects user type
        for lo_user in connection_lo_users:
            email = lo_user.data.get('Email', '')
            first_name = lo_user.data.get('First Name', '')
            last_name = lo_user.data.get('Last Name', '')
            created_at = lo_user.created_at
            laika_person = User.objects.filter(email=email)
            laika_person = laika_person.first()
            user_object = VendorUserType(
                name=f'{first_name} {last_name}',
                email=email,
                created_at=created_at,
                user_data=laika_person,
            )
            integration_users.append(user_object)
        # OrganizationVendorUsersSSO
        for sso_user in sso_users:
            email = sso_user.email
            name = sso_user.name
            laika_person = User.objects.filter(email=email)
            laika_person = laika_person.first()
            user_object = VendorUserType(name=name, email=email, user_data=laika_person)
            integration_users.append(user_object)
        return set(integration_users)


class VendorResponseType(graphene.ObjectType):
    data = graphene.List(OrganizationVendorType)
    pagination = graphene.Field(PaginationResponseType)
    filters = graphene.List(VendorFiltersType)

    def resolve_filters(self, info, **kwargs):
        organization = info.context.user.organization
        filters = get_organization_vendor_filters(organization)
        return filters


class ServiceAccountResponseType(graphene.ObjectType):
    results = graphene.List(ServiceAccountType)
    pagination = graphene.Field(PaginationResponseType)


class VendorOrderInputType(graphene.InputObjectType):
    field = graphene.String(required=True)
    order = graphene.String(required=True)


class Query(object):
    vendors = graphene.List(VendorType, search_criteria=graphene.String())
    vendor_candidates = graphene.Field(
        VendorCandidateType,
    )
    organization_vendors = graphene.List(OrganizationVendorType)
    organization_vendor = graphene.Field(OrganizationVendorType, id=graphene.Int())
    filtered_organization_vendors = graphene.Field(
        VendorResponseType,
        page_size=graphene.Int(),
        page=graphene.Int(),
        filters=graphene.Argument(FiltersVendorType, required=False),
        order_by=graphene.Argument(VendorOrderInputType, required=False),
    )
    certifications = graphene.List(CertificationType)
    service_accounts_per_vendor = graphene.Field(
        ServiceAccountResponseType,
        id=graphene.ID(),
        search_criteria=graphene.String(required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
        order_by=graphene.Argument(graphene.List(OrderInputType), required=False),
    )

    @laika_service(
        permission='vendor.view_organizationvendor',
        exception_msg='Cannot get organization vendors',
    )
    def resolve_service_accounts_per_vendor(self, info, **kwargs):
        organization = info.context.user.organization

        search_by_account_name = Q()
        search_criteria = kwargs.get('search_criteria')
        if search_criteria:
            search_by_account_name = (
                Q(**{'data__First Name__icontains': search_criteria})
                | Q(**{'data__Last Name__icontains': search_criteria})
                | Q(**{'data__Display Name__icontains': search_criteria})
            )

        order_by = kwargs.get(
            'order_by', [{'field': 'account_name', 'order': 'descend'}]
        )
        order_queries = []
        for order_declaration in order_by:
            field = order_declaration.get('field')
            order = order_declaration.get('order')
            expression = (
                F(field).desc(nulls_last=True)
                if order == 'descend'
                else F(field).asc(nulls_last=True)
            )
            order_queries.append(expression)

        pagination = kwargs.get('pagination')
        page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE
        page = pagination.page if pagination else DEFAULT_PAGE

        result = (
            LaikaObject.objects.filter(
                search_by_account_name,
                deleted_at__isnull=True,
                connection_account__organization=organization,
                connection_account__integration__vendor__id=kwargs['id'],
                object_type__type_name__in=[USER.type, SERVICE_ACCOUNT.type],
            )
            .annotate(
                account_name=Case(
                    When(
                        object_type__type_name='user',
                        then=Replace(
                            Concat('data__First Name', Value(' '), 'data__Last Name'),
                            Value('"'),
                            Value(''),
                        ),
                    ),
                    When(
                        object_type__type_name='service_account',
                        then=Replace(
                            Concat('data__Display Name', Value('')),
                            Value('"'),
                            Value(''),
                        ),
                    ),
                    default=Value('N/A'),
                    output_field=TextField(),
                )
            )
            .order_by(*order_queries)
        )

        paginated_result = get_paginated_result(result, page_size, page)

        return ServiceAccountResponseType(
            results=list(paginated_result.get('data', [])),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @laika_service(
        permission='vendor.view_vendorcandidate',
        exception_msg='Cannot get vendor candidates',
    )
    def resolve_vendor_candidates(self, info, **kwargs):
        organization = info.context.user.organization
        new_vendor_candidates = organization.vendor_candidates.filter(
            status=DISCOVERY_STATUS_NEW, vendor__isnull=False
        ).prefetch_related('vendor')
        new_vendors = [
            vendor_candidate.vendor for vendor_candidate in new_vendor_candidates
        ]
        ignored_vendor_candidates = organization.vendor_candidates.filter(
            status=DISCOVERY_STATUS_IGNORED, vendor__isnull=False
        ).prefetch_related('vendor')
        ignored_vendors = [
            vendor_candidate.vendor for vendor_candidate in ignored_vendor_candidates
        ]
        return VendorCandidateType(new=new_vendors, ignored=ignored_vendors)

    @login_required
    @service_exception('Cannot get vendors')
    def resolve_vendors(self, info, **kwargs):
        search_criteria = kwargs.get('search_criteria')

        if not search_criteria or not search_criteria.strip():
            return []

        query = Q(name__icontains=search_criteria.strip())
        is_in_organization = Q(id__in=info.context.user.organization.vendors.all())

        return Vendor.objects.filter(query).annotate(
            is_in_organization=ExpressionWrapper(is_in_organization, BooleanField())
        )

    @login_required
    @service_exception('Cannot get organization vendor')
    def resolve_organization_vendor(self, info, **kwargs):
        return info.context.user.organization.organization_vendors.get(
            pk=kwargs.get('id')
        )

    @login_required
    @service_exception('Cannot get organization vendors')
    def resolve_organization_vendors(self, info, **kwargs):
        return info.context.user.organization.organization_vendors.all()

    @login_required
    @service_exception('Cannot get filtered organization vendors')
    def resolve_filtered_organization_vendors(self, info, **kwargs):
        DEFAULT_ORDER_BY = {'field': 'vendor__name', 'order': 'ascend'}
        ord_by = kwargs.get('order_by', DEFAULT_ORDER_BY)
        filters = kwargs.get('filters', {})
        search = filters.get('search', '')
        search_filter = Q(vendor__name__unaccent__icontains=search)
        vendor_filters = get_vendor_filters(filters)
        risk_rating_rank = Case(
            When(risk_rating='critical', then=4),
            When(risk_rating='high', then=3),
            When(risk_rating='medium', then=2),
            When(risk_rating='low', then=1),
            When(risk_rating='', then=0),
            output_field=IntegerField(),
        )
        admin_count = Count('internal_stakeholders', output_field=IntegerField())
        certs_count = Count('vendor__certifications', output_field=IntegerField())
        ord_query_dic = {
            'risk_rating': get_order_query('risk_rating_rank', ord_by["order"]),
            'internal_stakeholders': get_order_query('admin_count', ord_by["order"]),
            'vendor__certifications': get_order_query('certs_count', ord_by["order"]),
        }
        order_query = ord_query_dic.get(
            ord_by["field"], get_default_order_by_query('vendor__name', **kwargs)
        )
        data = (
            info.context.user.organization.organization_vendors.filter(
                search_filter & vendor_filters
            )
            .annotate(
                risk_rating_rank=risk_rating_rank,
                admin_count=admin_count,
                certs_count=certs_count,
            )
            .order_by(order_query)
        )
        page = kwargs.get('page')
        page_size = kwargs.get('page_size') or DEFAULT_PAGE_SIZE
        paginated_result = get_paginated_result(data, page_size, page)
        return VendorResponseType(
            data=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @login_required
    @service_exception('Cannot get certifications')
    def resolve_certifications(self, info, **kwargs):
        return Certification.objects.all()


class AddVendorToOrganizationInput(graphene.InputObjectType):
    vendor_id = graphene.Int(required=True)


class AddVendorToOrganization(graphene.Mutation):
    class Arguments:
        input = AddVendorToOrganizationInput(required=True)

    success = graphene.Boolean(default_value=True)

    @login_required
    @service_exception('Cannot add vendor to organization')
    def mutate(self, info, input):
        _, created = OrganizationVendor.objects.get_or_create(
            organization=info.context.user.organization, vendor_id=input.vendor_id
        )
        if not created:
            raise ServiceException('Vendor already exists')
        return AddVendorToOrganization()


class VendorInput(object):
    name = graphene.String(required=True)
    website = graphene.String(required=True)
    description = graphene.String(required=True)
    file_name = graphene.String()
    file_contents = graphene.String()
    category_names = graphene.List(graphene.String)
    certification_ids = graphene.List(graphene.Int)


class StakeholderInput(graphene.InputObjectType):
    sort_index = graphene.Int()
    stakeholder_id = graphene.String()


class OrganizationVendorInput(object):
    status = graphene.String()
    financial_exposure = graphene.Float()
    operational_exposure = graphene.String()
    data_exposure = graphene.String()
    risk_rating = graphene.String()
    risk_assessment_date = graphene.Date()
    purpose_of_the_solution = graphene.String()
    additional_notes = graphene.String()
    contract_start_date = graphene.String()
    contract_renewal_date = graphene.String()
    internal_stakeholder_ids = graphene.List(StakeholderInput, required=False)
    primary_external_stakeholder_name = graphene.String()
    primary_external_stakeholder_email = graphene.String()
    secondary_external_stakeholder_name = graphene.String()
    secondary_external_stakeholder_email = graphene.String()


class CreateOrganizationVendorInput(
    VendorInput, OrganizationVendorInput, types.DjangoInputObjectBaseType
):
    class InputMeta:
        model = Vendor


class CreateOrganizationVendor(graphene.Mutation):
    class Arguments:
        input = CreateOrganizationVendorInput(required=True)

    success = graphene.Boolean(default_value=True)

    @login_required
    @transaction.atomic
    @service_exception('Cannot create organization vendor')
    @create_revision('Created organization vendor')
    def mutate(self, info, input):
        stripped_vendor_name = input.name.strip()
        if Vendor.objects.filter(name__iexact=stripped_vendor_name).exists():
            raise ServiceException(f'{input.name} vendor already exists')

        logo = None
        if input.file_name and input.file_contents:
            logo = File(
                name=input.file_name,
                file=io.BytesIO(base64.b64decode(input.file_contents)),
            )

        vendor = input.to_model(logo=logo, is_public=False, name=stripped_vendor_name)

        if input.category_names:
            for category_name in input.category_names:
                category, _ = Category.objects.get_or_create(name=category_name)
                vendor.categories.add(category)

        OrganizationVendor.objects.create(
            organization=info.context.user.organization, vendor=vendor
        )
        for certification_id in input.certification_ids:
            VendorCertification.objects.create(
                vendor=vendor, certification_id=certification_id
            )

        return CreateOrganizationVendor()


class DeleteOrganizationVendorInput(graphene.InputObjectType):
    ids = graphene.List(graphene.Int)
    vendor_ids = graphene.List(graphene.Int)


class DeleteOrganizationVendor(graphene.Mutation):
    class Arguments:
        input = DeleteOrganizationVendorInput(required=True)

    success = graphene.Boolean(default_value=True)

    @login_required
    @transaction.atomic
    @service_exception(
        'Cannot delete vendor because it’s connected to Laika via Integration'
    )
    def mutate(self, info, input):
        organization = info.context.user.organization
        filter_query = (
            Q(id__in=input.ids) if input.ids else Q(vendor__id__in=input.vendor_ids)
        )
        filter_query.add(Q(organization=organization), Q.AND)

        organization_vendors = OrganizationVendor.objects.filter(filter_query)
        for organization_vendor in organization_vendors:
            with reversion.create_revision():
                reversion.set_user(info.context.user)
                reversion.set_comment('Deleted organization vendor')
                organization_vendor.delete()

        return DeleteOrganizationVendor()


class UpdateOrganizationVendorInput(
    VendorInput, OrganizationVendorInput, types.DjangoInputObjectBaseType
):
    class InputMeta:
        model = OrganizationVendor

    name = graphene.String()
    website = graphene.String()
    description = graphene.String()


class UpdateOrganizationVendor(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = UpdateOrganizationVendorInput(required=True)

    success = graphene.Boolean(default_value=True)

    @login_required
    @transaction.atomic
    @service_exception('Cannot update organization vendor')
    @create_revision('Updated organization vendor')
    def mutate(self, info, id, input):
        organization = info.context.user.organization
        organization_vendor: OrganizationVendor = organization.organization_vendors.get(
            pk=id
        )
        input.to_model(
            update=organization_vendor,
            save=False,
        )

        if not organization_vendor.vendor.is_public:
            vendor = organization_vendor.vendor
            vendor.name = input.name or vendor.name
            vendor.website = input.website or vendor.website
            vendor.description = input.description or vendor.description

            UpdateOrganizationVendor.update_logo(input, vendor)
            UpdateOrganizationVendor.update_certifications(input, vendor)
            UpdateOrganizationVendor.update_categories(input, vendor)

            vendor.full_clean()
            vendor.save()

        if input.internal_stakeholder_ids is not None:
            OrganizationVendorStakeholder.objects.filter(
                organization_vendor=organization_vendor
            ).delete()

            for stakeholder in input.internal_stakeholder_ids:
                OrganizationVendorStakeholder.objects.create(
                    organization_vendor=organization_vendor,
                    stakeholder=User.objects.get(
                        organization=organization, username=stakeholder.stakeholder_id
                    ),
                    sort_index=stakeholder.sort_index,
                )

        organization_vendor.financial_exposure = Decimal(
            str(round(organization_vendor.financial_exposure, 2))
        )
        organization_vendor.full_clean()
        organization_vendor.save()
        return UpdateOrganizationVendor()

    @staticmethod
    def update_categories(input, vendor):
        if input.category_names is not None:
            VendorCategory.objects.filter(vendor=vendor).delete()

            for category_name in input.category_names:
                category, _ = Category.objects.get_or_create(name=category_name)
                vendor.categories.add(category)

    @staticmethod
    def update_certifications(input, vendor):
        if input.certification_ids is not None:
            VendorCertification.objects.filter(vendor=vendor).delete()

            certifications = Certification.objects.filter(
                pk__in=input.certification_ids
            )

            for certification in certifications:
                vendor.certifications.add(certification)

    @staticmethod
    def update_logo(input, vendor):
        if input.file_name == '' and input.file_contents == '':
            vendor.logo = None
        if input.file_name and input.file_contents:
            vendor.logo = File(
                name=input.file_name,
                file=io.BytesIO(base64.b64decode(input.file_contents)),
            )


class Mutation(graphene.ObjectType):
    add_vendor_to_organization = AddVendorToOrganization.Field()
    create_organization_vendor = CreateOrganizationVendor.Field()
    update_organization_vendor = UpdateOrganizationVendor.Field()
    delete_organization_vendor = DeleteOrganizationVendor.Field()
    add_vendor_documents = AddVendorDocuments.Field()
    delete_vendor_documents = DeleteVendorDocuments.Field()
    confirm_vendor_candidates = ConfirmVendorCandidates.Field()
