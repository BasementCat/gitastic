import unittest
import sys
import os
import StringIO
# import subprocess
# import threading
# import socket
# import time
# import tempfile
# import shutil
# import copy
# import getpass
# import signal
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "gitastic"))
from lib import shellutils

class MockSys(object):
    stderr=StringIO.StringIO()
    stdin=StringIO.StringIO("Test Standard Input")
    stdout=StringIO.StringIO()
    _exit_code=None

    @classmethod
    def exit(self, code=0):
        self._exit_code=code

    @classmethod
    def reset(self):
        self.stderr.close()
        self.stdin.close()
        self.stdout.close()
        self.stderr=StringIO.StringIO()
        self.stdin=StringIO.StringIO("Test Standard Input")
        self.stdout=StringIO.StringIO()
        self._exit_code=None

class MockRawInput_Base(object):
    def __init__(self):
        self.prompt=None
        self.values=["Test Raw Input", "Test Raw Input 2"]
        self.calls=0

    def __call__(self, prompt=None):
        self.prompt=prompt
        if self.calls>=len(self.values):
            self.calls=0
        out=self.values[self.calls]
        self.calls+=1
        return out

    def reset(self):
        self.prompt=None
        self.values=["Test Raw Input", "Test Raw Input 2"]
        self.calls=0

MockRawInput=MockRawInput_Base()

class TestShellUtils(unittest.TestCase):
    def setUp(self):
        if shellutils.sys is not MockSys:
            shellutils.sys=MockSys
        MockSys.reset()
        if not hasattr(shellutils, "raw_input") or shellutils.raw_input is not MockRawInput:
            shellutils.raw_input=MockRawInput
        MockRawInput.reset()

    def tearDown(self):
        MockSys.reset()
        MockRawInput.reset()

    def test_DieWithMessage(self):
        shellutils.die("TestMessage")
        self.assertEqual(MockSys.stderr.getvalue(), "TestMessage\n")
        self.assertEqual(MockSys._exit_code, 1)

    def test_DieWithMessage_interpolation(self):
        shellutils.die("TestMessage %s #%d", "Hello world", 7)
        self.assertEqual(MockSys.stderr.getvalue(), "TestMessage Hello world #7\n")
        self.assertEqual(MockSys._exit_code, 1)

    def test_DieWithMessage_code(self):
        shellutils.die("TestMessage", code=25)
        self.assertEqual(MockSys.stderr.getvalue(), "TestMessage\n")
        self.assertEqual(MockSys._exit_code, 25)

    def test_DieWithMessage_interpolation_code(self):
        shellutils.die("TestMessage %s #%d", "Hello", 12, code=9)
        self.assertEqual(MockSys.stderr.getvalue(), "TestMessage Hello #12\n")
        self.assertEqual(MockSys._exit_code, 9)

# def get_input(prompt=None, default=None, require=False, restrict=None):

    def test_input_noprompt(self):
        var=shellutils.get_input()
        self.assertEqual(MockRawInput.prompt, "")
        self.assertEqual(var, "Test Raw Input")

    def test_input_prompt(self):
        var=shellutils.get_input("Test Prompt")
        self.assertEqual(MockRawInput.prompt, "Test Prompt: ")
        self.assertEqual(var, "Test Raw Input")

    def test_input_default(self):
        MockRawInput.values=[""]
        var=shellutils.get_input("Test Prompt", default="Hello world")
        self.assertEqual(MockRawInput.prompt, "Test Prompt [Hello world]: ")
        self.assertEqual(var, "Hello world")

    def test_input_require(self):
        MockRawInput.values=["", "Test asdfasd"]
        var=shellutils.get_input("Test Prompt", require=True)
        self.assertEqual(MockRawInput.prompt, "Test Prompt: ")
        self.assertEqual(var, "Test asdfasd")
        self.assertEqual(MockSys.stderr.getvalue(), "An answer is required\n")

    def test_input_restrict(self):
        MockRawInput.values=["baz", "", "bar"]
        var=shellutils.get_input("Test Prompt", require=True, restrict=["foo", "bar"])
        self.assertEqual(MockRawInput.prompt, "Test Prompt (foo,bar): ")
        self.assertEqual(var, "bar")
        self.assertEqual(MockSys.stderr.getvalue(), "Answer must be one of foo, bar\nAn answer is required\n")

    def test_input_restrict_default(self):
        MockRawInput.values=["baz", "", "bar"]
        var=shellutils.get_input("Test Prompt", require=True, restrict=["foo", "bar"], default="foo")
        self.assertEqual(MockRawInput.prompt, "Test Prompt (foo,bar) [foo]: ")
        self.assertEqual(var, "foo")
        self.assertEqual(MockSys.stderr.getvalue(), "Answer must be one of foo, bar\n")

if __name__ == '__main__':
    unittest.main()