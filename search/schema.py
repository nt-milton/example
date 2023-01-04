import graphene

from laika.auth import login_required
from laika.decorators import laika_service
from search.search import get_launchpad_context
from search.types import CmdKSearchResponseType, SearchResponseType
from search.utils import parsed_global_search, to_cmd_k_results


class Query(object):
    search = graphene.List(
        SearchResponseType,
        search_criteria=graphene.String(),
        filters=graphene.List(graphene.String),
    )

    cmd_k_search = graphene.List(
        CmdKSearchResponseType,
        search_criteria=graphene.String(),
        filters=graphene.List(graphene.String),
    )

    launchpad_context = graphene.List(
        CmdKSearchResponseType,
    )

    @login_required
    def resolve_search(self, info, **kwargs):
        search_criteria = kwargs.get('search_criteria')
        if search_criteria == '':
            return []

        filters = kwargs.get('filters')

        return parsed_global_search(filters, search_criteria, info.context.user)

    @login_required
    def resolve_cmd_k_search(self, info, **kwargs):
        search_criteria = kwargs.get('search_criteria')
        if not search_criteria:
            return []

        filters = kwargs.get('filters')

        formatted_results = parsed_global_search(
            filters, search_criteria, info.context.user
        )

        return to_cmd_k_results(formatted_results)

    @laika_service(
        'dashboard.view_dashboard',
        exception_msg='Failed to retrieve launchpad context',
    )
    def resolve_launchpad_context(self, info, **kwargs):
        user = info.context.user

        return get_launchpad_context(user.organization_id)
