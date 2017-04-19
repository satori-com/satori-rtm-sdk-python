
'''

satori.rtm.logger
==================

The Python SDK includes a `logging.Logger` object in the `satori.rtm.logger`
module. You can configure this logger to your specific needs. You can set the
logging verbosity to `Debug` during debugging to find error sources faster.

To enable stderr-based verbose logging on the command-line, set the
DEBUG_SATORI_SDK environment variable to debug::

  export DEBUG_SATORI_SDK=debug
  ./example.py # this now produces verbose logs
  unset DEBUG_SATORI_SDK
  ./example.py # this does not

'''

import os
import logging

logger = logging.getLogger('satori')


def configure(level):
    ws4py_formatter = logging.Formatter('miniws4py: %(message)s')
    ws4py_handler = logging.StreamHandler()
    ws4py_handler.setFormatter(ws4py_formatter)

    ws4py_logger = logging.getLogger('miniws4py')
    ws4py_logger.setLevel(logging.WARNING)
    ws4py_logger.addHandler(ws4py_handler)

    satori_formatter = logging.Formatter(
        'satori:%(asctime)s:%(levelname)s:%(threadName)s: %(message)s')
    satori_handler = logging.StreamHandler()
    satori_handler.setFormatter(satori_formatter)

    logger.setLevel(level)
    logger.addHandler(satori_handler)

    ws4py_logger.setLevel(logging.DEBUG)


if 'DEBUG_SATORI_SDK' in os.environ:
    if os.environ['DEBUG_SATORI_SDK'] == 'debug':
        loglevel = logging.DEBUG
    elif os.environ['DEBUG_SATORI_SDK'] == 'warning':
        loglevel = logging.WARNING
    else:
        loglevel = logging.INFO
    configure(loglevel)
else:
    logger.addHandler(logging.NullHandler())
    miniws4py_logger = logging.getLogger('miniws4py')
    miniws4py_logger.addHandler(logging.NullHandler())