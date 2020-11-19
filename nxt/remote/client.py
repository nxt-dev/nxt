# Builtin
import sys
if sys.version_info[0] == 2:
    from xmlrpclib import ServerProxy
else:
    from xmlrpc.client import ServerProxy

# Internal
from nxt.remote import RPC_PORT


class NxtClient(ServerProxy, object):
    def __init__(self, host='http://localhost', port=RPC_PORT):
        self.host = host
        self.port = port
        self.address = '{host}:{port}'.format(host=self.host, port=self.port)
        super(NxtClient, self).__init__(self.address, allow_none=True)

    def __repr__(self):
        return self.address
