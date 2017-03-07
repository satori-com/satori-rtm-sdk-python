from __future__ import print_function

import subprocess
import unittest

from test.utils import make_channel_name


class TestChat(unittest.TestCase):

    def test_1(self):

        def say(person, message):
            person.stdin.write(message + b'\n')
            person.stdin.flush()

        def expect(persons, message):
            for person in persons:
                s = person.stdout.readline()
                self.assertEqual(s.rstrip(), message)

        channel = make_channel_name('chat')

        alice = subprocess.Popen(
            ['python', 'examples/chat/interactive.py', 'alice', channel],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE)

        try:
            expect([alice], b'alice joined the channel')

            bob = subprocess.Popen(
                ['python', 'examples/chat/interactive.py', 'bob', channel],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE)

            try:
                both = [alice, bob]

                expect(both, b'bob joined the channel')

                say(alice, b'Hi!')
                expect(both, b'alice> Hi!')

                say(bob, b'Welcome!')
                expect(both, b'bob> Welcome!')

                say(alice, b'kthxbye')
                expect(both, b'alice> kthxbye')

                say(alice, b'/quit')
                expect([bob], b'alice left the channel')

                say(bob, b'oh well')
                expect([bob], b'bob> oh well')

                say(bob, b'/quit')
            except:
                bob_out, bob_err = bob.communicate()
                print('Bob out: {0}'.format(bob_out))
                print('Bob err: {0}'.format(bob_err))
                raise
        except:
            alice_out, alice_err = alice.communicate()
            print('Alice out: {0}'.format(alice_out))
            print('Alice err: {0}'.format(alice_err))
            raise

        alice.communicate()
        bob.communicate()

        self.assertEqual(alice.returncode, 0)
        self.assertEqual(bob.returncode, 0)


if __name__ == '__main__':
    unittest.main()
