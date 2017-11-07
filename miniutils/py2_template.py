# THIS CODE IS MEANT TO BE RUN BY py2_wrap.py, NOT DIRECTLY!!!

import cPickle as pickle
import sys
import struct
import re
import importlib


def read_pkl():
    length = int(struct.unpack('@I', sys.stdin.read(4))[0])
    return pickle.loads(sys.stdin.read(length))


def write_pkl(data):
    data = pickle.dumps(data)
    sys.stdout.write(struct.pack('@I', len(data)))
    sys.stdout.write(data)
    sys.stdout.flush()


imports, global_dict, function_name, function_code = read_pkl()

for imp in imports:
    if len(imp) == 1:
        global_dict[imp[0]] = importlib.import_module(imp[0])
    elif len(imp) == 2:
        global_dict[imp[1]] = importlib.import_module(imp[0])


if function_code:
    exec(function_code, global_dict)

while True:
    arg = read_pkl()
    if arg is None:
        sys.exit(0)
    args, kwargs = arg
    try:
        result = eval("{}(*__args__, **__kwargs__)".format(function_name),
                      global_dict, dict(__args__=args, __kwargs__=kwargs))
        write_pkl((True, result))
    except Exception as ex:
        write_pkl((False, str(ex)))
