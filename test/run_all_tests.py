from __future__ import print_function

import os
import sys
import unittest
from test.utils import print_resource_usage

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
        unittest.main()
    finally:
        print_resource_usage()
        sys.stdout.flush()
        sys.stderr.flush()
