import ast, inspect, sys, copy


class DictStack:
    def __init__(self, base=None):
        import builtins
        base = base or {}
        self.dicts = [builtins.__dict__, base]

    def __setitem__(self, key, value):
        self.dicts[-1][key] = value

    def __getitem__(self, item):
        for dct in self.dicts[::-1]:
            if item in dct:
                return dct[item]
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

    def push(self, dct=None):
        self.dicts.append(dct or {})

    def pop(self):
        return self.dicts.pop()


def _function_ast(f):
    assert callable(f)

    try:
        f_file = sys.modules[f.__module__].__file__
    except (KeyError, AttributeError):
        f_file = ''

    root = ast.parse(inspect.getsource(f), f_file)
    return root, root.body[0].body, f_file


def _constant_iterable(node, ctxt):
    # Check for range(*constants)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and ctxt[node.func.id] == range and all(isinstance(arg, ast.Num) for arg in node.args):
        return [ast.Num(n) for n in range(*[arg.n for arg in node.args])]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return node.elts
    if isinstance(node, ast.Dict):
        return node.keys
    return None


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
            for val in iterable:
                self.ctxt.push({loop_var: val})
                self.loop_vars = orig_loop_vars | {loop_var}
                result.extend([self.visit(body_node) for body_node in copy.deepcopy(node.body)])
                self.ctxt.pop()
            self.loop_vars = orig_loop_vars
        return result

    def visit_Name(self, node):
        if node.id in self.loop_vars:
            if node.id in self.ctxt:
                return self.ctxt[node.id]
            raise NameError("'{}' not defined in context".format(node.id))
        return node


def unroll(f, return_source=False):
    f_mod, f_body, f_file = _function_ast(f)
    glbls = f.__globals__
    trans = UnrollTransformer(DictStack(glbls))
    result = [n for node in f_body for n in trans.visit(node)]
    f_mod.body[0].body = result
    if return_source:
        import astor
        return astor.to_source(f_mod)
    else:
        import astor
        print(astor.dump_tree(f_mod))
        compile(f_mod, f_file, 'exec')
