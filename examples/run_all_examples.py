
from __future__ import print_function
import os
import subprocess
import test.utils
import time

endpoint, appkey = test.utils.get_test_endpoint_and_appkey()
role, secret, _ = test.utils.get_test_role_name_secret_and_channel()

examples_that_must_be_stopped_externally = [
    'publish.py',
    'replacing_subscription.py',
    'subscribe_to_channel.py',
    'subscribe_to_open_channel.py',
    'subscribe_with_age.py',
    'subscribe_with_count.py',
    'subscribe_with_multiple_views.py',
    'subscribe_with_position.py',
    'subscribe_with_view.py']


def main():
    import logging
    logging.basicConfig(level=logging.WARNING)

    subprocess.check_call(['touch', 'examples/__init__.py'])
    excludes = [os.path.basename(__file__), '__init__.py', 'rest_api.py']
    for file in os.listdir('examples'):
        if file.endswith('.py') and\
                file not in excludes:
            run_example(
                os.path.join('examples', file),
                file in examples_that_must_be_stopped_externally)


def run_example(file, must_kill):
    mname = file.replace('/', '.').replace('.py', '')
    command = [
        'python',
        '-c',
        '''import {} as m;'''
        '''m.endpoint = "{}";'''
        '''m.appkey = "{}";'''
        '''m.role = u"{}";'''
        '''m.role_secret_key = u"{}";'''
        '''m.main()'''.format(mname, endpoint, appkey, role, secret)]
    p = subprocess.Popen(command)

    if must_kill:
        time.sleep(5)
        assert p.returncode is None, file
        p.terminate()

    p.communicate()

    if not must_kill:
        assert p.returncode == 0, file


if __name__ == '__main__':
    main()
