
# -*- coding: utf-8 -*-

from __future__ import print_function
from collections import namedtuple as t

# PubSub family
Publish = t('Publish', ['channel', 'message', 'callback'])
Subscribe = t(
    'Subscribe',
    ['channel_or_subscription_id', 'mode', 'observer', 'args'])
Unsubscribe = t('Unsubscribe', ['channel_or_subscription_id'])

# KV family
Read = t('Read', ['key', 'args', 'callback'])
Write = t('Write', ['key', 'value', 'callback'])
Delete = t('Delete', ['key', 'callback'])

# Search
Search = t('Search', ['prefix', 'callback'])

Authenticate = t('Authenticate', ['auth_delegate', 'callback'])

Start = t('Start', [])
Stop = t('Stop', [])
Dispose = t('Dispose', [])

ConnectingComplete = t('ConnectingComplete', [])
ConnectingFailed = t('ConnectingFailed', [])
ConnectionClosed = t('ConnectionClosed', [])
InternalError = t('InternalError', ['payload'])
ChannelData = t('ChannelData', ['data'])
ChannelError = t('ChannelError', ['channel', 'payload'])
FastForward = t('FastForward', ['channel', 'payload'])

Tick = t('Tick', [])