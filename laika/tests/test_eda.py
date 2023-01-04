# import logging
#
# import pytest
#
# from laika.edas import initialize_pika_client, initialize_pika_consumers
# from laika.eda_initializer import produce_event, EdaPublisher
# from policy.eda_dispatchers import PolicyEvents
# from policy.models import Policy
#
# logger = logging.getLogger(__name__)
#
#
# def callback(message):
#     logger.Info('test callback')
#
#
# @pytest.fixture(name="_events")
# def fixture_events():
#     return [('policy.PolicyPublishedEvent', callback)]
#
#
# @pytest.fixture(name="_pika_client")
# def fixture_pika_client():
#     return initialize_pika_client()
#
#
# @pytest.fixture(name="_pika_consumers")
# def fixture_pika_consumers(_pika_client):
#     initialize_pika_consumers(_pika_client)
#
#
# def test_eda_producer_no_exceptions(_pika_client):
#     message = dict(policy_id='1', user_id='1')
#
#     try:
#         produce_event(
#             message=message,
#             event=PolicyEvents.PUBLISH_POLICY,
#             client=_pika_client
#         )
#     except Exception:
#         pytest.fail()
#
#
# def test_eda_producer_logger_info(caplog, _pika_client):
#     message = dict(policy_id='1', user_id='1')
#     caplog.set_level(logging.INFO)
#     log_message = (
#         "sending message {\"policy_id\": \"1\", \"user_id\": \"1\","
#         " \"event\": \"policy.PublishPolicy\"} to policy\n"
#     )
#
#     produce_event(
#         message=message, event=PolicyEvents.PUBLISH_POLICY, client=_pika_client
#     )
#     assert log_message in caplog.text
#
#     # for the consumer test that the callback response is
#     # correct using the caplog
#     # def test_eda_consumers(caplog, _pika_client, _pika_consumers):
#     #     message = dict(
#     #         policy_id='1',
#     #         user_id='1'
#     #     )
#     #     caplog.set_level(logging.INFO)
#     #
#     #     produce_event(
#     #         message=message,
#     #         event=PolicyEvent.POLICY_PUBLISHED,
#     #         client=_pika_client
#     #     )
#     #
#     #     log_message = 'test callback'
#
#     # assert log_message in caplog.text
#
# def test_eda_consumer_action_item(caplog, _pika_client):
#     policy, _ = Policy.objects.get_or_create()
#     message = dict(policy_id=policy.id, user_id='1')
#     caplog.set_level(logging.INFO)
#     log_message = (
#         "sending message {\"policy_id\": \"1\", \"user_id\": \"1\","
#         " \"event\": \"policy.PublishPolicy\"} to policy\n"
#     )
#
#     EdaPublisher.submit_event(
#         message=message, event=PolicyEvents.PUBLISH_POLICY, client=_pika_client
#     )
#
#     assert log_message in caplog.text
