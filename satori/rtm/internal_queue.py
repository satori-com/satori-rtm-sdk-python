from six.moves import queue

import satori.rtm.internal_client_action as a

user_actions = [
    a.Publish, a.Subscribe,
    a.Authenticate,
    a.Read, a.Write, a.Delete]


class Queue(queue.Queue):
    def __init__(self, maxsize):
        self.softmaxsize = maxsize
        queue.Queue.__init__(self)

    def _put(self, item):
        is_user_action = type(item) in user_actions
        if len(self.queue) >= self.softmaxsize and is_user_action:
            raise Full
        queue.Queue._put(self, item)


Empty = queue.Empty
Full = queue.Full