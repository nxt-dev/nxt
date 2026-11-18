"""A session's log file is let go of when the session is done.

Every session logs to its own file through a handler on the nxt logger.
Nothing took that handler off again for the one off session made by
nxt.execute_graph, so an interpreter that ran graphs one after another, a
build button in a DCC for instance, kept one more log file open per run and
wrote every line of every later run to all of them.
"""
# Built-in
import json
import logging
import os
import shutil
import tempfile
import unittest

# Internal
import nxt
from nxt import nxt_log
from nxt.session import Session
from nxt.test import get_test_file_path

RUN_COUNT = 3


class SessionLog(unittest.TestCase):
    graph_path = get_test_file_path('StageRuntimeScope.nxt')

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nxt_session_log_')
        # Keep the session logs and the meta log that lists them out of the
        # real temp and user folders.
        self.real_dirs = (nxt_log.LOG_DIR, nxt_log.USER_DIR)
        nxt_log.LOG_DIR = os.path.join(self.tmp, 'logs')
        nxt_log.USER_DIR = self.tmp
        with open(os.path.join(self.tmp, '.nxt_meta_log'), 'w'):
            pass
        # Remember every handler a session makes.
        self.made_handlers = []
        self.real_make_session_log = nxt_log.make_session_log

        def make_session_log(filename=None):
            filename = self.real_make_session_log(filename)
            self.made_handlers.append(nxt_log.SESSION_LOG_HANDLERS[filename])
            return filename
        nxt_log.make_session_log = make_session_log
        self.nxt_logger = logging.getLogger('nxt')
        self.handlers_before = list(self.nxt_logger.handlers)
        self.tracked_before = dict(nxt_log.SESSION_LOG_HANDLERS)

    def tearDown(self):
        nxt_log.make_session_log = self.real_make_session_log
        nxt_log.LOG_DIR, nxt_log.USER_DIR = self.real_dirs
        # Whatever a failing test left behind must not reach the other tests.
        for handler in self.made_handlers:
            self.nxt_logger.removeHandler(handler)
            handler.close()
        nxt_log.SESSION_LOG_HANDLERS.clear()
        nxt_log.SESSION_LOG_HANDLERS.update(self.tracked_before)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_failing_graph(self):
        path = os.path.join(self.tmp, 'failing.nxt')
        data = {
            "version": "1.17",
            "alias": "failing",
            "mute": False,
            "solo": False,
            "meta_data": {},
            "nodes": {
                "/fail": {
                    "start_point": True,
                    "code": ["raise RuntimeError('This node always fails')"]
                }
            },
        }
        with open(path, 'w') as file_object:
            json.dump(data, file_object, indent=4)
        return path

    def assert_nothing_left(self):
        self.assertEqual(len(self.handlers_before),
                         len(self.nxt_logger.handlers))
        self.assertEqual(self.handlers_before, self.nxt_logger.handlers)
        self.assertEqual(self.tracked_before, nxt_log.SESSION_LOG_HANDLERS)
        still_open = [h for h in self.made_handlers if h.stream is not None]
        self.assertEqual([], still_open)

    def test_execute_graph_leaves_no_handler(self):
        for _ in range(RUN_COUNT):
            nxt.execute_graph(self.graph_path)
        self.assertEqual(RUN_COUNT, len(self.made_handlers))
        self.assert_nothing_left()
        # Nothing holds the log files, so they can be deleted (on Windows an
        # open file can not).
        shutil.rmtree(nxt_log.LOG_DIR)
        self.assertFalse(os.path.exists(nxt_log.LOG_DIR))

    def test_failing_graph_leaves_no_handler(self):
        graph_path = self.write_failing_graph()
        # The failure is logged, and this test causes it on purpose.
        propagate = self.nxt_logger.propagate
        self.nxt_logger.propagate = False
        try:
            for _ in range(RUN_COUNT):
                with self.assertRaises(Exception):
                    nxt.execute_graph(graph_path)
        finally:
            self.nxt_logger.propagate = propagate
        self.assertEqual(RUN_COUNT, len(self.made_handlers))
        self.assert_nothing_left()

    def test_session_logs_until_closed(self):
        session = Session()
        handler = self.made_handlers[0]
        # Running a graph does not end the session's log.
        session.execute_graph(self.graph_path)
        self.assertIn(handler, self.nxt_logger.handlers)
        self.assertIs(handler,
                      nxt_log.SESSION_LOG_HANDLERS[session.log_file])
        self.nxt_logger.error('written while the session is open')
        handler.flush()
        with open(session.log_file, 'r') as file_object:
            self.assertIn('written while the session is open',
                          file_object.read())
        session.close()
        self.assert_nothing_left()
        self.nxt_logger.error('written after the session closed')
        with open(session.log_file, 'r') as file_object:
            self.assertNotIn('written after the session closed',
                             file_object.read())
        # Closing again is harmless.
        session.close()
        self.assert_nothing_left()

    def test_stop_session_log(self):
        session = Session()
        nxt_log.stop_session_log(session.log_file)
        self.assert_nothing_left()
        # Neither a second call nor an unknown file is an error.
        nxt_log.stop_session_log(session.log_file)
        nxt_log.stop_session_log(os.path.join(self.tmp, 'not_a_log.log'))
        self.assert_nothing_left()


if __name__ == '__main__':
    unittest.main()
