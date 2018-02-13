import sys
import unittest
from collections import namedtuple
from bonsai.inkling_types import Luminance
from bonsai.common.state_to_proto import build_luminance_from_state

"""
This namedtuple is useful when generating generic protobuff messages
It will be useful in the future when we implement other complex types
"""
SimState = namedtuple("SimState", ["state", "is_terminal"])


class TestStateToProto(unittest.TestCase):
    """ All tests for state_to_proto.py will go in here """
    def test_exception_build_luminance_from_state(self):
        """
        Test that the exception is raised for the build_luminance_from_state
        function. We pass in some type that is not Luminance to check that
        the exception is raised
        """
        not_luminance = [1, 2, 3]
        self.assertRaises(Exception, build_luminance_from_state,
                          'generic_msg', 'generic_msg', not_luminance)

    def test_build_luminance_from_state(self):
        """
        Test that the build_luminance_from_state function runs
        properly when a Luminance type and a generic Luminance
        protobuff message are passed in.

        NOTE: We do not need an assert as the testing framework
              catches that a function did not run properly
        """
        # python2.7 bytes is an alias for str, use bytearray instead
        if sys.version_info.major < 3:
            lum_from_state = Luminance(0, 0, bytearray(0))
            lum_in_proto = Luminance(0, 0, bytearray(0))
        else:
            lum_from_state = Luminance(0, 0, bytes(0))
            lum_in_proto = Luminance(0, 0, bytes(0))
        field_name = "state"
        proto_msg = SimState(lum_in_proto, 'generic_msg')
        build_luminance_from_state(field_name, proto_msg, lum_from_state)

if __name__ == '__main__':
    unittest.main()
