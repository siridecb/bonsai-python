
class BrainServerProtocol(object):
    """
    Protocol for messages sent and received between a generator or simulator
    and a BRAIN server. "generate" methods fill in a SimulatorToServer message,
    while "handle" methods are expected to be passed in a member of a
    ServerToSimulator message pertinent to it.
    """
    def generate_register_message(self, message):
        """
        Sets the passed SimulatorToServer message to be a registration message.
        :param message: The message to fill.
        :type message: SimulatoToServer message
        """
        raise NotImplementedError()

    def handle_register_acknowledgement(self, message):
        """
        Processes the acknowledgement received from a register message.
        :param message: The acknowledgement message.
        :type message AcknowledgeRegisterData data
        :exception: RuntimeError for any errors
        """
        raise NotImplementedError()

    def handle_set_properties_message(self, message):
        """
        Given a protobuf message, parse it for properties and use
        appropriately. The schema for the properties will have been sent in
        the ack of a register message (see BrainServerRegistrationProtocol).
        :param message: The message from the server.
        :type SetPropertiesData protobuf object
        """
        raise NotImplementedError()


class BrainServerSimulatorProtocol(object):
    """
    Protocol specific to simulators for handling simulator specific messages
    such as predictions, states, and simulator commands.
    """
    def generate_state_message(self, message):
        """
        Captures the state from a simulator and returns that state encapsulated
        in a Protobuf message.
        :param message: The message to fill in.
        :type message: SimulatorToServer message
        """
        raise NotImplementedError()

    def handle_start_message(self):
        """
        Called when the BRAIN server sends a start message to the simulator.
        """
        raise NotImplementedError()

    def handle_stop_message(self):
        """
        Called when the BRAIN server sends a stop message to the simulator.
        """
        raise NotImplementedError()

    def handle_prediction_message(self, message):
        """
        Called when the BRAIN server sends a prediction to the simulator.
        :param message: The message containing the prediction.
        :type PredictionData message.
        """
        raise NotImplementedError()

    def handle_finish_message(self):
        """
        Called whe the BRAIN server sends a finished message to the simulator.
        """
        raise NotImplementedError()

    def handle_reset_message(self):
        """
        Called when the BRAIN server sends a reset message to the simulator.
        """
        raise NotImplementedError()

    def generate_ready_message(self, message):
        """
        Called to generate a ready message to the BRAIN server.
        :param message: The message to fill in.
        :type message: SimulatorToServer message
        """
        raise NotImplementedError()

    def advance(self):
        """
        Called to advance the simulator.
        """
        raise NotImplementedError()

    def generate_state_from_prediction(self, message):
        """
        Called to generate a state message from previously handled predictions.
        :param message: The message to fill in.
        :type message: SimulatorToServer message
        """
        raise NotImplementedError()


class BrainServerGeneratorProtocol(object):
    """
    Protocol specific to generators for handling gneerator specific messages
    around advancing and obtaining data.
    """

    def generate_next_data(self):
        """
        Return the next piece of data from the generator.
        :return: Message containing the next piece of data from the generator
        :rtype: SimulatorToServer protobuf message
        """
        raise NotImplementedError()
