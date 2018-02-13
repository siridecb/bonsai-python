# for python2.7 compatibility and the use of print(file=)
from __future__ import print_function

import logging
import os

from concurrent.futures import ThreadPoolExecutor

from google.protobuf.text_format import MessageToString

from six.moves.queue import Queue
import websocket

from bonsai.proto.generator_simulator_api_pb2 import ServerToSimulator
from bonsai.drivers import DriverState

log = logging.getLogger(__name__)


class _Runner(object):

    def __init__(self, access_key, brain_api_url, driver, recording_file):
        self.access_key = access_key
        self.brain_api_url = brain_api_url
        self.driver = driver
        self.recording_file = recording_file
        if self.recording_file:
            self.recording_queue = Queue()

    def record_to_file(self):
        # A loop to record queued information to a file.
        # This needs to run in a second thread.
        if not self.recording_file:
            return

        with open(self.recording_file, 'w') as out:
            while True:
                line = self.recording_queue.get()
                if not line:
                    break
                print(line, file=out)

    def _maybe_record(self, send_or_recv, message):
        if self.recording_file:
            self._record(send_or_recv, message)

    def _record(self, send_or_recv, message):
        self.recording_queue.put(send_or_recv)
        if message:
            body = MessageToString(message, as_one_line=True)
        else:
            body = 'None'
        self.recording_queue.put(body)

    def _get_proxy(self, is_secure):
        if is_secure:
            server = os.getenv('https_proxy')
        else:
            server = os.getenv('http_proxy')

        if server is None:
            server = os.getenv('all_proxy')

        proxy = {}
        if server:
            host_port = server.rsplit(':', 1)
            proxy['http_proxy_host'] = host_port[0]
            if len(host_port) > 1:
                proxy['http_proxy_port'] = host_port[1]

        return proxy

    def _on_message(self, ws, message):
        log.debug("ON_MESSAGE: %s", message)

        input_bytes = message
        if input_bytes:
            input_message = ServerToSimulator()
            input_message.ParseFromString(input_bytes)
        else:
            input_message = None

        try:
            self._handle_message(ws, input_message)
        except Exception as e:
            self._on_error(ws, e)
            ws.close()

    def _on_error(self, ws, error):
        if type(error) == KeyboardInterrupt:
            log.debug("Handling Ctrl+c ...")
            return
        log.debug("Error received for '%s': '%s'", self.brain_api_url, error)

    @staticmethod
    def on_close(ws, code, reason):
        log.debug("on_close()")
        if code is None or code == 1000:
            return

        log.debug("(code=%s) %s", code, reason)

    def _on_open(self, ws):
        log.debug("_on_open()")
        self._handle_message(ws, None)

    def _handle_message(self, ws, message):
        self._maybe_record('RECV', message)
        output_message = self.driver.next(message)
        self._maybe_record('SEND', output_message)

        # If the driver is FINSIHED, don't bother sending and
        # receiving again before exiting the loop.
        if self.driver.state == DriverState.FINISHED:
            if self.recording_file:
                self.recording_queue.put(None)
            ws.close()
            return

        if not output_message:
            raise RuntimeError(
                "Driver did not return a message to send.")

        output_bytes = output_message.SerializeToString()
        ws.send(output_bytes, opcode=websocket.ABNF.OPCODE_BINARY)

    def run(self):
        if not self.access_key:
            raise RuntimeError("Access Key was not set.")

        log.info("About to connect to %s", self.brain_api_url)

        ws = websocket.WebSocketApp(
            self.brain_api_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=_Runner.on_close,
            header=['Authorization: {}'.format(self.access_key)]
        )

        ws.on_open = self._on_open

        is_secure = self.brain_api_url.startswith('wss')
        proxy = self._get_proxy(is_secure)
        if proxy:
            log.info('Connecting via proxy: %s', proxy)

        try:
            ws.run_forever(**proxy)
        except KeyboardInterrupt as e:
            log.debug("Handling user Ctrl+C")
        finally:
            # insert None to make our recording method exit
            self._maybe_record(None, None)


def run(access_key, brain_api_url, driver, recording_file):
    """ run the simulator (synchronously) until it disconnects. """
    run_sim, record = create_tasks(access_key,
                                   brain_api_url,
                                   driver,
                                   recording_file)

    # A thread for recording traffic
    tpe = ThreadPoolExecutor(max_workers=1)
    tpe.submit(record)

    run_sim()
    tpe.shutdown(wait=False)


def create_tasks(access_key, brain_api_url, driver, recording_file):
    """ Create the task runner object """
    server = _Runner(access_key, brain_api_url, driver, recording_file)
    return server.run, server.record_to_file
