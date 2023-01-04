from laika.edas.decorators import Edas
from laika.edas.edas import EdaRegistry
from policy.constants import PUBLISHED_POLICY_EVENT

EdaRegistry.register_events(app=__package__, events=[])


@Edas.on_event(subscribed_to=PUBLISHED_POLICY_EVENT)
def process_policy_published(message):
    pass
