
try:
    import rapidjson as json
except ImportError:
    import json

__all__ = ['dumps', 'loads']

dumps = json.dumps
loads = json.loads