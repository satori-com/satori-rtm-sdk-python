# -*- coding: utf-8 -*-

from __future__ import print_function
import logging
import unittest

import satori.rtm.logger

levels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR]


def cleanup():
    for loggername in ['miniws4py', 'satori']:
        logger = logging.getLogger(loggername)
        while logger.handlers:
            h = logger.handlers[0]
            logger.removeHandler(h)


class TestLogging(unittest.TestCase):

    def test_configure_platform_logger(self):
        self.addCleanup(cleanup)

        # let's at least make sure that it doesn't throw
        for level in levels:
            satori.rtm.logger.configure(level)


if __name__ == '__main__':
    unittest.main()