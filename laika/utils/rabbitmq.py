import functools
import logging
import ssl
import threading
from typing import Any, Callable, Optional, Tuple

import pika

from laika.settings import ENVIRONMENT

logger = logging.getLogger(__name__)

SUBSCRIBER = 'subscriber'
PUBLISHER = 'publisher'
HEARTBEAT_TIMEOUT = 600
PREFETCH_COUNT = 5


CallbackType = Callable[
    [pika.channel.Channel, pika.spec.Basic.Deliver, pika.spec.BasicProperties, bytes],
    Any,
]


class PikaClient:
    """
    This class is used to instantiate a client using pika client.
    To initialize the instance is needed:
        broker: rabbitmq broker.
        credentials: login and password for broker.
        port: connection port for broker.
        vhost: rabbitmq virtual host.
        callback: this is the callback to be passed to
            the consumer to execute when event has occurred.
        origin: This client could be the publisher or subscriber.
    Methods:
        _get_parameterss: get params according to environment.
        connect: creates connection to broker and channel.
        declare_exchange: get or create the exchange.
        _reconnect_and_publish: reconnect to broker and publish message.
        _publish: publish message to exchange.
        declare_queue_and_bind: declare queue and bind it to exchange
        consume: bind queue to exchange, link callback to queue and open
            consuming loop.
        ack_message: acknoledge message when received.
        _on_message_callback: method to be called when message is received.
    """

    def __init__(
        self,
        credentials: Tuple[str, str],
        broker: str,
        port: int,
        vhost: str,
        callback: Optional[CallbackType] = None,
        origin: Optional[str] = PUBLISHER,
    ):
        self.credentials = credentials
        self.broker = broker
        self.port = port
        self.vhost = vhost
        self.callback = callback
        self.connection = None
        self.channel = None

        logger.info(f'{origin} client correctly initialized.')

    def _get_parameters(self):
        logger.info(f'Getting rabbitmq parameters for environment {ENVIRONMENT}')
        if ENVIRONMENT == 'local':
            plain_credentials = pika.PlainCredentials(*self.credentials)
            parameters = pika.ConnectionParameters(
                self.broker,
                self.port,
                self.vhost,
                plain_credentials,
                heartbeat=HEARTBEAT_TIMEOUT,
            )
        else:
            url = (
                f'amqps://{self.credentials[0]}:'
                f'{self.credentials[1]}'
                f'@{self.broker}:'
                f'{self.port}?heartbeat={HEARTBEAT_TIMEOUT}'
            )
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            ssl_context.set_ciphers('ECDHE+AESGCM:!ECDSA')
            parameters = pika.URLParameters(url)
            parameters.ssl_options = pika.SSLOptions(context=ssl_context)
        return parameters

    def connect(self):
        try:
            self.connection = pika.BlockingConnection(self._get_parameters())
        except Exception as e:
            logger.error(f'Connection cannot be initialized. Error: {e}')

        try:
            self.channel = self.connection.channel()
            self.channel.confirm_delivery()
            self.channel.basic_qos(prefetch_count=PREFETCH_COUNT)
        except Exception as e:
            logger.error(
                f'Channel for Connection {self.connection} could not be created'
                f'Error: {e}'
            )

    def declare_exchange(self, exchange_name=''):
        logger.info(f'Creating or getting exchange: {exchange_name}')
        try:
            self.channel.exchange_declare(
                exchange=exchange_name, exchange_type='fanout'
            )
        except Exception as e:
            logger.error(f'Could not create exchange {exchange_name}. Error: {e}')

    def _publish(self, exchange_name, routing_key, message_body, request_id):
        self.channel.basic_publish(
            exchange=exchange_name,
            routing_key=routing_key,
            body=message_body,
            properties=pika.BasicProperties(
                delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE,
                correlation_id=request_id,
            ),
        )

    def _reconnect_and_publish(
        self, exchange_name, routing_key, message_body, request_id
    ):
        self.connect()
        logger.info(f'Reconnecting to exchange {exchange_name}')
        self.publish(
            message_body=message_body,
            exchange_name=exchange_name,
            routing_key=routing_key,
            request_id=request_id,
        )

    def publish(self, *, message_body, exchange_name, routing_key='', request_id):
        try:
            self._publish(exchange_name, routing_key, message_body, request_id)
            logger.info(f'sending message {message_body} to {exchange_name}')
        except pika.exceptions.UnroutableError as e:
            logger.error(
                f'Message {message_body} to exchange {exchange_name} could not '
                f'be sent. Error {e}'
            )
        except pika.exceptions.ConnectionClosed as e:
            logger.error(
                'Connection is closed. trying to reconnect to publish to '
                f'exchange {exchange_name}. Error {e}'
            )
            self._reconnect_and_publish(
                exchange_name, routing_key, message_body, request_id
            )
        except pika.exceptions.StreamLostError as e:
            logger.error(
                'Stream is lost. trying to reconnect to publish to '
                f'exchange {exchange_name}. Error {e}'
            )
            self._reconnect_and_publish(
                exchange_name, routing_key, message_body, request_id
            )

    def declare_queue_and_bind(self, *, exchange_name, queue_name):
        logger.info(f'Declaring queue {queue_name}, and bind it to {exchange_name}')
        try:
            self.channel.queue_declare(queue=queue_name, durable=True)
            self.channel.queue_bind(exchange=exchange_name, queue=queue_name)
        except Exception as e:
            logger.error(
                f'Queue {queue_name} could not have been created or '
                f'bound for exchange {exchange_name}. Error: {e}'
            )

    def consume(self, *, queue_name):
        logger.info(f'Starting basic consume on queue {queue_name}')
        try:
            self.channel.basic_consume(
                queue=queue_name, on_message_callback=self._on_message_callback
            )
            self.channel.start_consuming()
        except Exception as e:
            logger.error(
                f'Channel could not start consuming. Error: {e} '
                f'callback = {self.callback}, channel = {self.channel}'
            )

    def _ack_message(self, channel: pika.channel.Channel, delivery_tag):
        if channel.is_open:
            channel.basic_ack(delivery_tag)

    def _on_message_callback(
        self,
        ch: pika.channel.Channel,
        method: pika.spec.Basic.Deliver,
        properties: pika.spec.BasicProperties,
        body: bytes,
    ):
        if self.connection and self.callback:
            self.callback(ch, method, properties, body)
            # Suggested method by rabbitmq to schedule the basic ack
            cb = functools.partial(self._ack_message, ch, method.delivery_tag)
            self.connection.add_callback_threadsafe(cb)


class SubscriberThread(threading.Thread):
    """
    This class instantiate a thread on which a pika instance
    will run. This pika instance will be for a subscriber and
    method consume will be called in order to start listening
    for events.
    To initialize the instance is needed:
    exchange_name: the name of the exchange on which the subscriber
    will be listening to.
    callback: this is the method to be passed to
        the consumer to execute when event has occurred.
    Methods:
        run: this method is called when start() method is called on
            the instance, if you want run the thread as a demon,
            you have to call it <instance>.daemon = True, and then
            call start method <instance>.start()
    """

    def __init__(self, exchange_name: str, callback: CallbackType, **connection_data):
        super(SubscriberThread, self).__init__()
        self.exchange_name = exchange_name
        self.callback = callback
        self.connection_data = connection_data

    def run(self):
        consumer = PikaClient(
            **self.connection_data,
            callback=self.callback,
            origin=SUBSCRIBER,
        )
        consumer.connect()
        consumer.declare_queue_and_bind(
            exchange_name=self.exchange_name, queue_name=self.exchange_name
        )
        consumer.consume(queue_name=self.exchange_name)
