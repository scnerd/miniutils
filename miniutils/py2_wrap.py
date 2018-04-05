import inspect
import os
import pickle
import re
import struct
import subprocess as sp
import textwrap


_re_var_name = re.compile(r'^[a-zA-Z_]\w*$', re.UNICODE)
_re_module_name = re.compile(r'^[a-zA-Z_.][\w.]*$', re.UNICODE)


# TODO: Use fd's besides stdin and stdout, so that you don't mess with code that reads or writes to those streams
class MakePython2:
    pickle_protocol = 2
    template = os.path.join(*(list(os.path.split(__file__))[:-1] + ['py2_template.py']))

    def __init__(self, func=None, *, imports=None, global_values=None, copy_function_body=True,
                 python2_path='python2'):
        """Make a function execute within a Python 2 instance

        :param func: The function to wrap. If not specified, this class instance behaves like a decorator
        :param imports: Any import statements the function requires. Should be a list, where each element is either a
            string (e.g., ``'sys'`` for ``import sys``)
            or a tuple (e.g., ``('os.path', 'path')`` for ``import os.path as pas``)
        :param global_values: A dictionary of global variables the function relies on. Key must be strings, and values
            must be picklable
        :param copy_function_body: Whether or not to copy the function's source code into the Python 2 instance
        :param python2_path: The path to the Python 2 executable to use
        """
        self.imports = imports or []
        self.globals = global_values or {}
        self.copy_function_body = copy_function_body
        self.python2_path = python2_path
        self.proc = None

        if isinstance(self.imports, dict):
            self.imports = list(self.imports.items())
        for i, imp in enumerate(self.imports):
            if isinstance(imp, str):
                self.imports[i] = (imp,)
            elif isinstance(imp, (tuple, list)):
                if len(imp) not in [1, 2]:
                    raise ValueError("Imports must be given as 'name', ('name',), or ('pkg', 'name')")
            if not all(isinstance(n, str) and _re_module_name.match(n) for n in imp):
                raise ValueError("Invalid import name: 'import {}{}'"
                                 .format(imp[0], 'as {}'.format(imp[1]) if len(imp) == 2 else ''))

        for k in self.globals.keys():
            if not isinstance(k, str):
                raise ValueError("Global variables must be given as {'name': value}")
            elif not _re_var_name.match(k):
                raise ValueError("Invalid variable name given: '{}'".format(k))

        if func:
            self(func)

    def _write_pkl(self, obj):
        data = pickle.dumps(obj, protocol=MakePython2.pickle_protocol)
        self.proc.stdin.write(struct.pack('@I', len(data)))
        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def _read_pkl(self):
        outp_length = int(struct.unpack('@I', self.proc.stdout.read(4))[0])
        return pickle.loads(self.proc.stdout.read(outp_length))

    def _wrapped_function(self, *args, **kwargs):
        self._write_pkl((args, kwargs))
        success, result = self._read_pkl()
        if success:
            return result
        else:
            raise RuntimeError(result)

    @property
    def function(self):
        return self._wrapped_function

    def __call__(self, func):
        if callable(func):
            function_code = textwrap.dedent(inspect.getsource(func)) if self.copy_function_body else ''
            function_code = '\n'.join(line for line in function_code.split('\n') if not line.startswith('@MakePython2'))
            function_name = func.__name__
        elif isinstance(func, str):
            function_code = ''
            function_name = func
        else:
            raise TypeError("MakePython2 must be given either a function or an expression string to execute")

        self.proc = sp.Popen([self.python2_path, MakePython2.template], executable=self.python2_path,
                             stdin=sp.PIPE, stdout=sp.PIPE)
        self._write_pkl((self.imports, self.globals, function_name, function_code))

        return self._wrapped_function

    def __del__(self):
        if self.proc:
            self._write_pkl(None)
            self.proc.stdin.close()
            self.proc.stdout.close()
            self.proc.terminate()
            self.proc.wait()
