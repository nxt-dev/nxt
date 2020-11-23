# Builtin
import os
import tempfile
import logging

logger = logging.getLogger('nxt')


def get_running_server_address(as_str=True):
    host = 'localhost'
    port = 8001
    server_info_filepath = get_server_info_filepath()
    valid_data = False
    if os.path.isfile(server_info_filepath):
        with open(server_info_filepath, 'r') as fp:
            lines = fp.readlines()
            if len(lines) == 2:
                _, port = lines
                port = int(port)
                valid_data = True
    if not valid_data:
        logger.error('No running server could be found, returning defaults!')
    if as_str:
        return '{}:{}'.format(host, port)
    else:
        return host, port


def get_server_info_filepath():
    temp_dir = tempfile.gettempdir()
    server_info_filepath = os.path.join(temp_dir, 'NXT_RPC_SERVER')
    return server_info_filepath
