"""
Thi file contains the client interfaces between simulators or generators and
the BRAIN backend. It is designed to be relatively modular and compatible with
both Python2 and Python3, using either Tornado or Asyncio (Python3 only) event
loops. In addition, the modularity makes it fairly simple to use with a
synchronous event loop or embed in some other type of client.
"""
import argparse
import logging
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


_BaseArguments = namedtuple('BaseArguments', ['brain_url',
                                              'headless',
                                              'recording_file'])


def parse_base_arguments():
    parser = argparse.ArgumentParser(
        description="Command line interface for running a simulator")

    train_brain_help = "The name of the BRAIN to connect to for training."
    predict_brain_help = (
        "The name of the BRAIN to connect to for predictions. If you "
        "use this flag, you must also specify the --predict-version flag.")
    predict_version_help = (
        "The version of the BRAIN to connect to for predictions. This flag "
        "must be specified when --predict-brain is used. This flag will "
        "be ignored if it is specified along with --train-brain or "
        "--brain-url.")
    brain_url_help = (
        "The full URL of the BRAIN to connect to. The URL should be of "
        "the form ws://api.bons.ai/v1/<username>/<brainname>/sims/ws "
        "when training, and of the form ws://api.bons.ai/v1/"
        "<username>/<brainname>/<version>/predictions/ws when predicting.")
    headless_help = (
        "The simulator can be run with or without the graphical environment."
        "By default the graphical environment is shown. Using --headless "
        "will run the simulator without graphical output.")
    recording_file_help = (
        "If specified, this should be a path to file where the simulator will "
        "record a stream of the messages transacted between the simulator and "
        "the BRAIN backend. If not specified, no recording is made."
    )

    brain_group = parser.add_mutually_exclusive_group(required=True)
    brain_group.add_argument("--train-brain", help=train_brain_help)
    brain_group.add_argument("--predict-brain", help=predict_brain_help)
    brain_group.add_argument("--brain-url", help=brain_url_help)
    parser.add_argument("--predict-version", help=predict_version_help)
    parser.add_argument("--headless", help=headless_help, action="store_true")
    parser.add_argument("--messages-out", help=recording_file_help,
                        default=None)

    args, unknown = parser.parse_known_args()

    config = BonsaiConfig()
    partial_url = "{base}/v1/{user}".format(
            base=config.brain_websocket_url(),
            user=config.username())

    # If the --brain_url flag was specified, use its value literally
    # for connecting to the BRAIN server. Otherwise, compose the url
    # to connect to from the other possible flags.
    if args.brain_url:
        brain_url = args.brain_url
    elif args.train_brain:
        brain_url = "{base}/{brain}/sims/ws".format(
            base=partial_url, brain=args.train_brain)
    elif args.predict_brain:
        if not args.predict_version:
            log.error("Flag --predict-version must be specified when flag "
                      "--predict-brain is used.")
            return
        brain_url = "{base}/{brain}/{version}/predictions/ws".format(
            base=partial_url,
            brain=args.predict_brain,
            version=args.predict_version)
    else:
        log.error("One of --brain-url, --predict-brain or --train-brain "
                  "must be specified.")
        return

    return _BaseArguments(brain_url, args.headless, args.messages_out)


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
    'access_key',
    'event_loop',
    'recording_file',
    'simulator_connection_class',
    'generator_connection_class',
    'connection_class_kwargs'
])


def _get_runtime_config(**kwargs):
    access_key = kwargs.pop('access_key', BonsaiConfig().access_key())
    event_loop = kwargs.pop('event_loop', 'tornado')
    recording_file = kwargs.pop('recording_file', None)
    simulator_connection_class = kwargs.pop('simulator_connection_class',
                                            SimulatorConnection)
    generator_connection_class = kwargs.pop('generator_connection_class',
                                            GeneratorConnection)
    connection_class_kwargs = kwargs.pop('connection_class_kwargs', None)
    return _RuntimeConfig(
        access_key=access_key,
        event_loop=event_loop,
        recording_file=recording_file,
        simulator_connection_class=simulator_connection_class,
        generator_connection_class=generator_connection_class,
        connection_class_kwargs=connection_class_kwargs
    )


def create_async_tasks(name,
                       simulator_or_generator,
                       brain_url,
                       **kwargs):
    """
    Creates tasks for a simulator or generator against the BRAIN server at the
    provided brain url.
    :param name: The name to assign to the simulator or generator.
    :param simulator_or_generator: Instance of the simulator or generator.
    :param brain_url: URL for reaching the backend BRAIN training or prediction
                      components.
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
                   - access_key = Overrides the access key provided by
                                  BonsaiConfig
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
    tasks = tasks_function(rcfg.access_key, brain_url,
                           driver, rcfg.recording_file)
    return tasks


def run_with_url(name,
                 simulator_or_generator,
                 brain_url,
                 **kwargs):
    """
    Runs a simulator or generator against the BRAIN server at the provided
    brain url.
    :param name: The name to assign to the simulator or generator.
    :param simulator_or_generator: Instance of the simulator or generator.
    :param brain_url: URL for reaching the backend BRAIN training or prediction
                      components.
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
                   - access_key = Overrides the access key provided by
                                  BonsaiConfig
    """

    rcfg = _get_runtime_config(**kwargs)
    driver = _create_driver(name, simulator_or_generator, brain_url,
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

    event_loop_func(rcfg.access_key, brain_url, driver, rcfg.recording_file)


def run_for_training_or_prediction(name,
                                   simulator_or_generator,
                                   **kwargs):
    """
    Helper function for client implemented simulators that exposes the
    appropriate command line arguments necessary for running a
    simulator with BrainServerConnection for training or prediction.
    :param name: The name to assign to the simulator or generator.
    :param simulator_or_generator: Instance of the simulator or generator.
    :param brain_url: URL for reaching the backend BRAIN training or prediction
                      components.
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
        run_with_url(name,
                     simulator_or_generator,
                     base_arguments.brain_url,
                     **kwargs)
