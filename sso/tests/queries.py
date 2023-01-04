GET_IDP = '''
    query GetIdp($idpId: String!) {
        getIdp(idpId: $idpId) {
            idpId
            status
            name
            clientFields {
                issuerUri
                ssoUrl
            }
            laikaFields {
                assertionConsumerServiceUrl
                audienceUri
            }
        }
    }
'''

GET_IDP_DOMAINS = '''
    query GetIdpDomains($idpId: String!){
        getIdpDomains(idpId: $idpId){
            domains
            error
        }
    }
'''

GET_ORGANIZATION_IDP = '''
    query GetOrganizationIdentityProvider {
        getOrganizationIdentityProvider {
            name
            provider
            idpId
        }
    }
'''
