"""Circular instance and execute in paths are reported and broken.

A node whose instance chain leads back to itself, or to one of its
ancestors, would have to contain itself. Comping one used to either loop
forever making proxies or give up part way through with an inheritance
error. Execute in cycles used to loop forever when finding the run order.
"""
# Builtin
import json
import logging
import os
import shutil
import tempfile
import threading
import unittest

# Internal
from nxt.session import Session
from nxt.nxt_node import INTERNAL_ATTRS

INST = INTERNAL_ATTRS.INSTANCE_PATH
INST_KEY = INTERNAL_ATTRS.as_save_key(INST)
EXEC_KEY = INTERNAL_ATTRS.as_save_key(INTERNAL_ATTRS.EXECUTE_IN)
ATTRS_KEY = 'attrs'


class ErrorCatcher(logging.Handler):
    def __init__(self):
        super(ErrorCatcher, self).__init__(logging.ERROR)
        self.messages = []

    def emit(self, record):
        self.messages += [record.getMessage()]


class CircularPathsBase(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.errors = ErrorCatcher()
        logging.getLogger('nxt').addHandler(self.errors)

    def tearDown(self):
        logging.getLogger('nxt').removeHandler(self.errors)
        shutil.rmtree(self.folder, ignore_errors=True)

    def load(self, nodes):
        path = os.path.join(self.folder, 'graph.nxt')
        with open(path, 'w') as f:
            json.dump({'version': '1.17', 'alias': 'graph', 'nodes': nodes},
                      f)
        return Session().load_file(path)

    def run_with_timeout(self, func, seconds=30):
        """Runs func in a thread so a regression fails instead of hanging."""
        result = {}

        def target():
            result['value'] = func()
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(seconds)
        self.assertFalse(thread.is_alive(), 'Never finished, stuck in a loop')
        return result['value']

    def cycle_errors(self):
        return [m for m in self.errors.messages if m.startswith('Circular')]


class CircularInstances(CircularPathsBase):

    def instance(self, comp, path):
        return getattr(comp.lookup(path), INST, None)

    def test_direct_cycle_is_reported_and_broken(self):
        stage = self.load({'/N1': {INST_KEY: '/N2'},
                           '/N2': {INST_KEY: '/N1',
                                   ATTRS_KEY: {'x': {'value': '1'}}}})
        comp = self.run_with_timeout(stage.build_stage)
        self.assertFalse(comp.failure)
        self.assertEqual(['Circular instance: /N1 -> /N2 -> /N1. Ignoring '
                          'the instance path on /N1.'], self.cycle_errors())
        self.assertIsNone(self.instance(comp, '/N1'))
        self.assertEqual('/N1', self.instance(comp, '/N2'))
        # The saved opinion is untouched
        spec = stage.top_layer.lookup('/N1')
        self.assertEqual('/N2', getattr(spec, INST))

    def test_longer_cycle_is_broken_once(self):
        stage = self.load({'/A': {INST_KEY: '/B'},
                           '/B': {INST_KEY: '/C'},
                           '/C': {INST_KEY: '/A'}})
        comp = self.run_with_timeout(stage.build_stage)
        self.assertFalse(comp.failure)
        self.assertEqual(1, len(self.cycle_errors()))
        self.assertIsNone(self.instance(comp, '/A'))
        self.assertEqual('/C', self.instance(comp, '/B'))

    def test_instancing_a_node_that_holds_you_does_not_hang(self):
        stage = self.load({'/A': {INST_KEY: '/B'},
                           '/B': {},
                           '/B/c': {INST_KEY: '/A'}})
        comp = self.run_with_timeout(stage.build_stage)
        self.assertFalse(comp.failure)
        self.assertEqual(['Circular instance: /B/c -> /A -> /B. Ignoring '
                          'the instance path on /B/c.'], self.cycle_errors())
        self.assertIsNone(self.instance(comp, '/B/c'))
        self.assertEqual('/B/c', self.instance(comp, '/A/c'))
        self.assertEqual(['/A', '/A/c', '/B', '/B/c'],
                         sorted(comp._nodes_path_as_key))

    def test_relative_cycle_is_caught(self):
        stage = self.load({'/A': {INST_KEY: '../B'},
                           '/B': {},
                           '/B/c': {INST_KEY: '../../A'}})
        comp = self.run_with_timeout(stage.build_stage)
        self.assertFalse(comp.failure)
        self.assertEqual(1, len(self.cycle_errors()))

    def test_good_instances_are_untouched(self):
        stage = self.load({'/A': {INST_KEY: '/B'},
                           '/B': {},
                           '/B/c': {INST_KEY: '/D'},
                           '/D': {}})
        comp = self.run_with_timeout(stage.build_stage)
        self.assertEqual([], self.cycle_errors())
        self.assertEqual('/B', self.instance(comp, '/A'))
        self.assertEqual('/D', self.instance(comp, '/B/c'))

    def set_instance(self, stage, comp, path, value):
        node = stage.top_layer.lookup(path)
        return stage.node_setattr_data(node, INST, stage.top_layer,
                                       create=True, comp_layer=comp,
                                       value=value)

    def test_setting_a_circular_instance_on_a_comp(self):
        stage = self.load({'/N1': {INST_KEY: '/N2'}, '/N2': {}})
        comp = stage.build_stage()
        self.run_with_timeout(
            lambda: self.set_instance(stage, comp, '/N2', '/N1'))
        self.assertEqual(1, len(self.cycle_errors()))
        self.assertIsNone(self.instance(comp, '/N2'))
        self.assertEqual('/N2', self.instance(comp, '/N1'))
        spec = stage.top_layer.lookup('/N2')
        self.assertEqual('/N1', getattr(spec, INST))

    def test_setting_an_instance_that_closes_a_cycle_below(self):
        stage = self.load({'/A': {}, '/B': {}, '/B/c': {INST_KEY: '/A'}})
        comp = stage.build_stage()
        self.run_with_timeout(
            lambda: self.set_instance(stage, comp, '/A', '/B'))
        self.assertEqual(1, len(self.cycle_errors()))
        self.assertIsNone(self.instance(comp, '/A'))
        self.assertEqual('/A', self.instance(comp, '/B/c'))


class CircularExecuteIn(CircularPathsBase):

    def test_execute_in_cycle_stops(self):
        stage = self.load({'/R1': {EXEC_KEY: '/R2'},
                           '/R2': {EXEC_KEY: '/R1'}})
        comp = stage.build_stage()
        order = self.run_with_timeout(lambda: comp.get_exec_order('/R1'))
        self.assertEqual(['/R1', '/R2'], order)
        self.assertEqual(1, len(self.cycle_errors()))

    def test_execute_in_itself_stops(self):
        stage = self.load({'/R1': {EXEC_KEY: '/R1'}})
        comp = stage.build_stage()
        order = self.run_with_timeout(lambda: comp.get_exec_order('/R1'))
        self.assertEqual(['/R1'], order)
