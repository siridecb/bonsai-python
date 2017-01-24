import asyncio
import logging

import websockets
from datetime import datetime

from bonsai.drivers import DriverState
from bonsai.proto.generator_simulator_api_pb2 import ServerToSimulator

log = logging.getLogger(__name__)


class _Runner(object):
    def __init__(self, access_key, brain_api_url, driver, recording_file):
        self.access_key = access_key
        self.brain_api_url = brain_api_url
        self.driver = driver
        self.recording_file = recording_file
        if self.recording_file:
            self.recording_queue = asyncio.queues.Queue()

    async def record_to_file(self):
        if not self.recording_file:
            return

        with open(self.recording_file, 'w') as out:
            while True:
                line = await self.recording_queue.get()
                if not line:
                    break
                out.write(line)

    async def _record(self, send_or_recv, message):
        await self.recording_queue.put(send_or_recv)
        if message:
            await self.recording_queue.put(
                message.MessageToString(as_one_line=True))
        else:
            await self.recording_queue.put('None')

    async def run(self):
        if not self.access_key:
            raise RuntimeError("Access Key was not set.")

        log.info("About to connect to %s", self.brain_api_url)
        async with websockets.connect(uri=self.brain_api_url,
                                      extra_headers={
                                          'Authorization': self.access_key
                                      }) as websocket:
            log.debug('Connection to %s established.', self.brain_api_url)
            input_message = None
            last_check = datetime.utcnow()
            try:
                log.debug('Starting execution loop...')
                # The driver starts out in an unregistered... the first "next"
                # will perform the registration and all subsequent "next"s will
                # continue the operation.
                while self.driver.state != DriverState.FINISHED:
                    now = datetime.utcnow()
                    if (now - last_check).total_seconds() > 10:
                        last_check = now
                        log.debug('Driver for %s currently in state %s...',
                                  self.brain_api_url, str(self.driver.state))

                    if self.recording_file:
                        await self._record('RECV', input_message)

                    # This is where the state-machine magic happens
                    output_message = self.driver.next(input_message)

                    if self.recording_file:
                        await self._record('SEND', output_message)

                    if output_message:
                        output_bytes = output_message.SerializeToString()
                        await websocket.send(output_bytes)

                    if self.driver.state != DriverState.FINISHED:
                        # Only do this part if the driver isn't in a FINISHED
                        # state.
                        input_bytes = await websocket.recv()
                        if input_bytes:
                            input_message = ServerToSimulator()
                            input_message.ParseFromString(input_bytes)
                        else:
                            input_message = None

            except websockets.exceptions.ConnectionClosed as e:
                log.error(
                    "Connection to '%s' is closed, code='%s', reason='%s'",
                    self.brain_api_url, e.code, e.reason)
            finally:
                log.debug('Execution loop complete for %s!',
                          self.brain_api_url)
                if self.recording_file:
                    await self.recording_queue.put(None)


def run(access_key, brain_api_url, driver, recording_file):
    loop = asyncio.get_event_loop()
    run_sim, record = create_tasks(access_key,
                                   brain_api_url,
                                   driver,
                                   recording_file)
    loop.run_until_complete(asyncio.gather([run_sim, record], loop))


def create_tasks(access_key, brain_api_url, driver, recording_file):
    server = _Runner(access_key, brain_api_url, driver, recording_file)

    return (asyncio.ensure_future(server.run()),
            asyncio.ensure_future(server.record_to_file()))
