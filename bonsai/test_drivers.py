import unittest
import os

from google.protobuf.text_format import MessageToString

from bonsai.proto.generator_simulator_api_pb2 import *
from bonsai.drivers import SimulatorDriverForTraining
from bonsai.drivers import SimulatorDriverForPrediction
from bonsai.protocols import BrainServerSimulatorProtocol, BrainServerProtocol
from bonsai.common.test_utils import load_test_message_stream


class _BadMessageType(RuntimeError):
    """Raised whenever an unexpected message is received."""
    def __init__(self, expected, got):
        super(_BadMessageType, self).__init__(
            'Expected message type {} bot got {}'.format(
                expected.__name__,
                MessageToString(got)
            )
        )


def _verify(expect, msg):
    if not (msg and isinstance(msg, expect)):
        raise _BadMessageType(expect, msg)


class _MockSimulatorConnectionForTraining(BrainServerProtocol,
                                          BrainServerSimulatorProtocol):
    """Mock connection that emulates the connection to a simulator"""
    def __init__(self):
        self.registers = 0
        self.set_properties = 0
        self.starts = 0
        self.stops = 0
        self.predictions = 0
        self.finishes = 0
        self.resets = 0
        self.advances = 0

    def generate_register_message(self, msg):
        msg.message_type = SimulatorToServer.REGISTER

    def handle_register_acknowledgement(self, message):
        _verify(AcknowledgeRegisterData, message)
        self.registers += 1

    def handle_set_properties_message(self, message):
        _verify(SetPropertiesData, message)
        self.set_properties += 1

    def generate_state_message(self, msg):
        msg.message_type = SimulatorToServer.STATE
        msg.state_data.add()

    def handle_start_message(self):
        self.starts += 1

    def handle_stop_message(self):
        self.stops += 1

    def handle_prediction_message(self, msg):
        _verify(PredictionData, msg)
        self.predictions += 1

    def handle_finish_message(self):
        self.finishes += 1

    def handle_reset_message(self):
        self.resets += 1

    def generate_ready_message(self, msg):
        msg.message_type = SimulatorToServer.READY

    def advance(self):
        self.advances += 1


class SimulatorDriverTests(unittest.TestCase):
    """
    Unit tests for the SimulatorDriverForTraining module.
    """
    blackjack_successful_messages = None

    @classmethod
    def setUpClass(cls):
        cls.blackjack_successful_messages = load_test_message_stream(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         os.pardir,
                         os.pardir,
                         'test_resources',
                         'blackjack_successful_run.txt'))

    def _run_training(self, messages):
        connection = _MockSimulatorConnectionForTraining()
        driver = SimulatorDriverForTraining(connection=connection,
                                            simulator_connection=connection)
        length = len(messages)
        for i in range(0, length, 2):
            recv = messages[i]
            send = messages[i+1]
            self.assertEqual('RECV', recv.direction)
            self.assertEqual('SEND', send.direction)
            try:
                output = driver.next(recv.message)
            except Exception as e:
                print('Error on lines ', i+1, ' and ', i+2, file=sys.stderr)
                raise e
            if output:
                self.assertEqual(send.message.message_type,
                                 output.message_type)
            else:
                self.assertIsNone(send.message)

    def test_blackjack_successful_run(self):
        self._run_training(SimulatorDriverTests.blackjack_successful_messages)


if __name__ == '__main__':
    unittest.main()
