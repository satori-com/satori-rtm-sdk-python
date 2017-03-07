# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

import threading
from threading import Event as E1
from threading import Event as E2


class TestEvent(unittest.TestCase):
    def test_event(self):

        e1 = E1()
        e2 = E2()

        self.assertEqual(e1.is_set(), e2.is_set())
        self.assertEqual(e1.isSet(), e2.isSet())

        e1.clear()
        e2.clear()

        self.assertEqual(e1.is_set(), e2.is_set())
        self.assertEqual(e1.isSet(), e2.isSet())

        e1.set()
        e2.set()

        self.assertEqual(e1.is_set(), e2.is_set())
        self.assertEqual(e1.isSet(), e2.isSet())

        e1.set()
        e2.set()

        self.assertEqual(e1.is_set(), e2.is_set())
        self.assertEqual(e1.isSet(), e2.isSet())

        e1.clear()
        e2.clear()

        self.assertEqual(e1.is_set(), e2.is_set())
        self.assertEqual(e1.isSet(), e2.isSet())

        def set_both_events():
            e1.set()
            e2.set()

        t = threading.Thread(
            target=set_both_events,
            name='test_event')
        t.start()

        e1.wait()
        e2.wait()

        t.join()

        self.assertEqual(e1.is_set(), e2.is_set())
        self.assertEqual(e1.isSet(), e2.isSet())


if __name__ == '__main__':
    unittest.main()
