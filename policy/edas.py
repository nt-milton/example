from action_item.constants import ACTION_ITEM_COMPLETED_EVENT
from laika.edas.decorators import Edas
from laika.edas.edas import EdaRegistry
from policy.constants import PUBLISHED_POLICY_EVENT

EdaRegistry.register_events(app=__package__, events=[PUBLISHED_POLICY_EVENT])


@Edas.on_event(subscribed_to=ACTION_ITEM_COMPLETED_EVENT)
def process_action_item_completed(message):
    pass


@Edas.on_event(subscribed_to=PUBLISHED_POLICY_EVENT)
def process_policy_published(message):
    pass
