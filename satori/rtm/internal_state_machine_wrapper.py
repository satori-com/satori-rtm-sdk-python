
import threading
from collections import deque

from satori.rtm.logger import logger


class StateMachineWrapper(object):
    def __init__(self, sm_class, delegate):
        self.lock = threading.RLock()
        self._sm = sm_class(delegate)
        self._sm_transition_queue = deque()

    def advance(self, f):
        def go(g):
            if self._sm_transition_queue:
                logger.debug('Appending to transition queue')
                self._sm_transition_queue.append(g)
            else:
                self._sm_transition_queue.append(g)
                logger.debug(
                    '%s performing transition',
                    self._sm.__class__.__name__)
                g(self._sm)
                self._sm_transition_queue.popleft()
                while self._sm_transition_queue:
                    h = self._sm_transition_queue.popleft()
                    go(h)

        with self.lock:
            go(f)

    def get_state_name(self):
        return self._sm.getState().getName()