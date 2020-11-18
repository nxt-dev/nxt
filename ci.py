# Builtin
import os
import subprocess

# Internal
import nxt

# For push builds, or builds not triggered by a pull request, this is the
# name of the branch.
# For builds triggered by a pull request this is the name of the branch
# targeted by the pull request.
# For builds triggered by a tag, this is the same as the name of the tag
TRAVIS_BRANCH = os.environ['TRAVIS_BRANCH']

# if the current job is a pull request, the name of the branch from which the
# PR originated.
TRAVIS_PULL_REQUEST_BRANCH = os.environ['TRAVIS_PULL_REQUEST_BRANCH']

# Indicates how the build was triggered.
# One of `push`, `pull_request`, `api`, `cron`
TRAVIS_EVENT_TYPE = os.environ['TRAVIS_EVENT_TYPE']


def run_tests():
    """Runs tests from newly installed package"""
    ret = subprocess.call(['python', '-m', 'nxt.cli', 'test'])
    if ret:
        raise Exception('Unittest cli returned a non 0 exit code.')


def pypi_deploy():
    """Deploys from source"""
    nxt.execute_graph('nxt/build/make_package.nxt')
    print("This is where I'd deploy")


if TRAVIS_BRANCH == 'release' and TRAVIS_EVENT_TYPE == 'push':
    run_tests()
    pypi_deploy()
    print('Successful deploy from release')

elif TRAVIS_BRANCH == 'release' and TRAVIS_EVENT_TYPE == 'pull_request':
    run_tests()
    print('Successful tests on dev')

elif TRAVIS_BRANCH not in ('dev', 'release'):
    # Should never get here because of the travis safelist
    raise NameError('Unknown branch: {}'.format(TRAVIS_BRANCH))

