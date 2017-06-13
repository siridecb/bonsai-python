"""
Thi file contains the client interfaces between simulators or generators and
the BRAIN backend. It is designed to be relatively modular and compatible with
both Python2 and Python3, using either Tornado or Asyncio (Python3 only) event
loops. In addition, the modularity makes it fairly simple to use with a
synchronous event loop or embed in some other type of client.
"""
import argparse
import logging
import os
from collections import namedtuple

from bonsai_config import BonsaiConfig
from bonsai.simulator import Simulator
from bonsai.generator import Generator
from bonsai.connections import SimulatorConnection, GeneratorConnection
from bonsai.drivers import SimulatorDriverForTraining
from bonsai.drivers import SimulatorDriverForPrediction
from bonsai.drivers import GeneratorDriverForTraining
from bonsai.drivers import GeneratorDriverForPrediction
from bonsai import tornado_event_loop

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


# The run methods in this dictionary have identical signatures. Asyncio is only
# available on Python 3.5 and higher. Runtime errors will be raised if you try
# to use the asyncio event loop on Python 3.4 and earlier, or any version of
# Python 2 (even with Trollius).
_RUN_EVENT_LOOP = {
    'tornado': tornado_event_loop.run,
}

# The methods in this dictionary have identical signatures. Asyncio is only
# available on Python 3.5 and higher. Runtime errors will be raised if you try
# to use the asyncio event loop on Python 3.4 and earlier, or any version of
# Python 2 (even with Trollius).
# Each method should return a tuple of the simulator run task (first) and a
# file recording task (second).
_CREATE_TASKS = {
    'tornado': tornado_event_loop.create_tasks,
}

try:
    from bonsai import asyncio_event_loop
    _RUN_EVENT_LOOP['asyncio'] = asyncio_event_loop.run
    _CREATE_TASKS['asyncio'] = asyncio_event_loop.create_tasks
except Exception as e:
    print('asyncio event loop not imported - %s' % str(e))


def _read_bonsai_config():
    """ Helper function to read the information that brain server
    connection needs from BonsaiConfig.
    """
    config = BonsaiConfig()
    return (
      config.access_key(), config.brain_websocket_url(), config.username())


def _env(key):
    return os.environ.get(key, None)


def parse_base_arguments(argv=None):
    parser = argparse.ArgumentParser(
        description="Command line interface for running a simulator "
                    "(brain_server_connection options)")

    train_brain_help = (
        "The name of the BRAIN to connect to for training.  "
        "This may be set as BONSAI_TRAIN_BRAIN in the environment.")
    predict_brain_help = (
        "The name of the BRAIN to connect to for predictions. If you "
        "use this flag, you must also specify the --predict-version flag. "
        "This may be set as BONSAI_PREDICT_BRAIN in the environment.")
    predict_version_help = (
        "The version of the BRAIN to connect to for predictions. This flag "
        "must be specified when --predict-brain is used. This flag will "
        "be ignored if it is specified along with --train-brain or "
        "--brain-url. "
        "This may be set as BONSAI_PREDICT_VERSION in the environment.")
    brain_url_help = (
        "The full URL of the BRAIN to connect to. The URL should be of "
        "the form ws://api.bons.ai/v1/<username>/<brainname>/sims/ws "
        "when training, and of the form ws://api.bons.ai/v1/"
        "<username>/<brainname>/<version>/predictions/ws when predicting. "
        "This may be set as BONSAI_BRAIN_URL in the environment.")
    recording_file_help = (
        "If specified, this should be a path to file where the simulator will "
        "record a stream of the messages transacted between the simulator and "
        "the BRAIN backend. If not specified, no recording is made.")
    access_key_help = (
        "The access key to use when connecting to the BRAIN server. If "
        "specified, it will be used instead of any access key information "
        "stored in a bonsai config file. "
        "This may be set as BONSAI_ACCESS_KEY in the environment.")

    brain_group = parser.add_mutually_exclusive_group(required=False)
    brain_group.add_argument("--train-brain", help=train_brain_help,
                             default=_env('BONSAI_TRAIN_BRAIN'))
    brain_group.add_argument("--predict-brain", help=predict_brain_help,
                             default=_env('BONSAI_PREDICT_BRAIN'))
    brain_group.add_argument("--brain-url", help=brain_url_help,
                             default=_env('BONSAI_BRAIN_URL'))
    parser.add_argument("--predict-version", help=predict_version_help,
                        default=_env('BONSAI_PREDICT_VERSION'))
    parser.add_argument("--recording-file", help=recording_file_help,
                        default=None)
    parser.add_argument("--access-key", help=access_key_help,
                        default=_env('BONSAI_ACCESS_KEY'))

    args, unknown = parser.parse_known_args(argv)

    # Read some information from the bonsai config
    access_key, base_url, username = _read_bonsai_config()

    # If the access key was not specified on the command line, read
    # it from bonsai config.
    if not args.access_key:
        if not access_key:
            parser.error("Access key is required.  It may be specified by"
                         " --access-key or by running bonsai configure.")
        args.access_key = access_key

    # Mutual exclusion check. ArgumentParser does not know if multiple
    # environment variables are set.
    number_set = 0
    for key in ['brain_url', 'train_brain', 'predict_brain']:
        if getattr(args, key):
            number_set = number_set + 1

    if number_set > 1:
        parser.error("At most one of --train-brain, --predict-brain, "
                     "or --brain-url (or similar environment variable) "
                     "is allowed.")
    elif number_set == 0:
        parser.error("At least one of --train-brain, --predict-brain, "
                     "or --brain-url is required.")

    # When the --train-brain or --predict-brain flags are specified,
    # we must compose brain_url ourselves.
    partial_url = "{base}/v1/{user}".format(base=base_url, user=username)
    if args.train_brain:
        args.brain_url = "{base}/{brain}/sims/ws".format(
            base=partial_url, brain=args.train_brain)
    elif args.predict_brain:
        if not args.predict_version:
            parser.error("Flag --predict-version must be specified when flag "
                         "--predict-brain is used.")
        args.brain_url = "{base}/{brain}/{version}/predictions/ws".format(
            base=partial_url,
            brain=args.predict_brain,
            version=args.predict_version)

    return args


def _create_driver(name, simulator_or_generator, brain_api_url,
                   simulator_connection_class,
                   generator_connection_class,
                   connection_class_kwargs):
    is_for_training = brain_api_url.endswith('/sims/ws')
    connection_class_kwargs = connection_class_kwargs or {}
    if isinstance(simulator_or_generator, Simulator):
        connection = simulator_connection_class(
            simulator_name=name,
            simulator=simulator_or_generator,
            **connection_class_kwargs)
        if is_for_training:
            return SimulatorDriverForTraining(
                connection=connection, simulator_connection=connection)
        else:
            return SimulatorDriverForPrediction(
                connection=connection, simulator_connection=connection)
    elif isinstance(simulator_or_generator, Generator):
        connection = generator_connection_class(
            generator_name=name,
            generator=simulator_or_generator,
            **connection_class_kwargs)
        if is_for_training:
            return GeneratorDriverForTraining(
                connection=connection, generator_connection=connection)
        else:
            return GeneratorDriverForPrediction(
                connection=connection, generator_connection=connection)
    else:
        error = ('Unrecognized simulator or generator type {}'.format(
            type(simulator_or_generator).__name__))
        raise RuntimeError(error)


_RuntimeConfig = namedtuple('RuntimeConfig', [
    'event_loop',
    'recording_file',
    'simulator_connection_class',
    'generator_connection_class',
    'connection_class_kwargs'
])


def _get_runtime_config(**kwargs):
    event_loop = kwargs.pop('event_loop', 'tornado')
    recording_file = kwargs.pop('recording_file', None)
    simulator_connection_class = kwargs.pop('simulator_connection_class',
                                            SimulatorConnection)
    generator_connection_class = kwargs.pop('generator_connection_class',
                                            GeneratorConnection)
    connection_class_kwargs = kwargs.pop('connection_class_kwargs', None)
    return _RuntimeConfig(
        event_loop=event_loop,
        recording_file=recording_file,
        simulator_connection_class=simulator_connection_class,
        generator_connection_class=generator_connection_class,
        connection_class_kwargs=connection_class_kwargs
    )


def create_async_tasks(name,
                       simulator_or_generator,
                       brain_url,
                       access_key,
                       **kwargs):
    """
    Creates tasks for a simulator or generator against the BRAIN server at the
    provided brain url.
    :param name: The name to assign to the simulator or generator.
    :param simulator_or_generator: Instance of the simulator or generator.
    :param brain_url: URL for reaching the backend BRAIN training or prediction
                      components.
    :param access_key: The access key to use when connecting to BRAIN backend.
    :param kwargs: Additional optional keyword arguments. Valid arguments
                   include:
                   - event_loop = Specifies which event loop to use to drive
                                  the simulator or generator. May be one of the
                                  following: ['tornado', 'asyncio']. Choose
                                  'tornado' if you are running Python 2.7 or
                                  Python 3.4 and below. Defaults to 'tornado'.
                   - recording_file = If defined, records a text file detailing
                                      all the messages communicated among the
                                      simulator/generator and the BRAIN backend
                                      to the path specified. This is useful for
                                      mock tests and playbacks. Defaults to
                                      None.
                   - simulator_connection_class = Class to be used for hooking
                                                  into the simulator. Defaults
                                                  to SimulatorConnection.
                   - generator_connection_class = Class to be used for hooking
                                                  into the generator. Defaults
                                                  to GeneratorConnection.
                   - connection_class_kwargs = Dictionary of parameters to be
                                               passed to the simulator or
                                               generator connection class at
                                               construction. Defaults to None.
    """
    rcfg = _get_runtime_config(**kwargs)
    driver = _create_driver(name, simulator_or_generator, brain_url,
                            rcfg.simulator_connection_class,
                            rcfg.generator_connection_class,
                            rcfg.connection_class_kwargs)

    try:
        tasks_function = _CREATE_TASKS[rcfg.event_loop]
    except KeyError:
        raise ValueError('Invalid event loop {} provided; only supported '
                         'event loops are {}'.format(rcfg.event_loop,
                                                     str(_CREATE_TASKS.keys())
                                                     ))

    return tasks_function(access_key, brain_url, driver, rcfg.recording_file)


def run_for_training_or_prediction(name,
                                   simulator_or_generator,
                                   **kwargs):
    """
    Helper function for client implemented simulators that exposes the
    appropriate command line arguments necessary for running a
    simulator with BrainServerConnection for training or prediction.
    :param name: The name to assign to the simulator or generator.
    :param simulator_or_generator: Instance of the simulator or generator.
    :param kwargs: Additional optional keyword arguments. Valid arguments
                   include:
                   - event_loop = Specifies which event loop to use to drive
                                  the simulator or generator. May be one of the
                                  following: ['tornado', 'asyncio']. Choose
                                  'tornado' if you are running Python 2.7 or
                                  Python 3.4 and below. Defaults to 'tornado'.
                   - recording_file = If defined, records a text file detailing
                                      all the messages communicated among the
                                      simulator/generator and the BRAIN backend
                                      to the path specified. This is useful for
                                      mock tests and playbacks. Defaults to
                                      None.
                   - simulator_connection_class = Class to be used for hooking
                                                  into the simulator. Defaults
                                                  to SimulatorConnection.
                   - generator_connection_class = Class to be used for hooking
                                                  into the generator. Defaults
                                                  to GeneratorConnection.
    """
    base_arguments = parse_base_arguments()
    if base_arguments:
        rcfg = _get_runtime_config(**kwargs)
        recording_file = rcfg.recording_file or base_arguments.recording_file

        driver = _create_driver(name, simulator_or_generator,
                                base_arguments.brain_url,
                                rcfg.simulator_connection_class,
                                rcfg.generator_connection_class,
                                rcfg.connection_class_kwargs)

        try:
            event_loop_func = _RUN_EVENT_LOOP[rcfg.event_loop]
        except KeyError:
            raise ValueError('Invalid event loop {} provided; only supported '
                             'event loops '
                             'are {}'.format(rcfg.event_loop,
                                             str(_RUN_EVENT_LOOP.keys())))

        event_loop_func(base_arguments.access_key, base_arguments.brain_url,
                        driver, recording_file)
