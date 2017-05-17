from __future__ import print_function

import os
import sys
import time
import unittest
from test.utils import print_resource_usage


class TimedResult(unittest.TextTestResult):
    def startTest(self, test):
        self._origin = time.time()
        unittest.TextTestResult.startTest(self, test)

    def addSuccess(self, test):
        duration = time.time() - self._origin
        if duration > 1:
            name = self.getDescription(test)
            print('\nSlow test {0}: {1:.02} sec'.format(name, duration))
        unittest.TextTestResult.addSuccess(self, test)


if __name__ == '__main__':

    # there's no test discovery in unittest module
    # from python 2.6 standard library, so we roll our own
    for file in os.listdir('test'):
        if file.endswith('.py') and file not in [__file__, '__init__.py']:
            module = __import__(file[:-3])
            for name, value in module.__dict__.items():
                if name.startswith('Test'):
                    locals()[name] = value

    try:
        unittest.main(
            testRunner=unittest.TextTestRunner(resultclass=TimedResult))
    finally:
        print_resource_usage()
        sys.stdout.flush()
        sys.stderr.flush()
