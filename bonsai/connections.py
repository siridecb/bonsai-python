import logging
from pprint import pformat

from google.protobuf.text_format import MessageToString

from bonsai.protocols import BrainServerProtocol, BrainServerSimulatorProtocol
from bonsai.protocols import BrainServerGeneratorProtocol
from bonsai.proto.generator_simulator_api_pb2 import SimulatorToServer
from bonsai.common.message_builder import reconstitute
from bonsai.common.state_to_proto import convert_state_to_proto


log = logging.getLogger(__name__)


class SimulatorConnection(BrainServerProtocol, BrainServerSimulatorProtocol):
    """
    This is the "glue" class that connects a simulator conforming to Bonsai's
    `Simulator` interface to the communication protocols used to pass messages
    to and from the BRAIN backend.
    """

    def __init__(self, **kwargs):
        """
        Initializes this brain server connection.
        :param kwargs: Arguments for initializing this protocol
        """

        # Protobuf class used for properties. This should be returned from the
        # ack of a registration.
        self._properties_schema = None

        # Protobuf class used for output. This should be returned from the
        # ack of a registration.
        self._output_schema = None

        # Protobuf class for predictions. This should be returned from the
        # ack of a registration.
        self._prediction_schema = None

        # The name of the simulator.
        self._simulator_name = kwargs.pop('simulator_name')

        # An instance of the simulator.
        self._simulator = kwargs.pop('simulator')

        # Whether or not to log state messages. If true, they'll be put on
        # a DEBUG stream.
        self._log_state_messages = kwargs.pop('log_state_messages', False)

        # The current reward name
        self._current_reward_name = None

        # the server-allocated ID for the current simulator session
        self._simulator_id = None

    def generate_register_message(self, message):
        message.message_type = SimulatorToServer.REGISTER
        message.register_data.simulator_name = self._simulator_name

    def handle_register_acknowledgement(self, message):
        log.debug('Processing acknowledgement %s', MessageToString(message))

        props_schema = message.properties_schema
        out_schema = message.output_schema
        pred_schema = message.prediction_schema
        self._properties_schema = reconstitute(props_schema)
        self._output_schema = reconstitute(out_schema)
        self._prediction_schema = reconstitute(pred_schema)
        self._simulator_id = message.sim_id

    def handle_set_properties_message(self, message):

        log.debug('Received set properties data %s',
                  MessageToString(message))
        property_data = message
        # Parse request_data into a properties message.
        properties_message = self._properties_schema()
        properties_message.ParseFromString(
            property_data.dynamic_properties)

        # Create a dictionary of the property names to values.
        properties = {}
        for field in properties_message.DESCRIPTOR.fields:
            properties[field.name] = getattr(properties_message,
                                             field.name)

        # Call set_properties on the simulator.
        self._simulator.set_properties(**properties)

        # Set current reward name.
        self._current_reward_name = property_data.reward_name

        # Set the predictions schema
        self._prediction_schema = reconstitute(property_data.prediction_schema)

    def generate_state_message(self, message):

        message.message_type = SimulatorToServer.STATE
        message.sim_id = self._simulator_id
        state = self._simulator.get_state()

        if self._current_reward_name:
            reward = getattr(self._simulator, self._current_reward_name)()
        else:
            reward = 0.0

        log.debug('generate_state_message => state = %s', pformat(state))
        terminal = state.is_terminal
        state_message = self._output_schema()
        convert_state_to_proto(state_message, state.state)

        current_state_data = message.state_data.add()
        current_state_data.state = state_message.SerializeToString()
        current_state_data.reward = reward
        current_state_data.terminal = terminal

        # add action taken
        last_action = self._simulator.get_last_action()
        if last_action is not None:
            actions_msg = self._prediction_schema()
            convert_state_to_proto(actions_msg, last_action)
            current_state_data.action_taken = actions_msg.SerializeToString()
        if self._log_state_messages:
            log.debug('Generated simulator state %s',
                      MessageToString(message))

    def handle_start_message(self):
        self._simulator.start()

    def handle_stop_message(self):
        self._simulator.stop()

    def handle_prediction_message(self, message):
        log.debug('Received prediction message %s',
                  MessageToString(message))

        prediction_data = message.dynamic_prediction
        # Parse request_data into a properties message.
        predictions_msg = self._prediction_schema()
        predictions_msg.ParseFromString(prediction_data)

        # Create a dictionary of the property names to values.
        predictions = {}
        for field in predictions_msg.DESCRIPTOR.fields:
            predictions[field.name] = getattr(predictions_msg, field.name)

        self._simulator.notify_prediction_received(predictions)

    def handle_finish_message(self):
        pass

    def handle_reset_message(self):
        self._simulator.reset()

    def advance(self):
        self._simulator.advance(self._simulator.get_last_action())

    def generate_ready_message(self, message):
        message.message_type = SimulatorToServer.READY
        message.sim_id = self._simulator_id


class GeneratorConnection(BrainServerProtocol, BrainServerGeneratorProtocol):
    """
    This is the "glue" class that connects a generator conforming to Bonsai's
    `Generator` interface to the communication protocols used to pass messages
    to and from the BRAIN backend.
    """
    # TODO: Impement me!
    def __init__(self, **kwargs):
        self._generator = kwargs.pop('generator')
        self._generator_name = kwargs.pop('generator_name')
