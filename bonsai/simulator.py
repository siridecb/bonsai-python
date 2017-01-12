
from collections import namedtuple

# SimState is a convenience class for the data generated by the simulator
# during training. It consists of a "state", which is a dictionary mapping
# the field names specified in the source-inkling file with the state data
# for the relevant field. The second argument "is_terminal" is a boolean
# indicating whether or not the reported state is a final state of the
# simulation
SimState = namedtuple("SimState", ["state", "is_terminal"])


class Simulator(object):
    """
    Interface for client implemented Simulators using
    BrainServerConnection.

    Simulators must implement get_state() and advance()

    Simulators must also add methods whose names correspond to the
    objectives declared in inkling.
    Note: This Simulator class assumes synchronous action-state transitions.
    This means that the action takes place before the next state is sent. If
    this is not a safe assumption, use AsynchronousSimulator
    """
    def __init__(self):
        self.properties = {}
        self._last_actions = None

    def set_properties(self, **kwargs):
        self.properties = kwargs

    def start(self):
        pass

    def stop(self):
        pass

    def reset(self):
        pass

    def get_last_action(self):
        """ when sending states to the server, this function determines which
        corresponding action to send """
        return self._last_actions

    def notify_prediction_received(self, predictions):
        """ When receiving new predictions, save off a copy before reporting
        to simulator """
        self._last_actions = predictions

    def advance(self, actions):
        """ This function must be implemented for all simulators.
        During training this function will be called repeatedly, and is used
        to advance the simulation using the specified actions.
        """
        raise NotImplementedError()

    def get_state(self):
        """ This function must be implemented for all simulators.
        During training and prediction, this is used to construct the state
        message that represents the current simulation state.
        It is assumed that this function returns SimState objects """
        raise NotImplementedError()
