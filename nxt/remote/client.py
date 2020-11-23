# Builtin
import sys
if sys.version_info[0] == 2:
    from xmlrpclib import ServerProxy
else:
    from xmlrpc.client import ServerProxy

# Internal
from nxt.remote import get_running_server_address


class NxtClient(ServerProxy, object):
    def __init__(self, address=None):
        if address is None:
            address = 'http://{}'.format(get_running_server_address())
        self.address = address
        super(NxtClient, self).__init__(self.address, allow_none=True)

    def __repr__(self):
        return self.address
