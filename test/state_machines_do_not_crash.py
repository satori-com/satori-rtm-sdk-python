# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

import satori.rtm.internal_subscription as sis
import satori.rtm.generated.subscription_sm as ssm

not_event_names = ['Entry', 'Exit', 'Default', '__module__', '__doc__']


class FSM_Mock(object):

    def __init__(self, s, t, fail_count_is_small):
        self.state = s
        self.transition = t
        self.log = []
        self.ctxtlog = []
        self.fail_count_is_small = fail_count_is_small

    def getOwner(self):
        class Owner(object):
            def _fail_count_is_small(this):
                return self.fail_count_is_small

            def __getattr__(this, name):
                def f(*args):
                    self.ctxtlog.append((name, len(args)))
                return f
        return Owner()

    def getState(self):
        return self

    def clearState(self):
        self.state = None

    def setState(self, s):
        self.state = s

    def getName(self):
        return self.state.getName()

    def getTransition(self):
        return self.transition

    def __getattr__(self, name):
        self.transition = name
        self.log.append(name)
        return lambda *args: 42


class TestStateMachinesDoNotCrash(unittest.TestCase):

    def test_state_sm(self):
        event_names = []
        for event_name in ssm.SubscriptionState.__dict__:
            if event_name not in not_event_names:
                event_names.append(event_name)

        ctxtlog = []

        for state_name, state_class in ssm.__dict__.items():
            if state_name in ['Subscription_sm', 'Subscription_Default']:
                continue
            if state_name.startswith('Subscription_'):

                state_value = state_class(state_name, 1)
                fsm_mock = FSM_Mock(state_value, None, True)
                state_value.Entry(fsm_mock)
                state_value.Exit(fsm_mock)
                ctxtlog += fsm_mock.ctxtlog

                for event_name in event_names:
                    state_value = state_class(state_name, 1)
                    fsm_mock = FSM_Mock(
                        state_value, event_name, True)
                    if event_name == 'ChannelError':
                        getattr(state_value, event_name)(
                            fsm_mock, 'Test error')
                    else:
                        getattr(state_value, event_name)(fsm_mock)
                    ctxtlog += fsm_mock.ctxtlog

        subscription = sis.Subscription(None, None, None, None)
        for method_name, _arity in ctxtlog:
            method = getattr(subscription, method_name)
            self.assertTrue(method)


if __name__ == '__main__':
    unittest.main()
