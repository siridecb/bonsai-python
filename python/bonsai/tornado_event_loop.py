from __future__ import print_function

import logging

from google.protobuf.text_format import MessageToString, Merge
from tornado import gen
from tornado.ioloop import IOLoop
from tornado import websocket as websockets
from tornado.httpclient import HTTPRequest
from tornado import queues

from bonsai.proto.generator_simulator_api_pb2 import ServerToSimulator
from bonsai.proto.generator_simulator_api_pb2 import SimulatorToServer
from bonsai.drivers import DriverState

log = logging.getLogger(__name__)


class ManualClosedException(Exception):
    pass


class _WrapSocket(object):
    def __init__(self, websocket):
        self.websocket = websocket

    @gen.coroutine
    def send(self, message):
        yield self.websocket.write_message(message, binary=True)

    @gen.coroutine
    def recv(self):
        msg = yield self.websocket.read_message()
        if msg is None:
            raise ManualClosedException()
        raise gen.Return(msg)

    def close(self):
        self.websocket.close()


class _Runner(object):

    def __init__(self, access_key, brain_api_url, driver, recording_file):
        self.access_key = access_key
        self.brain_api_url = brain_api_url
        self.driver = driver
        self.recording_file = recording_file
        if self.recording_file:
            self.recording_queue = queues.Queue()

    @gen.coroutine
    def record_to_file(self):

        if not self.recording_file:
            return

        with open(self.recording_file, 'w') as out:
            while True:
                line = yield self.recording_queue.get()
                if not line:
                    break
                print(line, file=out)

    @gen.coroutine
    def _record(self, send_or_recv, message):
        yield self.recording_queue.put(send_or_recv)
        if message:
            yield self.recording_queue.put(
                MessageToString(message, as_one_line=True))
        else:
            yield self.recording_queue.put('None')

    @gen.coroutine
    def run(self):
        if not self.access_key:
            raise RuntimeError("Access Key was not set.")

        log.info("About to connect to %s", self.brain_api_url)

        req = HTTPRequest(self.brain_api_url, connect_timeout=60,
                          request_timeout=60)
        req.headers['Authorization'] = self.access_key
        f = websockets.WebSocketClientConnection(IOLoop.current(), req)
        websocket = yield f.connect_future
        wrapped = _WrapSocket(websocket)

        input_message = None

        try:
            # The driver starts out in an unregistered... the first "next" will
            # perform the registration and all subsequent "next"s will continue
            # the operation.
            while self.driver.state != DriverState.FINISHED:

                if self.recording_file:
                    yield self._record('RECV', input_message)
                output_message = self.driver.next(input_message)
                if self.recording_file:
                    yield self._record('SEND', output_message)

                # If the driver is FINSIHED, don't bother sending and
                # receiving again before exiting the loop.
                if self.driver.state != DriverState.FINISHED:

                    if not output_message:
                        raise RuntimeError(
                            "Driver did not return a message to send.")

                    output_bytes = output_message.SerializeToString()
                    yield wrapped.send(output_bytes)

                    # Only do this part if the last message wasn't a FINISH
                    input_bytes = yield wrapped.recv()
                    if input_bytes:
                        input_message = ServerToSimulator()
                        input_message.ParseFromString(input_bytes)
                    else:
                        input_message = None

        except (websockets.WebSocketClosedError, ManualClosedException):
            code = websocket.close_code
            reason = websocket.close_reason
            log.error("Connection to '%s' is closed, code='%s', reason='%s'",
                      self.brain_api_url, code, reason)
        finally:
            if self.recording_file:
                yield self.recording_queue.put(None)
            websocket.close()


def run(access_key, brain_api_url, driver, recording_file):

    run_sim, record = create_tasks(access_key,
                                   brain_api_url,
                                   driver,
                                   recording_file)
    IOLoop.current().add_callback(record)
    IOLoop.current().run_sync(run_sim)


def create_tasks(access_key, brain_api_url, driver, recording_file):
    server = _Runner(access_key, brain_api_url, driver, recording_file)
    return server.run, server.record_to_file
