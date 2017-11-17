import ast, inspect, sys, copy
from miniutils.opt_decorator import optional_argument_decorator
import textwrap
import astor


class DictStack:
    def __init__(self, *base):
        import builtins
        self.dicts = [dict(builtins.__dict__)] + [dict(d) for d in base]
        self.constants = [True] + [False] * len(base)

    def __setitem__(self, key, value):
        self.dicts[-1][key] = value

    def __getitem__(self, item):
        for dct in self.dicts[::-1]:
            if item in dct:
                return dct[item]
        raise KeyError()

    def __delitem__(self, item):
        for dct in self.dicts[::-1]:
            if item in dct:
                del dct[item]
                return
        raise KeyError()

    def __contains__(self, item):
        return any(item in dct for dct in self.dicts[::-1])

    def items(self):
        items = []
        for dct in self.dicts[::-1]:
            for k, v in dct.items():
                if k not in items:
                    items.append((k, v))
        return items

    def keys(self):
        return set().union(*[dct.keys() for dct in self.dicts])

    def push(self, dct=None, is_constant=False):
        self.dicts.append(dct or {})
        self.constants.append(is_constant)

    def pop(self):
        self.constants.pop()
        return self.dicts.pop()


def _function_ast(f):
    assert callable(f)

    try:
        f_file = sys.modules[f.__module__].__file__
    except (KeyError, AttributeError):
        f_file = ''

    root = ast.parse(textwrap.dedent(inspect.getsource(f)), f_file)
    return root, root.body[0].body, f_file


def _constant_iterable(node, ctxt):
    # Check for range(*constants)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and ctxt[node.func.id] == range and all(
            isinstance(arg, ast.Num) for arg in node.args):
        return [ast.Num(n) for n in range(*[arg.n for arg in node.args])]
    elif isinstance(node, (ast.List, ast.Tuple)):
        return [resolve_name_or_attribute(e, ctxt) for e in node.elts]
    # Can't yet support sets and lists, since you need to compute what the unique values would be
    # elif isinstance(node, ast.Dict):
    #     return node.keys
    elif isinstance(node, (ast.Name, ast.Attribute)):
        res = resolve_name_or_attribute(node, ctxt)
        if not isinstance(res, ast.AST):
            try:
                iter(res)
                return list(res)
            except TypeError:
                pass
    return None


def resolve_name_or_attribute(node, ctxt_or_obj):
    if isinstance(node, ast.Name):
        if isinstance(ctxt_or_obj, DictStack):
            if node.id in ctxt_or_obj:
                return ctxt_or_obj[node.id]
            else:
                return node
        else:
            return getattr(ctxt_or_obj, node.id, node)
    elif isinstance(node, ast.Attribute):
        base_obj = resolve_name_or_attribute(node.value, ctxt_or_obj)
        if not isinstance(base_obj, ast.AST):
            return getattr(base_obj, node.attr, node)
        else:
            return node
    else:
        return node


class UnrollTransformer(ast.NodeTransformer):
    def __init__(self, ctxt=None, *args, **kwargs):
        self.ctxt = ctxt or DictStack()
        self.loop_vars = set()
        super().__init__(*args, **kwargs)

    def visit_For(self, node):
        result = [node]
        iterable = _constant_iterable(node.iter, self.ctxt)
        if iterable is not None:
            result = []
            loop_var = node.target.id
            orig_loop_vars = self.loop_vars
            #print("Unrolling 'for {} in {}'".format(loop_var, list(iterable)))
            for val in iterable:
                self.ctxt.push({loop_var: val})
                self.loop_vars = orig_loop_vars | {loop_var}
                for body_node in copy.deepcopy(node.body):
                    res = self.visit(body_node)
                    if isinstance(res, list):
                        result.extend(res)
                    elif res is None:
                        continue
                    else:
                        result.append(res)
                #result.extend([self.visit(body_node) for body_node in copy.deepcopy(node.body)])
                self.ctxt.pop()
            self.loop_vars = orig_loop_vars
        return result

    def visit_Name(self, node):
        if node.id in self.loop_vars:
            if node.id in self.ctxt:
                return self.ctxt[node.id]
            raise NameError("'{}' not defined in context".format(node.id))
        return node

    def visit_Assign(self, node):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var = node.targets[0].id
            val = _constant_iterable(node.value, self.ctxt)
            if val is not None:
                self.ctxt[var] = val
            else:
                self.ctxt[var] = node.value
        return node


@optional_argument_decorator
def unroll(return_source=False, **kwargs):
    """Unrolls

    :param return_source:
    :param kwargs:
    :return:
    """
    # TODO: Support zipping
    # TODO: Support sets/dicts
    # TODO: Support provided constants (i.e. "x=5; range(x)")
    def inner(f):
        f_mod, f_body, f_file = _function_ast(f)
        glbls = f.__globals__
        trans = UnrollTransformer(DictStack(glbls, kwargs))
        f_mod.body[0].decorator_list = []
        f_mod = trans.visit(f_mod)
        if return_source:
            try:
                import astor
                return astor.to_source(f_mod)
            except ImportError:
                raise ImportError("miniutils.pragma.unroll requires 'astor' to be installed to return source code")
        else:
            #func_source = astor.to_source(f_mod)
            f_mod = ast.fix_missing_locations(f_mod)
            exec(compile(f_mod, f_file, 'exec'), glbls)
            return glbls[f_mod.body[0].name]

    return inner


# # Given a set of functions that are called, inline their code into the decorated function
# def inline(*inline_fs):
#     def inner(f):
#         return f
#
#     return inner


# # Collapse defined literal values, and operations thereof, where possible
# def collapse_constants():
#     def inner(f):
#         return f
#
#     return inner
