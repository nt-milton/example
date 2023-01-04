CREATE_IDP = '''
    mutation CreateIdentityProvider($provider: String!){
        createIdentityProvider(provider: $provider) {
            data {
                idpId,
                name,
                status,
                clientFields {
                    issuerUri,
                    ssoUrl
                },
                laikaFields {
                    assertionConsumerServiceUrl,
                    audienceUri
                },
            }
        }
    }
'''

UPDATE_IDP = '''
    mutation UpdateIdentityProvider(
        $idpId: String!,
        $name: String,
        $ssoUrl: String,
        $issuerUri: String,
        $certificate: String
    ) {
        updateIdentityProviderById(
            idpId: $idpId,
            name: $name,
            ssoUrl: $ssoUrl,
            issuerUri: $issuerUri,
            certificate: $certificate
        ) {
            data {
                status
                error
            }
        }
    }
'''

SET_IDP_DOMAINS = '''
    mutation SetIdentityProviderDomains($idpId: String!, $domains: [String]){
        setIdentityProviderDomains(idpId: $idpId, domains: $domains) {
            data {
                domains
                error
            }
        }
    }
'''

DISABLE_IDP = '''
    mutation DisableIdentityProvider($idpId: String!){
        disableIdentityProvider(idpId: $idpId) {
            data {
                idpId
                error
            }
        }
    }
'''

ENABLE_IDP = '''
    mutation EnableIdentityProvider($idpId: String!){
        enableIdentityProvider(idpId: $idpId) {
            data {
                idpId
                error
            }
        }
    }
'''

DELETE_IDP = '''
    mutation DeleteIdentityProvider($idpId: String!){
        deleteIdentityProvider(idpId: $idpId) {
            data {
                idpId
            }
        }
    }
'''
