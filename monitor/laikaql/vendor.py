from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
    select
    vv.id as vendor_id,
    vv.name,
    vv.description,
    (Select uu.first_name || ' ' || uu.last_name as admin
    from vendor_organizationvendorstakeholder as vs
    left join user_user as uu
    on vs.stakeholder_id = uu.id where
    vv.id = vs.organization_vendor_id limit 1),
    array (Select cc.name
    from vendor_vendorcertification as vc
    left join certification_certification as cc
    on vc.certification_id = cc.id
    where vv.id = vc.vendor_id ) as compliant_with,
    vo.risk_rating as criticality,
    vo.status,
    vv.website,
    array (Select vca.name
    from vendor_category as vca
    left join vendor_vendorcategory as vc
    on vc.category_id = vca.id
    where vv.id = vc.vendor_id ) as type,
    array(Select uu.first_name || ' ' || uu.last_name
    from vendor_organizationvendorstakeholder as vs
    left join user_user as uu
    on vs.stakeholder_id = uu.id where
    vv.id = vs.organization_vendor_id) as internal_stakeholders,
    vo.primary_external_stakeholder_name,
    vo.primary_external_stakeholder_email,
    vo.secondary_external_stakeholder_name,
    vo.secondary_external_stakeholder_email,
    vo.financial_exposure,
    vo.operational_exposure,
    vo.data_exposure,
    vo.risk_rating,
    vo.purpose_of_the_solution,
    vo.additional_notes,
    vo.contract_start_date,
    vo.contract_renewal_date
    from vendor_vendor vv left join
    vendor_organizationvendor vo on vv.id = vo.vendor_id
    where vo.organization_id = '{organization.id}'
    '''
