"""
These are a collection of utilities used in unit testing Simulator and
Generator drivers.
"""

from collections import namedtuple

from google.protobuf.text_format import Merge

from bonsai.proto.generator_simulator_api_pb2 import ServerToSimulator
from bonsai.proto.generator_simulator_api_pb2 import SimulatorToServer


SampleMessage = namedtuple('SampleMessage', [
    'direction',
    'message_as_text',
    'message'
])


def load_test_message_stream(path):
    """
    Loads a message stream. The message stream is a simple text file of
    protobuf messages sent and received during the course of a training or
    prediction run.

    The file is very simply formatted as a pairs of lines for each message:
    Line N  : SEND|RECV
    Line N+1: ServerToSimulator or SimulutorToServer protobuf object serialized
              to text form with google.protobuf.text_format.MessageToString(),
              or None indicating an empty message.

    This output file can be easily re-created with any of the gym sample
    simulators by simply adding a "--messages-out <PATH>" parameter to the
    command line.

    :param path: Path to test file to load.
    :type path: string
    :return: Array of SampleMessage instances representing the back-and-forth
             communications between the simulator and its BRAIN.
    """
    with open(path, 'r') as infile:

        line_number = 0
        direction = None
        message_as_text = None
        message = None
        messages = []
        for line in infile:
            line_number += 1
            line = line.strip()
            if line_number % 2 == 1:
                direction = line
            else:
                message_as_text = line
                if message_as_text == 'None':
                    message = None
                elif direction == 'RECV':
                    message = ServerToSimulator()
                elif direction == 'SEND':
                    message = SimulatorToServer()
                else:
                    raise RuntimeError('Error loading file '
                                       'on line {}'.format(line_number))
                if message:
                    Merge(message_as_text, message)
                tst_msg = SampleMessage(
                    direction=direction,
                    message_as_text=message_as_text,
                    message=message)
                messages.append(tst_msg)

    return messages
