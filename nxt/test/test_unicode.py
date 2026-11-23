# -*- coding: utf-8 -*-
"""Graphs can be written in any language.

Node names, attribute names and values, comments and code can hold letters
from any script, and so can the folders and files a graph lives in. Files
are read and written as UTF-8 whatever the system's own encoding is, which
on Windows is not UTF-8. A graph saved by another tool with the characters
written out, rather than escaped the way nxt saves them, opens too, as do
files with a byte order mark and older files in the system's encoding.
"""
# Builtin
import io
import json
import locale
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

# Internal
import nxt
from nxt import nxt_io, nxt_log
from nxt.session import Session

#: A word in each of several scripts, and a name that python accepts for
#: each, so they can be node and attribute names too.
WORDS = {
    'chinese': u'中文', 'japanese': u'日本語', 'korean': u'한국어',
    'russian': u'Русский', 'greek': u'Ελληνικά', 'arabic': u'عربي',
    'hindi': u'हिन्दी', 'accents': u'Ñandú_çà', 'emoji': u'smile😀',
}
NAMES = [u'节点', u'ノード', u'노드', u'узел', u'κόμβος', u'عقدة', u'Ñandú']


def write_json(path, data, ascii_only=False):
    """Write a graph the way another tool might: the characters as they are,
    in UTF-8, unless ascii_only, which is how nxt itself saves."""
    with io.open(path, 'w', encoding='utf-8') as fp:
        fp.write(json.dumps(data, ensure_ascii=ascii_only, indent=4))
    return path


def graph_data(out_path):
    """A graph with a node per name, each writing its words to out_path."""
    nodes = {'/': {'attrs': {'out': {'value': repr(out_path)}}}}
    previous = None
    for index, name in enumerate(NAMES):
        attrs = {u'名字_{}'.format(index): {'value': repr(name),
                                           'comment': u'属性说明 ' + name}}
        node = {'comment': u'注释 ' + name, 'attrs': attrs,
                'code': [u'# ' + u' '.join(WORDS.values()),
                         u"with open(${out}, 'a', encoding='utf-8') as fp:",
                         u"    fp.write(${{名字_{}}} + '\\n')".format(index)]}
        if previous:
            node['execute_in'] = previous
        else:
            node['start_point'] = True
        nodes[u'/' + name] = node
        previous = u'/' + name
    return {'version': '1.17', 'alias': u'图', 'nodes': nodes}


class AnyLanguage(unittest.TestCase):

    def setUp(self):
        # A folder with a name outside English, as many people's are.
        root = tempfile.mkdtemp(prefix='nxt_unicode_')
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.dir = os.path.join(root, u'项目 Проект')
        os.makedirs(self.dir)
        self.out = os.path.join(self.dir, u'输出.txt').replace(os.sep, '/')

    def written(self):
        with io.open(self.out, encoding='utf-8') as fp:
            return fp.read().split()

    def test_a_graph_with_the_characters_written_out_opens_and_runs(self):
        path = write_json(os.path.join(self.dir, u'图表.nxt'),
                          graph_data(self.out))
        Session().execute_graph(path)
        self.assertEqual(NAMES, self.written())

    def test_a_graph_nxt_saved_opens_and_runs(self):
        path = write_json(os.path.join(self.dir, u'escaped.nxt'),
                          graph_data(self.out), ascii_only=True)
        Session().execute_graph(path)
        self.assertEqual(NAMES, self.written())

    def test_names_and_values_survive_a_save(self):
        source = write_json(os.path.join(self.dir, u'图表.nxt'),
                            graph_data(self.out))
        stage = Session().load_file(source)
        layer = stage.top_layer
        saved = os.path.join(self.dir, u'保存.nxt')
        nxt_io.save_file_data(layer.get_save_data(), saved)
        again = nxt_io.load_file_data(saved)
        for name in NAMES:
            self.assertIn(u'/' + name, again['nodes'])
            self.assertIn(u'注释 ' + name,
                          again['nodes'][u'/' + name]['comment'])
        # Saved escaped, so any reader can open it, whatever its encoding.
        with open(saved, 'rb') as fp:
            fp.read().decode('ascii')

    def test_a_byte_order_mark_is_fine(self):
        path = os.path.join(self.dir, u'bom.nxt')
        data = json.dumps(graph_data(self.out), ensure_ascii=False)
        with open(path, 'wb') as fp:
            fp.write(u'﻿'.encode('utf-8') + data.encode('utf-8'))
        Session().execute_graph(path)
        self.assertEqual(NAMES, self.written())

    def test_a_file_in_the_systems_own_encoding_still_opens(self):
        encoding = locale.getpreferredencoding(False)
        try:
            u'é'.encode(encoding)
        except UnicodeEncodeError:
            self.skipTest('{} has no é'.format(encoding))
        if u'é'.encode(encoding) == u'é'.encode('utf-8'):
            self.skipTest('the system encoding is UTF-8 already')
        path = os.path.join(self.dir, u'old.nxt')
        data = {'version': '1.17', 'alias': 'old', 'nodes': {
            '/node': {'comment': u'café'}}}
        with open(path, 'wb') as fp:
            fp.write(json.dumps(data, ensure_ascii=False).encode(encoding))
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)
        loaded = nxt_io.load_file_data(path)
        self.assertEqual(u'café', loaded['nodes']['/node']['comment'])

    def test_a_file_token_reads_any_language(self):
        text_file = os.path.join(self.dir, u'内容.txt')
        with io.open(text_file, 'w', encoding='utf-8') as fp:
            fp.write(u'привет 你好')
        data = {'version': '1.17', 'alias': 'contents', 'nodes': {
            '/': {'attrs': {'out': {'value': repr(self.out)}}},
            '/node': {'start_point': True, 'attrs': {
                'text': {'value': u'${contents::' +
                         text_file.replace(os.sep, '/') + u'}'}},
                'code': [u"with open(${out}, 'w', encoding='utf-8') as fp:",
                         u"    fp.write('''${text}''')"]}}}
        path = write_json(os.path.join(self.dir, u'contents.nxt'), data)
        Session().execute_graph(path)
        self.assertEqual([u'привет', u'你好'], self.written())

    def test_parameters_from_a_file_in_any_language(self):
        path = write_json(os.path.join(self.dir, u'图表.nxt'),
                          graph_data(self.out))
        params = os.path.join(self.dir, u'参数.json')
        with open(params, 'wb') as fp:
            # A byte order mark, as Windows tools often write one.
            fp.write(u'﻿'.encode('utf-8') + json.dumps(
                {u'/节点.名字_0': repr(u'Привет')},
                ensure_ascii=False).encode('utf-8'))
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        # This nxt, wherever the tests before this one left the working
        # directory.
        root = os.path.dirname(os.path.dirname(os.path.abspath(nxt.__file__)))
        env['PYTHONPATH'] = os.pathsep.join(
            [root] + [p for p in [env.get('PYTHONPATH')] if p])
        subprocess.check_call([sys.executable, '-m', 'nxt.cli', 'exec',
                               path, '-p', params], env=env, cwd=root,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
        self.assertEqual([u'Привет'] + NAMES[1:], self.written())

    def test_the_session_log_takes_any_language(self):
        log_path = os.path.join(self.dir, u'日志.nxtlog')
        nxt_log.make_session_log(log_path)
        self.addCleanup(nxt_log.stop_session_log, log_path)
        logging.getLogger('nxt').warning(u'Added node: /节点 😀')
        for handler in logging.getLogger('nxt').handlers:
            handler.flush()
        with io.open(log_path, encoding='utf-8') as fp:
            self.assertIn(u'/节点 😀', fp.read())


if __name__ == '__main__':
    unittest.main()
