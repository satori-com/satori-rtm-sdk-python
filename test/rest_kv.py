
from __future__ import print_function
import unittest
from hypothesis import given
import hypothesis.strategies as st

from satori.rtm.kv import KV

from test.utils import get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()

alphabet = 'abc123 /?;.&%'


def gen_text(min_size):
    return st.text(alphabet=alphabet, min_size=min_size)


class TestRestKV(unittest.TestCase):
    def setUp(self):
        self.kv = KV(endpoint, appkey)

    @unittest.skip("not implemented yet")
    @given(gen_text(min_size=1), gen_text(min_size=1))
    def test_write_read(self, k, v):
        self.kv.write(k, v)
        v_ = self.kv.read(k)
        self.assertEqual(v, v_)

    @unittest.skip("not implemented yet")
    @given(gen_text(min_size=1), gen_text(min_size=1), gen_text(min_size=1))
    def test_write_write_read(self, k, v1, v2):
        self.kv.write(k, v1)
        self.kv.write(k, v2)
        v_ = self.kv.read(k)
        self.assertEqual(v2, v_)

    @unittest.skip("not implemented yet")
    @given(gen_text(min_size=1), gen_text(min_size=1))
    def test_write_delete_read(self, k, v):
        self.kv.write(k, v)
        self.kv.delete(k)
        v_ = self.kv.read(k)
        self.assertIsNone(v_)

    @unittest.skip("not implemented yet")
    @given(gen_text(min_size=1), gen_text(min_size=1))
    def test_write_read_with_position(self, k, v):
        pw = self.kv.write(k, v)
        rbody = self.kv.read_with_position(k)
        self.assertEqual(v, rbody['message'])
        self.assertEqual(pw, rbody['position'])

    @unittest.skip("not implemented yet")
    @given(gen_text(min_size=1), gen_text(min_size=1))
    def test_write_read_read_with_position(self, k, v):
        self.kv.write(k, v)
        rbody1 = self.kv.read_with_position(k)
        rbody2 = self.kv.read_with_position(k)
        self.assertEqual(rbody1, rbody2)


if __name__ == '__main__':
    unittest.main()