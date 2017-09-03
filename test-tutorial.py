#!/usr/bin/env python

import json
import shutil
import subprocess
import time

def main():
    with open('credentials.json') as f:
        creds = json.load(f)

    shutil.rmtree('test.tutorials', ignore_errors=True)
    shutil.copytree('tutorials', 'test.tutorials')

    with open('test.tutorials/quickstart.py') as fi:
        with open('test.tutorials/quickstart.py.tmp', 'w') as fo:
            fo.writelines(inject_credentials(creds, l) for l in fi.readlines())
    shutil.move('test.tutorials/quickstart.py.tmp', 'test.tutorials/quickstart.py')

    p = subprocess.Popen(['python', './quickstart.py'],
        cwd='test.tutorials',
        env={'PYTHONPATH': '..'},
        stdout=subprocess.PIPE,
        bufsize=1)
    try:
        time.sleep(10)
        assert p.returncode == None
    finally:
        p.terminate()

    out, err = p.communicate()
    out = out.decode('utf8')

    assert 'Animal is published' in out, out
    assert 'Animal is received' in out, out

    print('Tutorial seems to be working fine')


def inject_credentials(creds, s):
    return s\
        .replace('YOUR_ENDPOINT', creds['endpoint'])\
        .replace('YOUR_APPKEY', creds['appkey'])\
        .replace('YOUR_ROLE', creds['auth_role_name'])\
        .replace(" = 'YOUR_SECRET'", " = '" + creds['auth_role_secret_key'] + "'")

if __name__ == '__main__':
    main()
