"""
Unit tests for the code in brain_server_connection.py.
"""
import os
import sys
from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import ANY, Mock, patch

from bonsai.simulator import Simulator
from bonsai.brain_server_connection import parse_base_arguments
from bonsai.brain_server_connection import run_for_training_or_prediction


@contextmanager
def hide_stderr():
    """This context manager can be used to temporarily redirect
    stderr output to null.
    """
    class NullStream:
        def write(self, _):
            pass

    stderr_orig = sys.stderr
    sys.stderr = NullStream()

    try:
        yield
    finally:
        sys.stderr = stderr_orig


class BrainServerConnectionTests(TestCase):
    def _default_args(self):
        return ['--access-key', 'test-key']

    def test_brain_url_passed_literally(self):
        """This tests verifies that a url passed using the flag --brain-url
        is returned unmodified.
        """
        brain_url = "ws://some_url_here"
        argv = ["--brain-url", brain_url]
        argv.extend(self._default_args())
        base_args = parse_base_arguments(argv)
        self.assertEqual(brain_url, base_args.brain_url)
        self.assertIsNone(base_args.recording_file)

    @patch("bonsai.brain_server_connection._read_bonsai_config")
    def test_train_brain(self, mock_read):
        """This test verfies that brain_url is composed correctly when
        the --train-brain flag is passed.
        """
        mock_read.return_value = ("trainkey", "ws://root", "test_user")

        argv = ["--train-brain", "cartpole"]
        base_args = parse_base_arguments(argv)

        self.assertEqual("ws://root/v1/test_user/cartpole/sims/ws",
                         base_args.brain_url)
        self.assertEqual("trainkey", base_args.access_key)

    @patch("bonsai.brain_server_connection._read_bonsai_config")
    def test_predict_brain(self, mock_read):
        """This test verifies that brain_url is composed correctly when
        the predict flags are passed.
        """
        mock_read.return_value = ("predictkey", "ws://root", "test_user")

        argv = ["--predict-brain", "cartpole", "--predict-version", "49"]
        base_args = parse_base_arguments(argv)

        self.assertEqual("ws://root/v1/test_user/cartpole/49/predictions/ws",
                         base_args.brain_url)
        self.assertEqual("predictkey", base_args.access_key)

    def test_predict_brain_missing_version(self):
        """This test verifies that an error occurs when the predict brain
        flag is passed without the predict version flag.
        """
        argv = ["--predict-brain", "cartpole"]
        argv.extend(self._default_args())
        # Argument parsing errors end up on stderr, which makes unit test
        # output messy, so hide it here.
        with hide_stderr():
            with self.assertRaises(SystemExit):
                parse_base_arguments(argv)

    @patch("bonsai.brain_server_connection._read_bonsai_config")
    def test_access_key(self, mock_read):
        """This test verifies that an access key specified on the command
        line is used over an access key read from bonsai config.
        """
        mock_read.return_value = ("config_key", "ws://root", "test_user")

        argv = ["--train-brain", "cartpole", "--access-key", "cmd_line_key"]
        base_args = parse_base_arguments(argv)

        self.assertEqual("cmd_line_key", base_args.access_key)

    @patch("bonsai.brain_server_connection._read_bonsai_config")
    def test_access_key_missing(self, mock_read):
        """If no access key is provided, the command returns an error.
        """
        mock_read.return_value = (None, None, None)

        argv = ["--train-brain", "cartpole"]
        with hide_stderr():
            with self.assertRaises(SystemExit):
                base_args = parse_base_arguments(argv)

    def test_env_url(self):
        """ A brain-url specified by an environment variable is used """
        argv = []
        argv.extend(self._default_args())
        with patch.dict('os.environ', {'BONSAI_BRAIN_URL': 'ws://test/v1/'}):
            base_args = parse_base_arguments(argv)

        self.assertEqual("ws://test/v1/", base_args.brain_url)

    def test_env_override(self):
        """Command line arguments override environment variables """
        argv = ['--brain-url', 'ws://cmdline/v1/brain']
        argv.extend(self._default_args())
        with patch.dict('os.environ', {'BONSAI_BRAIN_URL': 'ws://test/v1/'}):
            base_args = parse_base_arguments(argv)

        self.assertEqual('ws://cmdline/v1/brain', base_args.brain_url)

    def test_env_exclusive(self):
        """ Command arguments and env variables are mutually exclusive """
        argv = ['--predict-brain', 'life_of_brian']
        argv.extend(self._default_args())
        with patch.dict('os.environ', {'BONSAI_BRAIN_URL': 'ws://test/v1/'}):
            with hide_stderr():
                with self.assertRaises(SystemExit):
                    base_args = parse_base_arguments(argv)

    def test_recording_file(self):
        """ Recording file argument is used """
        argv = ['program', '--train-brain', 'life', '--recording-file', 'file']
        argv.extend(self._default_args())
        mock_run = Mock()
        with patch('sys.argv', argv):
            with patch.dict('bonsai.brain_server_connection._RUN_EVENT_LOOP',
                            {'tornado': mock_run}):
                run_for_training_or_prediction('name', Simulator())
                mock_run.assert_called_with('test-key', ANY, ANY, 'file')
                mock_run.reset_mock()

                # the kwarg overrides the command line argument
                run_for_training_or_prediction('name', Simulator(),
                                               recording_file='override')
                mock_run.assert_called_with('test-key', ANY, ANY, 'override')
