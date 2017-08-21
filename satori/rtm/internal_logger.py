
import os
import logging

logger = logging.getLogger('satori.rtm')


def configure_for_debugging():
    ws4py_formatter = logging.Formatter(
        'miniws4py:%(asctime)s:%(levelname)s:'
        '%(module)s.%(funcName)s:%(lineno)s:%(threadName)s: %(message)s')
    ws4py_handler = logging.StreamHandler()
    ws4py_handler.setFormatter(ws4py_formatter)

    ws4py_logger = logging.getLogger('miniws4py')
    ws4py_logger.setLevel(logging.DEBUG)
    ws4py_logger.addHandler(ws4py_handler)

    satori_formatter = logging.Formatter(
        'satori.rtm:%(asctime)s:%(levelname)s:'
        '%(module)s.%(funcName)s:%(lineno)s:%(threadName)s: %(message)s')
    satori_handler = logging.StreamHandler()
    satori_handler.setFormatter(satori_formatter)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(satori_handler)


if 'DEBUG_SATORI_SDK' in os.environ:
    configure_for_debugging()