# -*- encoding: utf-8 -*-
"""Test "hunittest.line_printer" package.
"""

import unittest

try:
    from colorama import Fore
except ImportError:
    HAS_COLORAMA = False
else:
    HAS_COLORAMA = True

from hunittest.line_printer import truncate_ansi_string
from hunittest.line_printer import ansi_string_truncinfo


class TestTruncateAnsiString(unittest.TestCase):

    # def setUp(self):
    #     self.normal = "foobarblue"
    #     self.normal_ansi = "foo"+Fore.GREEN+"bar"+Fore.BLUE+"blue"+Fore.RESET
    #     self.ansi_ansi = \
    #         Fore.RED+"foo"+Fore.GREEN+"bar"+Fore.BLUE+"blue"+Fore.RESET
    #     self.ansi_normal = Fore.RED+"foo"+Fore.GREEN+"bar"+Fore.BLUE+"blue"

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

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_0_ansi_first(self):
        fixture = Fore.RED+"text"
        size = 0
        expected = ""
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((0, 0, False),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_1_ansi_first(self):
        fixture = Fore.RED+"text"
        size = 1
        expected = Fore.RED+"t"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), 1, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_2_ansi_first(self):
        fixture = Fore.RED+"text"
        size = 2
        expected = Fore.RED+"te"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_3_ansi_first(self):
        fixture = Fore.RED+"text"
        size = 3
        expected = Fore.RED+"tex"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_exceed_ansi_first(self):
        fixture = Fore.RED+"text"
        expected = Fore.RED+"text"
        actual = truncate_ansi_string(fixture, 4000)
        self.assertEqual(expected, actual)

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_0_ansi_middle(self):
        fixture = "123"+Fore.RED+"red"
        size = 0
        expected = ""
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, False),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_1_ansi_middle(self):
        fixture = "123"+Fore.RED+"red"
        size = 1
        expected = "1"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, False),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_2_ansi_middle(self):
        fixture = "123"+Fore.RED+"red"
        size = 2
        expected = "12"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, False),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_3_ansi_middle(self):
        fixture = "123"+Fore.RED+"red"
        size = 3
        expected = "123"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, False),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_4_ansi_middle(self):
        fixture = "123"+Fore.RED+"456"
        size = 4
        expected = "123"+Fore.RED+"4"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_5_ansi_middle(self):
        fixture = "123"+Fore.RED+"456"
        size = 5
        expected = "123"+Fore.RED+"45"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_6_ansi_middle(self):
        fixture = "123"+Fore.RED+"456"
        size = 6
        expected = "123"+Fore.RED+"456"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_exceed_ansi_middle(self):
        fixture = "123"+Fore.RED+"456"
        size = 10000
        expected = "123"+Fore.RED+"456"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), 6, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_0_ansi_first_middle(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"red"
        size = 0
        expected = ""
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, False),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_1_ansi_first_middle(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"red"
        size = 1
        expected = Fore.BLUE+"1"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_2_ansi_first_middle(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"red"
        size = 2
        expected = Fore.BLUE+"12"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_3_ansi_first_middle(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"red"
        size = 3
        expected = Fore.BLUE+"123"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_4_ansi_first_middle(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"456"
        size = 4
        expected = Fore.BLUE+"123"+Fore.RED+"4"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_5_ansi_first_middle(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"456"
        size = 5
        expected = Fore.BLUE+"123"+Fore.RED+"45"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_6_ansi_first_middle(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"456"
        size = 6
        expected = Fore.BLUE+"123"+Fore.RED+"456"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_exceed_ansi_first_middle(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"456"
        size = 1000
        expected = Fore.BLUE+"123"+Fore.RED+"456"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), 6, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_0_ansi_first_middle_last(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"red"+Fore.GREEN
        size = 0
        expected = ""
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, False),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_1_ansi_first_middle_last(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"red"+Fore.GREEN
        size = 1
        expected = Fore.BLUE+"1"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_2_ansi_first_middle_last(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"red"+Fore.GREEN
        size = 2
        expected = Fore.BLUE+"12"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_3_ansi_first_middle_last(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"red"+Fore.GREEN
        size = 3
        expected = Fore.BLUE+"123"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_4_ansi_first_middle_last(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"456"+Fore.GREEN
        size = 4
        expected = Fore.BLUE+"123"+Fore.RED+"4"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_5_ansi_first_middle_last(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"456"+Fore.GREEN
        size = 5
        expected = Fore.BLUE+"123"+Fore.RED+"45"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_6_ansi_first_middle_last(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"456"+Fore.GREEN
        size = 6
        expected = Fore.BLUE+"123"+Fore.RED+"456"
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), size, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_7_ansi_first_middle_last(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"456"+Fore.GREEN
        size = 7
        expected = Fore.BLUE+"123"+Fore.RED+"456"+Fore.GREEN
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), 6, True),
                         ansi_string_truncinfo(fixture, size))

    @unittest.skipUnless(HAS_COLORAMA, "colorama is not installed")
    def test_size_exceed_ansi_first_middle_last(self):
        fixture = Fore.BLUE+"123"+Fore.RED+"456"+Fore.GREEN
        size = 1000
        expected = Fore.BLUE+"123"+Fore.RED+"456"+Fore.GREEN
        actual = truncate_ansi_string(fixture, size)
        self.assertEqual(expected, actual)
        self.assertEqual((len(expected), 6, True),
                         ansi_string_truncinfo(fixture, size))
