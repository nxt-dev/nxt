"""Env files set environment variables as nxt starts.

A graph that references `$PROJECT_GRAPHS/rig.nxt` only loads where that
variable is set, and it has to be set everywhere nxt starts from. An env
file says it once, beside the project, and nxt applies it on import.

What these tests hold it to: a variable set outside nxt is never replaced,
a file can be edited and applied again in a running session, a file can
travel with its project, and a broken file is skipped rather than raised.
"""
# Builtin
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

# Internal
from nxt import env_files


def write(path, variables=None, include=None, **extra):
    data = dict(extra)
    if include is not None:
        data['include'] = include
    if variables is not None:
        data['variables'] = variables
    with open(path, 'w') as file_object:
        json.dump(data, file_object)
    return path


class EnvFilesCase(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix='nxt_env_')
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        # A private environment and a private memory of what was applied,
        # so nothing here leaks into the process or into another test.
        environ = mock.patch.dict(os.environ, clear=False)
        environ.start()
        self.addCleanup(environ.stop)
        # And temporary user and site files, never the real ones.
        for patch in (mock.patch.object(env_files, '_applied', {}),
                      mock.patch.object(env_files, '_declared', []),
                      mock.patch.object(env_files, 'USER_ENV_FILE',
                                        self.path('user/env.json')),
                      mock.patch.object(env_files, 'SITE_ENV_FILE',
                                        self.path('site/env.json'))):
            patch.start()
            self.addCleanup(patch.stop)
        for name in ('NXT_T_A', 'NXT_T_B', 'NXT_T_ROOTS',
                     env_files.ENV_FILES_ENV_VAR):
            os.environ.pop(name, None)

    def path(self, name):
        return os.path.join(self.folder, name)

    def directory(self):
        return self.folder.replace(os.sep, '/')


class ApplyingAFile(EnvFilesCase):

    def test_sets_what_the_file_says(self):
        env = write(self.path('env.json'), {'NXT_T_A': 'one'})
        result, problems = env_files.apply([env])
        self.assertEqual('one', os.environ['NXT_T_A'])
        self.assertEqual(('one', os.path.abspath(env)), result['NXT_T_A'])
        self.assertEqual([], problems)

    def test_a_list_is_joined_with_the_path_separator(self):
        env = write(self.path('env.json'), {'NXT_T_ROOTS': ['/a', '/b']})
        env_files.apply([env])
        self.assertEqual(os.pathsep.join(['/a', '/b']),
                         os.environ['NXT_T_ROOTS'])

    def test_the_files_own_folder(self):
        # This is what lets the file be committed beside the graphs.
        env = write(self.path('env.json'), {
            'NXT_T_A': '$NXT_ENV_FILE_DIR/graphs',
            'NXT_T_B': '${NXT_ENV_FILE_DIR}/more'})
        env_files.apply([env])
        self.assertEqual(self.directory() + '/graphs', os.environ['NXT_T_A'])
        self.assertEqual(self.directory() + '/more', os.environ['NXT_T_B'])

    def test_a_value_can_build_on_one_above_it(self):
        env = write(self.path('env.json'), {})
        with open(env, 'w') as file_object:
            # Written by hand: the order in the file is the order applied.
            file_object.write('{"variables": {"NXT_T_A": "/root", '
                              '"NXT_T_B": "$NXT_T_A/child"}}')
        env_files.apply([env])
        self.assertEqual('/root/child', os.environ['NXT_T_B'])

    def test_numbers_are_text(self):
        env = write(self.path('env.json'), {'NXT_T_A': 3})
        env_files.apply([env])
        self.assertEqual('3', os.environ['NXT_T_A'])


class WhoHasTheLastWord(EnvFilesCase):

    def test_a_variable_set_outside_is_left_alone(self):
        os.environ['NXT_T_A'] = 'from the launcher'
        env = write(self.path('env.json'), {'NXT_T_A': 'from the file'})
        result, _ = env_files.apply([env])
        self.assertEqual('from the launcher', os.environ['NXT_T_A'])
        self.assertNotIn('NXT_T_A', result)

    def test_a_later_file_wins(self):
        first = write(self.path('first.json'), {'NXT_T_A': 'first'})
        second = write(self.path('second.json'), {'NXT_T_A': 'second'})
        result, _ = env_files.apply([first, second])
        self.assertEqual('second', os.environ['NXT_T_A'])
        self.assertEqual(os.path.abspath(second), result['NXT_T_A'][1])

    def test_the_including_file_wins_over_what_it_includes(self):
        write(self.path('shared.json'), {'NXT_T_A': 'shared',
                                         'NXT_T_B': 'shared'})
        mine = write(self.path('mine.json'), {'NXT_T_A': 'mine'},
                     include=['shared.json'])
        env_files.apply([mine])
        self.assertEqual('mine', os.environ['NXT_T_A'])
        self.assertEqual('shared', os.environ['NXT_T_B'])

    def test_files_named_in_the_environment_are_read_last(self):
        extra = write(self.path('extra.json'), {'NXT_T_A': 'extra'})
        os.environ[env_files.ENV_FILES_ENV_VAR] = extra
        files = env_files.start_files()
        self.assertEqual(extra, files[-1])
        self.assertIn(env_files.USER_ENV_FILE, files)


class ApplyingAgain(EnvFilesCase):
    """What the editor does after a file is edited."""

    def test_an_edited_value_is_updated(self):
        env = write(self.path('env.json'), {'NXT_T_A': 'before'})
        env_files.apply([env])
        write(env, {'NXT_T_A': 'after'})
        env_files.apply([env])
        self.assertEqual('after', os.environ['NXT_T_A'])

    def test_a_removed_variable_is_unset(self):
        env = write(self.path('env.json'), {'NXT_T_A': 'x', 'NXT_T_B': 'y'})
        env_files.apply([env])
        write(env, {'NXT_T_B': 'y'})
        env_files.apply([env])
        self.assertNotIn('NXT_T_A', os.environ)
        self.assertEqual('y', os.environ['NXT_T_B'])

    def test_a_value_changed_by_a_graph_since_is_not_touched(self):
        # Something else set it after nxt did. It is theirs now.
        env = write(self.path('env.json'), {'NXT_T_A': 'file'})
        env_files.apply([env])
        os.environ['NXT_T_A'] = 'set by a node'
        write(env, {})
        env_files.apply([env])
        self.assertEqual('set by a node', os.environ['NXT_T_A'])


class Includes(EnvFilesCase):

    def test_relative_to_the_file(self):
        os.mkdir(self.path('sub'))
        write(self.path('sub/inner.json'), {'NXT_T_A': 'inner'})
        outer = write(self.path('outer.json'), include=['sub/inner.json'])
        env_files.apply([outer])
        self.assertEqual('inner', os.environ['NXT_T_A'])

    def test_two_files_including_each_other_end(self):
        a = write(self.path('a.json'), {'NXT_T_A': 'a'}, include=['b.json'])
        write(self.path('b.json'), {'NXT_T_B': 'b'}, include=['a.json'])
        loaded = env_files.read_files([a])
        self.assertEqual(['b.json', 'a.json'],
                         [os.path.basename(f.path) for f in loaded])

    def test_a_missing_include_is_a_problem_not_an_error(self):
        env = write(self.path('env.json'), {'NXT_T_A': 'x'},
                    include=['nope.json'])
        _, problems = env_files.apply([env])
        self.assertEqual('x', os.environ['NXT_T_A'])
        self.assertEqual(1, len(problems))
        self.assertIn('nope.json', problems[0][0])


class FilesThatCannotBeUsed(EnvFilesCase):

    def test_a_start_file_that_is_not_there_is_fine(self):
        # Nobody has an env file until they make one.
        result, problems = env_files.apply([self.path('none.json')])
        self.assertEqual({}, dict(result))
        self.assertEqual([], problems)

    def test_broken_json_is_skipped_and_said(self):
        bad = self.path('bad.json')
        with open(bad, 'w') as file_object:
            file_object.write('{not json')
        good = write(self.path('good.json'), {'NXT_T_A': 'x'})
        _, problems = env_files.apply([bad, good])
        self.assertEqual('x', os.environ['NXT_T_A'])
        self.assertEqual([bad], [path for path, _ in problems])

    def test_a_value_that_is_not_text(self):
        bad = write(self.path('bad.json'), {'NXT_T_A': {'nested': 1}})
        with self.assertRaises(env_files.EnvFileError):
            env_files.EnvFile.load(bad)

    def test_a_file_from_a_newer_nxt(self):
        newer = write(self.path('newer.json'), {'NXT_T_A': 'x'},
                      version=env_files.FORMAT_VERSION + 1)
        _, problems = env_files.apply([newer])
        self.assertNotIn('NXT_T_A', os.environ)
        self.assertEqual(1, len(problems))


class VariableNames(EnvFilesCase):

    def test_a_longer_name_is_another_variable(self):
        # $NXT_ENV_FILE_DIRX is not the file's folder with an X after it.
        os.environ['NXT_T_B'] = 'b'
        env = write(self.path('env.json'), {
            'NXT_T_A': '$NXT_ENV_FILE_DIRX/a; ${NXT_ENV_FILE_DIR}X; '
                       '$NXT_T_Bc; $NXT_T_B/c'})
        with self.assertLogs(env_files.logger, 'WARNING'):
            env_files.apply([env])
        self.assertEqual('$NXT_ENV_FILE_DIRX/a; {}X; $NXT_T_Bc; b/c'
                         ''.format(self.directory()),
                         os.environ['NXT_T_A'])

    def test_an_unset_variable_is_kept_and_said(self):
        env = write(self.path('env.json'), {'NXT_T_A': '$NXT_T_NOT_SET/b'})
        with self.assertLogs(env_files.logger, 'WARNING') as logs:
            env_files.apply([env])
        self.assertEqual('$NXT_T_NOT_SET/b', os.environ['NXT_T_A'])
        said = '\n'.join(logs.output)
        self.assertIn('NXT_T_NOT_SET', said)
        self.assertIn('NXT_T_A', said)
        self.assertIn(os.path.abspath(env), said)

    def test_an_unset_variable_in_an_include_is_said(self):
        env = write(self.path('env.json'), {'NXT_T_A': 'x'},
                    include=['$NXT_T_NOT_SET/shared.json'])
        with self.assertLogs(env_files.logger, 'WARNING') as logs:
            env_files.apply([env])
        self.assertEqual('x', os.environ['NXT_T_A'])
        self.assertIn('NXT_T_NOT_SET', '\n'.join(logs.output))

    def test_percent_is_only_a_variable_on_windows(self):
        os.environ['NXT_T_B'] = 'b'
        env = write(self.path('env.json'), {
            'NXT_T_A': '%NXT_T_B%/%NXT_ENV_FILE_DIR%'})
        env_files.apply([env])
        first = 'b' if os.name == 'nt' else '%NXT_T_B%'
        self.assertEqual(first + '/' + self.directory(),
                         os.environ['NXT_T_A'])

    def test_what_decides_the_files_cannot_come_from_one(self):
        for name in env_files.NOT_FROM_A_FILE:
            os.environ.pop(name, None)
        env = write(self.path('env.json'), {
            'NXT_USER_DIR': self.path('u'), 'NXT_SITE_DIR': self.path('s'),
            'NXT_ENV_FILES': self.path('more.json'), 'NXT_T_A': 'a'})
        with self.assertLogs(env_files.logger, 'WARNING') as logs:
            result, _ = env_files.apply([env])
        for name in env_files.NOT_FROM_A_FILE:
            self.assertNotIn(name, os.environ)
            self.assertNotIn(name, result)
            self.assertIn(name, '\n'.join(logs.output))
        self.assertEqual('a', os.environ['NXT_T_A'])
        self.assertEqual(['NXT_T_A'], env_files._declared)

    @unittest.skipUnless(os.name == 'nt', 'names only ignore case on '
                                          'Windows')
    def test_case_is_ignored_on_windows(self):
        first = write(self.path('first.json'), {'nxt_t_a': 'first'})
        second = write(self.path('second.json'), {'NXT_T_A': 'second',
                                                  'NXT_T_B': '$nxt_t_a'})
        env_files.apply([first, second])
        # One variable, so the later file wins, as it would spelled alike.
        self.assertEqual('second', os.environ['NXT_T_A'])
        self.assertEqual('second', os.environ['NXT_T_B'])
        self.assertTrue(env_files.is_applied('nxt_t_a'))
        self.assertEqual(1, len([name for name in env_files._declared
                                 if name.upper() == 'NXT_T_A']))
        write(second, {})
        write(first, {})
        env_files.apply([first, second])
        self.assertNotIn('NXT_T_A', os.environ)

    @unittest.skipIf(os.name == 'nt', 'names ignore case on Windows')
    def test_case_counts_elsewhere(self):
        env = write(self.path('env.json'), {'nxt_t_a': 'lower',
                                            'NXT_T_A': 'upper'})
        env_files.apply([env])
        self.assertEqual('lower', os.environ['nxt_t_a'])
        self.assertEqual('upper', os.environ['NXT_T_A'])


class WhatWasApplied(EnvFilesCase):

    def test_a_copy_of_what_the_files_set(self):
        os.environ['NXT_T_B'] = 'from the launcher'
        env = write(self.path('env.json'), {'NXT_T_A': 'a',
                                            'NXT_T_B': 'b'})
        env_files.apply([env])
        applied = env_files.applied()
        self.assertEqual({'NXT_T_A': 'a'}, applied)
        applied['NXT_T_A'] = 'changed'
        self.assertEqual('a', env_files.applied()['NXT_T_A'])

    def test_is_applied(self):
        os.environ['NXT_T_B'] = 'from the launcher'
        env = write(self.path('env.json'), {'NXT_T_A': 'a',
                                            'NXT_T_B': 'b'})
        env_files.apply([env])
        self.assertTrue(env_files.is_applied('NXT_T_A'))
        self.assertFalse(env_files.is_applied('NXT_T_B'))
        self.assertFalse(env_files.is_applied('NXT_T_ROOTS'))
        os.environ['NXT_T_A'] = 'set by a node'
        self.assertFalse(env_files.is_applied('NXT_T_A'))


class SavingAFile(EnvFilesCase):

    def test_what_is_saved_loads_the_same(self):
        env_file = env_files.EnvFile(self.path('made/env.json'))
        env_file.include = ['$NXT_ENV_FILE_DIR/shared.json']
        env_file.variables['NXT_T_ROOTS'] = ['/a', '/b']
        env_file.variables['NXT_T_A'] = 'one'
        env_file.save()
        loaded = env_files.EnvFile.load(env_file.path)
        self.assertEqual(env_file.include, loaded.include)
        self.assertEqual(list(env_file.variables.items()),
                         list(loaded.variables.items()))


class AnyLanguage(EnvFilesCase):
    """An env file is UTF-8, whatever the system's own encoding is."""

    def test_a_utf8_file_with_a_byte_order_mark_is_read(self):
        env = self.path('env.json')
        with open(env, 'w', encoding='utf-8-sig') as file_object:
            file_object.write('{"variables": {"NXT_T_A": "/グラフ/'
                              'réseau"}}')
        env_files.apply([env])
        self.assertEqual('/グラフ/réseau',
                         os.environ['NXT_T_A'])

    def test_saved_as_utf8_and_loads_the_same(self):
        env_file = env_files.EnvFile(self.path('env.json'))
        env_file.variables['NXT_T_A'] = '/グラフ/réseau'
        env_file.save()
        with open(env_file.path, 'rb') as file_object:
            raw = file_object.read()
        self.assertIn('グラフ'.encode('utf-8'), raw)
        loaded = env_files.EnvFile.load(env_file.path)
        self.assertEqual('/グラフ/réseau',
                         loaded.variables['NXT_T_A'])


if __name__ == '__main__':
    unittest.main()
