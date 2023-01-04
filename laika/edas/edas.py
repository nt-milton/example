import json
import logging
import threading
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Tuple
from uuid import uuid4

import pika
from django.db import connection
from log_request_id import local

from laika.edas.exceptions import (
    EdaBaseException,
    EdaErrorException,
    EdaWarningException,
)
from laika.utils.exceptions import format_stack_in_one_line
from laika.utils.rabbitmq import PikaClient as Pika
from laika.utils.rabbitmq import SubscriberThread

logger = logging.getLogger(__name__)

EDA_EVENT_SEPARATOR = '::'
EVENT_NAME_ATTRIBUTE = '_event_name'
EDA_MODULE_NAME = 'edas'


class EdaEvent(ABC):
    """
    Base class for the creation of Eda events. This class will keep a registry
    for instances created. The registry will store a set of events per app.

    Parameters:
        app_name: EdaApp - The app the event belongs to.

        event_name: str - The name for the event.

    Methods:
        name(EdaEvent) -> str - return name in the format: {app_name::event_name}
    """

    registry = defaultdict(set)

    def __init__(self, *, app_name: str, event_name: str):
        self.app_name = app_name
        self.event_name = event_name
        EdaEvent.registry[self.app_name].add(self)

    def name(self):
        return f"{self.app_name}{EDA_EVENT_SEPARATOR}{self.event_name}"


class EdaMessage:
    """
    Base class for the creation of Eda messages.

    Parameters:
        event: EdaEvent - The EdaEvent instance the message will receive as input.

    Methods:
        to_json -> str - serializes each EdaMessage instance to a JSON formatted string.
    """

    def __init__(self, *, event: EdaEvent):
        self.message_id = uuid4()
        self.request_id = local.request_id
        self.event = event
        self.created_at = datetime.today()

    @property
    def event(self):
        return self._event

    @event.setter
    def event(self, new_event: EdaEvent):
        try:
            if not isinstance(new_event, EdaEvent):
                raise EdaBaseException(
                    f'Event with value {new_event} should be an instance of EdaEvent'
                )
            self._event = new_event.name()
        except EdaBaseException as e:
            logger.error(
                f'Cannot instantiate EdaMessage with event: {new_event} '
                f'of type {type(new_event)}. {e}'
            )

    def to_json(self):
        try:
            return json.dumps(vars(self), default=str)
        except Exception as e:
            logger.error(
                f'Eda message to submit: {self} cannot be serialized. Error: {e}'
            )

    @classmethod
    def build(cls, *, event: EdaEvent, **kwargs):
        message_instance = cls(event=event)
        for argument_name, argument_value in kwargs.items():
            setattr(message_instance, argument_name, argument_value)
        return message_instance


class EdaRegistry:
    """
    Registry for eda events and listeners.

    Attributes:
        listeners: registry for listeners per event.
        events: registry for events per app
    """

    listeners: defaultdict[str, set] = defaultdict(set)
    events: defaultdict[str, dict] = defaultdict(dict)

    @staticmethod
    def register_events(*, app: str, events: list[str]):
        """
        Method to register eda events.

        Args:
            app (str): app name which the event belongs to.
            events (list[str]): list of events to register.
        """
        for event in events:
            EdaRegistry.events[app][event] = EdaEvent(app_name=app, event_name=event)
        events_per_app = [event for event in EdaRegistry.events[app].keys()]
        logger.info(f'Registered events for {app} app: {events_per_app}')

    @staticmethod
    def register_listeners(edas_modules):
        """
        Method to register eda event listeners.

        Args:
            edas_modules (module): list of edas modules from each
            registered application.
        """
        for module in edas_modules:
            for method in dir(module):
                processor = getattr(module, method, False)
                event_name = getattr(processor, EVENT_NAME_ATTRIBUTE, False)
                if event_name:
                    event_processors_set = EdaRegistry.listeners[event_name]
                    event_processors_set.add(processor)

        event_listeners_summary = {
            event: [
                f'{processor.__module__}.{processor.__name__}'
                for processor in processors
            ]
            for event, processors in EdaRegistry.listeners.items()
        }
        logger.info(f'Event listeners configuration: {event_listeners_summary}')

    @staticmethod
    def event_lookup(event: str):
        try:
            if not event:
                raise EdaWarningException('Not event provided for event lookup')

            for events in EdaRegistry.events.values():
                if not events.get(event):
                    continue
                return events.get(event)

        except EdaWarningException as e:
            logger.warning(f'Error on search of event: {event}. Error: {e}')


class Client(ABC):
    @abstractmethod
    def publish(self, *, message: EdaMessage):
        pass

    @abstractmethod
    def subscribe(self, app_name):
        pass


class PikaClient(Client):
    def __init__(
        self,
        apps_to_subscribe: list[str],
        credentials: Tuple[str, str],
        broker: str,
        port: int,
        vhost: str,
    ):
        self.credentials = credentials
        self.broker = broker
        self.port = port
        self.vhost = vhost
        self.pika_client = None
        self.initialize_pika_client()
        for exchange_name in apps_to_subscribe:
            self.subscribe(exchange_name)

    def connection_data(self):
        return dict(
            credentials=self.credentials,
            broker=self.broker,
            port=self.port,
            vhost=self.vhost,
        )

    def initialize_pika_client(self):
        self.pika_client = Pika(**self.connection_data())
        self.pika_client.connect()

    def initialize_subscriber_thread(self, exchange_name: str):
        consumer = SubscriberThread(
            exchange_name=exchange_name,
            callback=PikaClient.callback,
            **self.connection_data(),
        )
        consumer.daemon = True
        consumer.start()

    @staticmethod
    def callback(
        ch: pika.channel.Channel,
        method: pika.spec.Basic.Deliver,
        properties: pika.spec.BasicProperties,
        body: bytes,
    ):
        message = json.loads(body)
        received_event = message['_event']
        event_name = received_event.split(EDA_EVENT_SEPARATOR)[1]
        event_processors = EdaRegistry.listeners.get(event_name)
        local.request_id = properties.correlation_id
        if event_processors:
            logger.info(
                'Processors: '
                f'{[".".join([p.__module__, p.__name__]) for p in event_processors]}'
                f' processing event: {received_event}.'
            )
            for processor in event_processors:
                PikaClient.start_processing(processor, message, local)

    @staticmethod
    def start_processing(processor, message, local):
        ProcessorThread(processor, message, local).start()

    def publish(self, *, message: EdaMessage):
        try:
            if not self.pika_client or not message:
                raise EdaBaseException('Not client or message provided.')
            app = message.event.split(EDA_EVENT_SEPARATOR)[0]
            serialized_message = message.to_json()
            self.pika_client.publish(
                message_body=serialized_message,
                exchange_name=app,
                request_id=local.request_id,
            )
        except EdaBaseException as e:
            logger.error(e)

    def subscribe(self, app_name):
        self.pika_client.declare_exchange(exchange_name=app_name)
        self.initialize_subscriber_thread(app_name)


class EdaPublisher:
    """
    This class is used to publish messages.
    Params needed to instantiate this class:
        exchanges: list of exchanges to create
        broker: rabbitmq broker.
        credentials: login and password for broker
        port: connection port for broker
        vhost: rabbitmq virtual host.
    Methods:
        connection_data: returns dict with params for pika connection data.
        initialize_pika_client: Initialize pika client used to publish
        initialize_pika_consumers: Initialize subscribers
        initialize_subscriber_thread: Initialize thread for each subscriber
        callback: method to be called after event is received.
    """

    def __init__(self, client: Client):
        self.client = client

    def submit_event(self, *, message: EdaMessage) -> bool:
        try:
            json_message = message.to_json()
            logger.info(f'Trying to submit eda event: {json_message}')
            self.client.publish(message=message)
            logger.info(f'submit successful eda event: {json_message}')
            return True
        except Exception as e:
            logger.warning(f'An error occurred when submitting eda event {e}')
            return False


class ProcessorThread(threading.Thread):
    """
    This class is used to instantiate a thread for
    each event processor.
    Methods:
        this method is called when start() method is called on
        the instance, if you want run the thread as a demon,
        you have to call it <instance>.daemon = True, and then
        call start method <instance>.start()
    """

    def __init__(self, processor, message, thread_local):
        super(ProcessorThread, self).__init__()
        self.processor = processor
        self.message = message
        self.local = thread_local
        self.request_id = self.local.request_id

    def run(self):
        self.local.request_id = self.request_id
        self.local.span_id = uuid.uuid4()
        try:
            self.processor(self.message)
        except EdaWarningException as e:
            logger.warning(
                f'module: {self.processor.__module__} '
                f'Error calling: {self.processor.__name__} '
                f'when processing event: {self.processor._event_name}, '
                f'stack: {format_stack_in_one_line(e)}'
            )
        except (EdaErrorException, EdaBaseException) as e:
            logger.exception(
                f'module: {self.processor.__module__} '
                f'Error calling: {self.processor.__name__} '
                f'when processing event: {self.processor._event_name}, '
                f'stack: {format_stack_in_one_line(e)}'
            )
        except Exception as e:
            logger.exception(
                f'module: {self.processor.__module__} '
                f'Error calling: {self.processor.__name__} '
                f'when processing event: {self.processor._event_name}, '
                f'stack: {format_stack_in_one_line(e)}'
            )
        finally:
            # close connection to DB per thread
            connection.close()
