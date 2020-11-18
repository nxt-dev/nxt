import os

TRAVIS_BRANCH = os.environ['TRAVIS_BRANCH']
TRAVIS_PULL_REQUEST_BRANCH = os.environ['TRAVIS_PULL_REQUEST_BRANCH']
TRAVIS_TYPE = os.environ['TRAVIS_TYPE']
TRAVIS_EVENT_TYPE = os.environ['TRAVIS_EVENT_TYPE']

if TRAVIS_BRANCH == 'release' == TRAVIS_PULL_REQUEST_BRANCH:
    print('Hello from the release')

elif TRAVIS_BRANCH == 'dev':  # and TRAVIS_EVENT_TYPE == 'pull_request'
    print('Hello dev branch')

elif TRAVIS_BRANCH not in ('dev', 'release'):
    # Should never get here because of the travis safelist
    raise NameError('Unknown branch: {}'.format(TRAVIS_BRANCH))
