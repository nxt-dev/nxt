import sys


def load(json_load):
    return _byteify(json_load)


def _byteify(data, ignore_dicts=False):
    '''
    Encodes any unicode data as utf-8
    :param data: A data object from json.load or json.loads
    :param ignore_dicts: Should be true if loading json without a top level dict
    :return: unicode/byte free data
    '''
    # Python 2/3 compatibility
    if sys.version_info[0] == 2:
        if isinstance(data, unicode):
            return data.encode('utf-8')
    else:
        if isinstance(data, bytes):
            return data.encode('utf-8')
    if isinstance(data, list):
        return [_byteify(item, ignore_dicts=True) for item in data]
    if isinstance(data, dict) and not ignore_dicts:
        return {_byteify(key, ignore_dicts=True): _byteify(value, ignore_dicts=True) for key, value in data.items()}
    return data
