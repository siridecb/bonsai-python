"""
This file contains functionality related to logging.
"""

import logging


def logging_basic_config(level=logging.INFO):
    """
    This function sets up a very simple root logger with the intention
    of making it simple for most simulators to setup logging. Simulators
    should call this function at the beginning of their main, before
    calling bonsai.run_for_training_or_prediction(). If you are an
    advanced user who wants to configure their own logging, you do not
    need to use this function.
    """
    logging.basicConfig(
        level=level,
        format="[%(asctime)s][%(levelname)s][%(name)s]%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")
