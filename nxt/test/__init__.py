# Builtin
import os
import inspect

# NOTE: the behavior of inspect.currentframe() likely requires cpython.
# https://docs.python.org/2.7/library/inspect.html#inspect.currentframe
_this_file = inspect.getframeinfo(inspect.currentframe()).filename
TEST_DIR = os.path.dirname(os.path.abspath(_this_file))


def get_test_file_path(file_name):
    """Shortcut to get full path to desired test file.

    Only assembles path, no validation.

    :param file_name: Filename of testing file.
    :type file_name: str
    :return: Full path for given file name.
    :rtype: str
    """
    return os.path.join(TEST_DIR, file_name)
