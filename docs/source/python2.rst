Nesting Python 2
================

In `very` rare situations, the standard means of Python2 compatibility within Python3 (such as ``six``, ``2to3``, or ``__futures__``) might simply be insufficient. Sometimes, you just need to run Python2 wholesale to get the correct behavior.

    This is not generally advised at all. I built this out of necessity, where identical function calls to a built-in Python package worked in Python2 and broke in Python3, and I could see no other way to solve the problem. Please exhaust all other options before deciding to use this hack.

In the vein of making complex modules in support of simple code, I wrapped the entire behavior into a function decorator. Define the function you want to run in Python2, decorate it, then just run it like you normally would. Voila, it's executed in a Python2 subprocess.

This works essentially using code templating. A Python2 instance is kicked off as a subprocess; it loads the parameters needed to run the function (as given to the decorator); finally, it sits in an infinite loop receiving arguments as pickles, running them through the function, and returning the results as pickles. It's designed to run self-contained functions, with some support for wrapping functions defined in external modules (though generally, in this case, I'd recommend writing a simple self-contained function that loads that module and runs the function).

Let's take a look at a minimal example::

    @MakePython2()
    def get_version():
        import sys
        return sys.version_info[0]

    get_version()  # Reports that we're in Python 2

    import sys
    sys.version_info[0]  # Reports that we're in Python 3

Of course, not every function is self-contained like this. To handle the majority of easy cases, the ``MakePython2`` decorator supports pre-defining a set of imports and global variables.

Imports are given as a list of items, each of which should be either a simple string::

    @MakePython2(imports=['sys'])
    def get_version():
        return sys.version_info[0]

or as a tuple of ``(package, name)``::

    @MakePython2(imports=[('sys', 'another_name')])
    def get_version():
        return another_name.version_info[0]

Global variables (if they can be pickled using protocol 2, the highest protocol for Python2) can be given as a dictionary of ``dict(name=value,...)``::

    @MakePython2(global_values={'x': 5})
    def add(y):
        return x + y

Additional features include changing the Python2 executable path, specifying that the function code shouldn't be copied to the Python2 instance (e.g., if you're just running a single function from an external module), and specifying the function to execute by name instead of by passing the function directly.

For example, to execute an external function, you can use the class as a wrapper instead of using the decorator notation::

    uname = MakePython2('os.uname', imports=['os'], copy_function_body=False).function

.. autoclass:: miniutils.py2_wrap.MakePython2
    :members:

    .. automethod:: __init__
