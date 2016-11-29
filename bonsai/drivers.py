import logging

from google.protobuf.text_format import MessageToString

from bonsai.proto.generator_simulator_api_pb2 import ServerToSimulator
from bonsai.proto.generator_simulator_api_pb2 import SimulatorToServer


log = logging.getLogger(__name__)


class DriverState(object):
    UNREGISTERED = 0
    REGISTERING = 10
    REGISTERED = 20
    ACTIVE = 30
    FINISHED = 40


class EmptyMessageError(RuntimeError):
    """
    Thrown when receiving an empty message when it shouldn't have been empty.
    """
    def __init__(self, message_name):
        super(EmptyMessageError, self).__init__(
            'Expected a {} message but received nothing... '
            '(sigh) absolutely nothing...'.format(message_name)
        )


class MalformedMessageError(RuntimeError):
    """Thrown when receiving a malformed message (i.e. missing a field)"""
    def __init__(self, missing_field, message):
        super(MalformedMessageError, self).__init__(
            'Could not locate {} in message {} - got {}'.format(
                missing_field,
                type(message).__name__,
                MessageToString(message, as_one_line=True)
            )
        )


class UnexpectedMessageError(RuntimeError):
    """Thrown when an unexpected or unhandled message is received"""
    def __init__(self, expected, message):
        super(UnexpectedMessageError, self).__init__(
            'Expected {} but got {}'.format(
                expected,
                MessageToString(message, as_one_line=True)
            )
        )


class Driver(object):
    """
    A state-machine-esque entity that handles the logic of coordinating
    messages between a generator or simulator and the BRAIN backend. This will
    be the object that an event loop asynchronous library "drives".
    """

    def __init__(self, **kwargs):
        self._state = DriverState.UNREGISTERED
        self._base_protocol = kwargs.pop('connection')

    def next(self, message):
        # type: (ServerToSimulator) -> SimulatorToServer
        """
        This is the "driving" function, in that given an input that comes from
        a source (likely a websocket), do something with it depending on the
        state of the driver, the produce an output to be sent back to the
        server.
        :param message: Message from the server to be processed. This may be
                        None, but how that is handled depends on the state and
                        implementation of the derived driver.
        :type message: ServerToSimulator protobuf message.
        :return: A message to be sent back to the server. This may be None,
                 indicating that no message needs to be sent back.
        :rtype: SimulatorToServer protobuf message.
        """
        raise NotImplementedError()

    @property
    def state(self):
        """
        Returns the state of the driver.
        :return: State of the driver.
        :rtype: Member of the DriverState enumeration.
        """
        return self._state


class SimulatorDriverForTraining(Driver):
    """
    Driver used for training with a simulator.
    """

    def __init__(self, **kwargs):
        super(SimulatorDriverForTraining, self).__init__(**kwargs)
        self._simulator_protocol = kwargs.pop('simulator_connection')
        self._state_funcs = {
            DriverState.UNREGISTERED: self._send_register_message,
            DriverState.REGISTERING: self._handle_registration_acknowledgement,
            DriverState.ACTIVE: self._handle_runtime_message,
            DriverState.FINISHED: self._do_nothing
        }
        self._active_funcs = {
            ServerToSimulator.SET_PROPERTIES:
                self._handle_set_properties_message,
            ServerToSimulator.START: self._handle_start_message,
            ServerToSimulator.STOP: self._handle_stop_message,
            ServerToSimulator.PREDICTION: self._handle_prediction_message,
            ServerToSimulator.RESET: self._handle_reset_message,
            ServerToSimulator.FINISHED: self._handle_finished_message
        }

    def _do_nothing(self, _):
        return None

    def _send_register_message(self, _):
        """
        In the beginning, send a register message.
        :return: A registration message
        :rtype: SimulatorToServer
        """
        self._state = DriverState.REGISTERING
        message = SimulatorToServer()
        self._base_protocol.generate_register_message(message)
        return message

    def _handle_registration_acknowledgement(self, message):
        """
        The server sends back an acknowledgement. Process that acknowledgement
        and send back a ready message to the server.
        :param message: An acknowledge register message.
        :type message: ServerToSimulator protobuf class
        :return: A ready message
        :rtype: SimulatorToServer protobuf message
        """

        if not message:
            raise EmptyMessageError('ServerToSimulator with '
                                    'AcknowledgeRegisterData')
        if not message.HasField('acknowledge_register_data'):
            raise MalformedMessageError('acknowledge_register_data',
                                        message)

        self._state = DriverState.ACTIVE
        self._base_protocol.handle_register_acknowledgement(
            message.acknowledge_register_data)
        reply = SimulatorToServer()
        self._simulator_protocol.generate_ready_message(reply)

        if reply.message_type != SimulatorToServer.READY:
            raise UnexpectedMessageError('READY SimulatorToServer message',
                                         reply)

        return reply

    def _handle_runtime_message(self, message):
        """
        Once the simulator has signalled that it is ready to run, the server
        will issue it active messages, like set properties, start, stop, reset,
        or finish. This is a catch-all for all those active messages, which are
        routed to their own handlers.
        :param message: Message containing the active command.
        :type message: ServerToSimulator protobuf message
        :return: Potentially, a message to send back to the server from the
                 simulator. If there isn't anything to send back, None is
                 returned.
        :rtype: SimulatorToServer protobuf message or None.
        """
        if not message:
            raise EmptyMessageError('ServerToSimulator')
        try:
            active_func = self._active_funcs[message.message_type]
        except KeyError:
            error = 'one of {}'.format(str(self._active_funcs.keys()))
            raise UnexpectedMessageError(error, message)

        return active_func(message)

    def _handle_set_properties_message(self, message):
        """
        The server sent a properties message. Process it, and return back a
        "ready" message.
        :param message: The set properties message.
        :type message: ServerToSimulator protobuf message.
        :return: A ready message.
        :rtype: SimulatorToServer protobuf message.
        """
        if not message.HasField('set_properties_data'):
            raise MalformedMessageError('set_properties_data', message)

        self._base_protocol.handle_set_properties_message(
            message.set_properties_data)
        reply = SimulatorToServer()
        self._simulator_protocol.generate_ready_message(reply)

        if reply.message_type != SimulatorToServer.READY:
            raise UnexpectedMessageError('READY SimulatorToServer message',
                                         reply)

        return reply

    def _handle_start_message(self, _):
        """
        The server sent a Start message. Send back a message containing the
        current state of the simulator.
        :return: States from the simulator
        :rtype: SimulatorToServer message
        """
        self._simulator_protocol.handle_start_message()
        reply = SimulatorToServer()
        self._simulator_protocol.generate_state_message(reply)

        if reply.message_type != SimulatorToServer.STATE:
            raise UnexpectedMessageError('STATE SimulatorToServer message',
                                         reply)

        if len(reply.state_data) == 0:
            raise MalformedMessageError('state_data', reply)

        return reply

    def _handle_stop_message(self, _):
        """
        The server sent a stop message. Handle it and send back a ready
        message.
        :return: A ready message
        :rtype: SimulatorToServer message
        """
        self._simulator_protocol.handle_stop_message()

        reply = SimulatorToServer()
        self._simulator_protocol.generate_ready_message(reply)

        if reply.message_type != SimulatorToServer.READY:
            raise UnexpectedMessageError('READY SimulatorToServer message',
                                         reply)

        return reply

    def _handle_prediction_message(self, message):
        """
        The server sent predictions. Process it and send back the simulator's
        state.
        :param message: The message containing the prediction.
        :type message: ServerToSimulator protobuf message
        :return: The simulator state
        :rtype: SimulatorToServer protobuf message
        """

        if not message:
            raise EmptyMessageError('ServerToSimulator with PredictionData')
        if len(message.prediction_data) == 0:
            raise MalformedMessageError('prediction_data', message)

        reply = SimulatorToServer()

        for prediction in message.prediction_data:
            self._simulator_protocol.handle_prediction_message(prediction)
            self._simulator_protocol.advance()
            self._simulator_protocol.generate_state_message(reply)

        if reply.message_type != SimulatorToServer.STATE:
            raise UnexpectedMessageError('STATE SimulatorToServer '
                                         'message', reply)
        return reply

    def _handle_reset_message(self, _):
        """
        The server sent a reset. Handle it and return a Ready message.
        :return: A ready message
        :rtype: SimulatorToServer protobuf message
        """
        self._simulator_protocol.handle_reset_message()
        reply = SimulatorToServer()
        self._simulator_protocol.generate_ready_message(reply)

        if reply.message_type != SimulatorToServer.READY:
            raise UnexpectedMessageError('READY SimulatorToServer message',
                                         reply)

        return reply

    def _handle_finished_message(self, _):
        """
        When this message is recieved, time to exit.
        :return: None
        """
        self._simulator_protocol.handle_finish_message()
        self._state = DriverState.FINISHED
        return None

    def next(self, message):
        return self._state_funcs[self._state](message)


class SimulatorDriverForPrediction(Driver):
    """
    Driver used for prediction with a simulator.

    The prediction flow is different from training, in that it doesn't get
    the START/STOP/RESET/FINISH signals from the server and it needs to send
    its on its own the initial simulator state.
    """

    def __init__(self, **kwargs):
        super(SimulatorDriverForPrediction, self).__init__(**kwargs)
        self._simulator_protocol = kwargs.pop('simulator_connection')
        self._state_funcs = {
            DriverState.UNREGISTERED: self._send_register_message,
            DriverState.REGISTERING: self._handle_registration_acknowledgement,
            DriverState.ACTIVE: self._handle_prediction_message,
            DriverState.FINISHED: self._do_nothing
        }

    def _do_nothing(self, _):
        return None

    def _send_register_message(self, _):
        """
        In the beginning, send a register message.
        :return: A registration message
        :rtype: SimulatorToServer
        """
        self._state = DriverState.REGISTERING
        message = SimulatorToServer()

        self._base_protocol.generate_register_message(message)
        if message.message_type != SimulatorToServer.REGISTER:
            raise UnexpectedMessageError('REGISTER SimulatorToServer message',
                                         message)

        return message

    def _handle_registration_acknowledgement(self, message):
        """
        The server sends back an acknowledgement. Process that acknowledgement
        and send back a ready message to the server.
        :param message: An acknowledge register message.
        :type message: ServerToSimulator protobuf class
        :return: A ready message
        :rtype: SimulatorToServer protobuf message
        """
        if message.message_type != ServerToSimulator.ACKNOWLEDGE_REGISTER:
            error = 'Expected ACKNOWLEDGE_REGISTER but got {}'.format(
                MessageToString(message))
            raise RuntimeError(error)
        if not message.acknowledge_register_data:
            error = 'Missing data in ACKNOWLEDGE_REGISTER message {}'.format(
                MessageToString(message))
            raise RuntimeError(error)
        self._state = DriverState.ACTIVE
        self._base_protocol.handle_register_acknowledgement(
            message.acknowledge_register_data)

        # Difference between training and predicting is here... instead of
        # sending a READY, send an initial STATE.
        reply = SimulatorToServer()
        self._simulator_protocol.generate_state_message(reply)
        return reply

    def _handle_prediction_message(self, message):
        """
        The server sent predictions. Process it and send back the simulator's
        state.
        :param message: The message containing the prediction.
        :type message: ServerToSimulator protobuf message
        :return: The simulator state
        :rtype: SimulatorToServer protobuf message
        """

        if not message:
            raise EmptyMessageError('ServerToSimulator with PredictionData')
        if len(message.prediction_data) == 0:
            raise MalformedMessageError('prediction_data', message)

        reply = SimulatorToServer()

        for prediction in message.prediction_data:
            self._simulator_protocol.handle_prediction_message(prediction)
            self._simulator_protocol.advance()
            self._simulator_protocol.generate_state_message(reply)

        if reply.message_type != SimulatorToServer.STATE:
            raise UnexpectedMessageError('STATE SimulatorToServer '
                                         'message', reply)
        return reply

    def next(self, message):
        return self._state_funcs[self._state](message)


class GeneratorDriverForTraining(Driver):
    # TODO: Implement me!
    pass


class GeneratorDriverForPrediction(Driver):
    # TODO: Implement me!
    pass
