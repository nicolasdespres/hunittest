# -*- encoding: utf-8 -*-
"""Test "hunittest.line_printer" package.
"""

import unittest

from hunittest.termlib import truncate_ansi_string
from hunittest.termlib import ansi_string_truncinfo
from hunittest.termlib import TermInfo


class TestTruncateAnsiString(unittest.TestCase):

    def setUp(self):
        super(TestTruncateAnsiString, self).setUp()
        self.termnfo = TermInfo(color_mode="always")

    def test_negative(self):
        with self.assertRaises(ValueError):
            ansi_string_truncinfo("", -1)
        with self.assertRaises(ValueError):
            truncate_ansi_string("", -1)

    def test_none_string(self):
        with self.assertRaises(ValueError):
            ansi_string_truncinfo(None, 1)
        with self.assertRaises(ValueError):
            truncate_ansi_string(None, 1)

    def test_empty_string(self):
        self.assertEqual((0, 0, False), ansi_string_truncinfo("", 0))
        self.assertEqual((0, 0, False), ansi_string_truncinfo("", 1))
        self.assertEqual((0, 0, False), ansi_string_truncinfo("", 100))
        self.assertEqual("", truncate_ansi_string("", 0))
        self.assertEqual("", truncate_ansi_string("", 1))
        self.assertEqual("", truncate_ansi_string("", 100))

    def test_size_0_no_ansi(self):
        q = "foobarblue"
        a = ""
        s = 0
        self.assertEqual(a, truncate_ansi_string(q, s))
        self.assertEqual((s, s, False),
                         ansi_string_truncinfo(q, s))

    def test_size_1_no_ansi(self):
        q = "foobarblue"
        s = 1
        a = "f"
        self.assertEqual(a, truncate_ansi_string(q, s))
        self.assertEqual((s, s, False),
                         ansi_string_truncinfo(q, s))

    def test_size_3_no_ansi(self):
        q = "foobarblue"
        a = "foo"
        s = 3
        self.assertEqual(a, truncate_ansi_string(q, s))
        self.assertEqual((s, s, False),
                         ansi_string_truncinfo(q, s))

    def test_size_exceed_no_ansi(self):
        text = "foobarblue"
        s = 10000
        self.assertEqual(text, truncate_ansi_string(text, s))
        self.assertEqual((len(text), len(text), False),
                         ansi_string_truncinfo(text, s))

    def test_size_0_ansi_first(self):
        fixture = self.termnfo.fore_red+"text"
        size = 0
        expected = ""
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((0, 0, False),
                         ansi_string_truncinfo(fixture, size))

    def test_size_1_ansi_first(self):
        fixture = self.termnfo.fore_red+"text"
        size = 1
        expected = self.termnfo.fore_red+"t"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), 1, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_2_ansi_first(self):
        fixture = self.termnfo.fore_red+"text"
        size = 2
        expected = self.termnfo.fore_red+"te"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_3_ansi_first(self):
        fixture = self.termnfo.fore_red+"text"
        size = 3
        expected = self.termnfo.fore_red+"tex"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_exceed_ansi_first(self):
        fixture = self.termnfo.fore_red+"text"
        expected = self.termnfo.fore_red+"text"
        actual = truncate_ansi_string(fixture, 4000)
        self.assertEqual(expected, actual)

    def test_size_0_ansi_middle(self):
        fixture = "123"+self.termnfo.fore_red+"red"
        size = 0
        expected = ""
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, False),
                         ansi_string_truncinfo(fixture, size))

    def test_size_1_ansi_middle(self):
        fixture = "123"+self.termnfo.fore_red+"red"
        size = 1
        expected = "1"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, False),
                         ansi_string_truncinfo(fixture, size))

    def test_size_2_ansi_middle(self):
        fixture = "123"+self.termnfo.fore_red+"red"
        size = 2
        expected = "12"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, False),
                         ansi_string_truncinfo(fixture, size))

    def test_size_3_ansi_middle(self):
        fixture = "123"+self.termnfo.fore_red+"red"
        size = 3
        expected = "123"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, False),
                         ansi_string_truncinfo(fixture, size))

    def test_size_4_ansi_middle(self):
        fixture = "123"+self.termnfo.fore_red+"456"
        size = 4
        expected = "123"+self.termnfo.fore_red+"4"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_5_ansi_middle(self):
        fixture = "123"+self.termnfo.fore_red+"456"
        size = 5
        expected = "123"+self.termnfo.fore_red+"45"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_6_ansi_middle(self):
        fixture = "123"+self.termnfo.fore_red+"456"
        size = 6
        expected = "123"+self.termnfo.fore_red+"456"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_exceed_ansi_middle(self):
        fixture = "123"+self.termnfo.fore_red+"456"
        size = 10000
        expected = "123"+self.termnfo.fore_red+"456"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), 6, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_0_ansi_first_middle(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"red"
        size = 0
        expected = ""
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, False),
                         ansi_string_truncinfo(fixture, size))

    def test_size_1_ansi_first_middle(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"red"
        size = 1
        expected = self.termnfo.fore_blue+"1"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_2_ansi_first_middle(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"red"
        size = 2
        expected = self.termnfo.fore_blue+"12"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_3_ansi_first_middle(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"red"
        size = 3
        expected = self.termnfo.fore_blue+"123"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_4_ansi_first_middle(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"
        size = 4
        expected = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"4"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_5_ansi_first_middle(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"
        size = 5
        expected = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"45"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_6_ansi_first_middle(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"
        size = 6
        expected = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_exceed_ansi_first_middle(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"
        size = 1000
        expected = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), 6, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_0_ansi_first_middle_last(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"red"+self.termnfo.fore_green
        size = 0
        expected = ""
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, False),
                         ansi_string_truncinfo(fixture, size))

    def test_size_1_ansi_first_middle_last(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"red"+self.termnfo.fore_green
        size = 1
        expected = self.termnfo.fore_blue+"1"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_2_ansi_first_middle_last(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"red"+self.termnfo.fore_green
        size = 2
        expected = self.termnfo.fore_blue+"12"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_3_ansi_first_middle_last(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"red"+self.termnfo.fore_green
        size = 3
        expected = self.termnfo.fore_blue+"123"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_4_ansi_first_middle_last(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"+self.termnfo.fore_green
        size = 4
        expected = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"4"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_5_ansi_first_middle_last(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"+self.termnfo.fore_green
        size = 5
        expected = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"45"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_6_ansi_first_middle_last(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"+self.termnfo.fore_green
        size = 6
        expected = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_7_ansi_first_middle_last(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"+self.termnfo.fore_green
        size = 7
        expected = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"+self.termnfo.fore_green
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), 6, True),
                         ansi_string_truncinfo(fixture, size))

    def test_size_exceed_ansi_first_middle_last(self):
        fixture = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"+self.termnfo.fore_green
        size = 1000
        expected = self.termnfo.fore_blue+"123"+self.termnfo.fore_red+"456"+self.termnfo.fore_green
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), 6, True),
                         ansi_string_truncinfo(fixture, size))

    def test_use_case(self):
        fixture = "[ 50%|253.71|"+self.termnfo.fore_green+"2"+self.termnfo.reset_all+"|"+self.termnfo.fore_red+"0"+self.termnfo.reset_all+"|"+self.termnfo.fore_magenta+"0"+self.termnfo.reset_all+"|"+self.termnfo.fore_blue+"0"+self.termnfo.reset_all+"|"+self.termnfo.fore_yellow+"0"+self.termnfo.reset_all+"|"+self.termnfo.fore_cyan+"0"+self.termnfo.reset_all+"]"+self.termnfo.fore_green+" SUCCESS "+self.termnfo.reset_all+": testtest.test_allgood.Case1.test_success2 (0:00:00.252080)"
        size = 50
        expected = "[ 50%|253.71|"+self.termnfo.fore_green+"2"+self.termnfo.reset_all+"|"+self.termnfo.fore_red+"0"+self.termnfo.reset_all+"|"+self.termnfo.fore_magenta+"0"+self.termnfo.reset_all+"|"+self.termnfo.fore_blue+"0"+self.termnfo.reset_all+"|"+self.termnfo.fore_yellow+"0"+self.termnfo.reset_all+"|"+self.termnfo.fore_cyan+"0"+self.termnfo.reset_all+"]"+self.termnfo.fore_green+" SUCCESS "+self.termnfo.reset_all+": testtest.test_"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))
