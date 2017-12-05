import ast
import astor
import copy
import inspect
import sys
import tempfile
import textwrap
import traceback
import warnings

from miniutils.opt_decorator import optional_argument_decorator
from miniutils.magic_contract import magic_contract, safe_new_contract
from contracts import ContractNotRespected

try:
    import numpy

    num_types = (int, float, numpy.number)
    float_types = (float, numpy.floating)
except ImportError:  # pragma: nocover
    num_types = (int, float)
    float_types = (float,)


def is_iterable(x):
    try:
        iter(x)
        return True
    except Exception:
        return False


safe_new_contract('function', lambda x: callable(x))
safe_new_contract('iterable', is_iterable)
safe_new_contract('literal', 'int|float|str|bool|tuple|list|None')
for name, tp in inspect.getmembers(ast, inspect.isclass):
    safe_new_contract(name, tp)

# Astor tries to get fancy by failing nicely, but in doing so they fail when traversing non-AST type node properties.
#  By deleting this custom handler, it'll fall back to the default ast visit pattern, which skips these missing
# properties. Everything else seems to be implemented, so this will fail silently if it hits an AST node that isn't
# supported but should be.
try:
    del astor.node_util.ExplicitNodeVisitor.visit
except AttributeError:
    # visit isn't defined in this version of astor
    pass


class DictStack:
    """
    Creates a stack of dictionaries to roughly emulate closures and variable environments
    """

    def __init__(self, *base):
        import builtins
        self.dicts = [dict(builtins.__dict__)] + [dict(d) for d in base]
        self.constants = [True] + [False] * len(base)

    def __setitem__(self, key, value):
        # print("SETTING {} = {}".format(key, value))
        self.dicts[-1][key] = value

    def __getitem__(self, item):
        for dct in self.dicts[::-1]:
            if item in dct:
                if dct[item] is None:
                    raise KeyError("Found '{}', but it was set to an unknown value".format(item))
                return dct[item]
        raise KeyError("Can't find '{}' anywhere in the function's context".format(item))

    def __delitem__(self, item):
        for dct in self.dicts[::-1]:
            if item in dct:
                del dct[item]
                return
        raise KeyError()

    def __contains__(self, item):
        try:
            _ = self[item]
            return True
        except KeyError:
            return False

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


@magic_contract
def _function_ast(f):
    """
    Returns ast for the given function. Gives a tuple of (ast_module, function_body, function_file
    :param f: The function to parse
    :type f: function
    :return: The relevant AST code: A module including only the function definition; the func body; the func file
    :rtype: tuple(Module, list(AST), str)
    """
    try:
        f_file = sys.modules[f.__module__].__file__
    except (KeyError, AttributeError):
        f_file = ''

    root = ast.parse(textwrap.dedent(inspect.getsource(f)), f_file)
    return root, root.body[0].body, f_file


@magic_contract
def _can_have_side_effect(node, ctxt):
    """
    Checks whether or not copying the given AST node could cause side effects in the resulting function
    :param node: The AST node to be checked
    :type node: AST
    :param ctxt: The environment stack to use when running the check
    :type ctxt: DictStack
    :return: Whether or not duplicating this node could cause side effects
    :rtype: bool
    """
    if isinstance(node, ast.AST):
        # print("Can {} have side effects?".format(node))
        if isinstance(node, ast.Call):
            # print("  Yes!")
            return True
        else:
            for field, old_value in ast.iter_fields(node):
                if isinstance(old_value, list):
                    return any(_can_have_side_effect(n, ctxt) for n in old_value if isinstance(n, ast.AST))
                elif isinstance(old_value, ast.AST):
                    return _can_have_side_effect(old_value, ctxt)
                else:
                    # print("  No!")
                    return False
    else:
        return False


@magic_contract
def _constant_iterable(node, ctxt, avoid_side_effects=True):
    """
    If the given node is a known iterable of some sort, return the list of its elements.
    :param node: The AST node to be checked
    :type node: AST
    :param ctxt: The environment stack to use when running the check
    :type ctxt: DictStack
    :param avoid_side_effects: Whether or not to avoid unwrapping side effect-causing AST nodes
    :type avoid_side_effects: bool
    :return: The iterable if possible, else None
    :rtype: iterable|None
    """

    # TODO: Support zipping
    # TODO: Support sets/dicts?
    # TODO: Support for reversed, enumerate, etc.
    # TODO: Support len, in, etc.
    # Check for range(*constants)
    def wrap(return_node, name, idx):
        if not avoid_side_effects:
            return return_node
        if _can_have_side_effect(return_node, ctxt):
            return ast.Subscript(name, ast.Index(idx))
        return _make_ast_from_literal(return_node)

    if isinstance(node, ast.Call):
        if _resolve_name_or_attribute(node.func, ctxt) == range:
            args = [_collapse_literal(arg, ctxt) for arg in node.args]
            if all(isinstance(arg, ast.Num) for arg in args):
                return [ast.Num(n) for n in range(*[arg.n for arg in args])]

        return None
    elif isinstance(node, (ast.List, ast.Tuple)):
        return [_collapse_literal(e, ctxt) for e in node.elts]
        # return [_resolve_name_or_attribute(e, ctxt) for e in node.elts]
    # Can't yet support sets and lists, since you need to compute what the unique values would be
    # elif isinstance(node, ast.Dict):
    #     return node.keys
    elif isinstance(node, (ast.Name, ast.Attribute, ast.NameConstant)):
        res = _resolve_name_or_attribute(node, ctxt)
        # print("Trying to resolve '{}' as list, got {}".format(astor.to_source(node), res))
        if isinstance(res, ast.AST) and not isinstance(res, (ast.Name, ast.Attribute, ast.NameConstant)):
            res = _constant_iterable(res, ctxt)
        if not isinstance(res, ast.AST):
            try:
                if hasattr(res, 'items'):
                    return dict([(k, wrap(_make_ast_from_literal(v), node, k)) for k, v in res.items()])
                else:
                    return [wrap(_make_ast_from_literal(res_node), node, i) for i, res_node in enumerate(res)]
            except TypeError:
                pass
    return None


@magic_contract
def _resolve_name_or_attribute(node, ctxt):
    """
    If the given name of attribute is defined in the current context, return its value. Else, returns the node
    :param node: The node to try to resolve
    :type node: AST
    :param ctxt: The environment stack to use when running the check
    :type ctxt: DictStack
    :return: The object if the name was found, else the original node
    :rtype: *
    """
    if isinstance(node, ast.Name):
        if node.id in ctxt:
            return ctxt[node.id]
        else:
            return node
    elif isinstance(node, ast.NameConstant):
        return node.value
    elif isinstance(node, ast.Attribute):
        base_obj = _resolve_name_or_attribute(node.value, ctxt)
        if not isinstance(base_obj, ast.AST):
            return getattr(base_obj, node.attr, node)
        else:
            return node
    else:
        return node


_collapse_map = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,

    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
    ast.LShift: lambda a, b: a << b,
    ast.RShift: lambda a, b: a >> b,
    ast.MatMult: lambda a, b: a @ b,

    ast.BitAnd: lambda a, b: a & b,
    ast.BitOr: lambda a, b: a | b,
    ast.BitXor: lambda a, b: a ^ b,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
    ast.Invert: lambda a: ~a,
    ast.Not: lambda a: not a,

    ast.UAdd: lambda a: a,
    ast.USub: lambda a: -a,

    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
}


@magic_contract
def _make_ast_from_literal(lit):
    """
    Converts literals into their AST equivalent
    :param lit: The literal to attempt to turn into an AST
    :type lit: *
    :return: The AST version of the literal, or the original AST node if one was given
    :rtype: *
    """
    if isinstance(lit, ast.AST):
        return lit
    elif isinstance(lit, (list, tuple)):
        res = [_make_ast_from_literal(e) for e in lit]
        tp = ast.List if isinstance(lit, list) else ast.Tuple
        return tp(elts=res)
    elif isinstance(lit, num_types):
        if isinstance(lit, float_types):
            lit2 = float(lit)
        else:
            lit2 = int(lit)
        if lit2 != lit:
            raise AssertionError("({}){} != ({}){}".format(type(lit), lit, type(lit2), lit2))
        return ast.Num(lit2)
    elif isinstance(lit, str):
        return ast.Str(lit)
    elif isinstance(lit, bool):
        return ast.NameConstant(lit)
    else:
        # warnings.warn("'{}' of type {} is not able to be made into an AST node".format(lit, type(lit)))
        return lit


@magic_contract
def _is_wrappable(lit):
    """
    Checks if the given object either is or can be made into a known AST node
    :param lit: The object to try to wrap
    :type lit: *
    :return: Whether or not this object can be wrapped as an AST node
    :rtype: bool
    """
    return isinstance(_make_ast_from_literal(lit), ast.AST)


@magic_contract
def __collapse_literal(node, ctxt):
    """
    Collapses literal expressions. Returns literals if they're available, AST nodes otherwise
    :param node: The AST node to be checked
    :type node: AST
    :param ctxt: The environment stack to use when running the check
    :type ctxt: DictStack
    :return: The given AST node with literal operations collapsed as much as possible
    :rtype: *
    """
    # try:
    #     print("Trying to collapse {}".format(astor.to_source(node)))
    # except:
    #     print("Trying to collapse (source not possible) {}".format(astor.dump_tree(node)))

    if isinstance(node, (ast.Name, ast.Attribute, ast.NameConstant)):
        res = _resolve_name_or_attribute(node, ctxt)
        if isinstance(res, ast.AST) and not isinstance(res, (ast.Name, ast.Attribute, ast.NameConstant)):
            new_res = __collapse_literal(res, ctxt)
            if _is_wrappable(new_res):
                # print("{} can be replaced by more specific literal {}".format(res, new_res))
                res = new_res
            # else:
            #     print("{} is an AST node, but can't safely be made more specific".format(res))
        return res
    elif isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Str):
        return node.s
    elif isinstance(node, ast.Index):
        return __collapse_literal(node.value, ctxt)
    elif isinstance(node, (ast.Slice, ast.ExtSlice)):
        raise NotImplemented()
    elif isinstance(node, ast.Subscript):
        # print("Attempting to subscript {}".format(astor.to_source(node)))
        lst = _constant_iterable(node.value, ctxt)
        # print("Can I subscript {}?".format(lst))
        if lst is None:
            return node
        slc = __collapse_literal(node.slice, ctxt)
        # print("Getting subscript at {}".format(slc))
        if isinstance(slc, ast.AST):
            return node
        # print("Value at {}[{}] = {}".format(lst, slc, lst[slc]))
        val = lst[slc]
        if isinstance(val, ast.AST):
            new_val = __collapse_literal(val, ctxt)
            if _is_wrappable(new_val):
                # print("{} can be replaced by more specific literal {}".format(val, new_val))
                val = new_val
        #     else:
        #         print("{} is an AST node, but can't safely be made more specific".format(val))
        # print("Final value at {}[{}] = {}".format(lst, slc, val))
        return val
    elif isinstance(node, ast.UnaryOp):
        operand = __collapse_literal(node.operand, ctxt)
        if isinstance(operand, ast.AST):
            return node
        else:
            try:
                return _collapse_map[node.op](operand)
            except:
                warnings.warn(
                    "Unary op collapse failed. Collapsing skipped, but executing this function will likely fail."
                    " Error was:\n{}".format(traceback.format_exc()))
    elif isinstance(node, ast.BinOp):
        left = __collapse_literal(node.left, ctxt)
        right = __collapse_literal(node.right, ctxt)
        # print("({} {})".format(repr(node.op), ", ".join(repr(o) for o in operands)))
        lliteral = not isinstance(left, ast.AST)
        rliteral = not isinstance(right, ast.AST)
        if lliteral and rliteral:
            # print("Both operands {} and {} are literals, attempting to collapse".format(left, right))
            try:
                return _collapse_map[type(node.op)](left, right)
            except:
                warnings.warn(
                    "Binary op collapse failed. Collapsing skipped, but executing this function will likely fail."
                    " Error was:\n{}".format(traceback.format_exc()))
                return node
        else:
            left = _make_ast_from_literal(left)
            left = left if isinstance(left, ast.AST) else node.left

            right = _make_ast_from_literal(right)
            right = right if isinstance(right, ast.AST) else node.right
            # print("Attempting to combine {} and {} ({} op)".format(left, right, node.op))
            return ast.BinOp(left=left, right=right, op=node.op)
    elif isinstance(node, ast.Compare):
        operands = [__collapse_literal(o, ctxt) for o in [node.left] + node.comparators]
        if all(not isinstance(opr, ast.AST) for opr in operands):
            return all(_collapse_map[type(cmp_func)](operands[i - 1], operands[i])
                       for i, cmp_func in zip(range(1, len(operands)), node.ops))
        else:
            return node
    else:
        return node


@magic_contract
def _collapse_literal(node, ctxt, give_raw_result=False):
    """
    Collapse literal expressions in the given node. Returns the node with the collapsed literals
    :param node: The AST node to be checked
    :type node: AST
    :param ctxt: The environment stack to use when running the check
    :type ctxt: DictStack
    :return: The given AST node with literal operations collapsed as much as possible
    :rtype: *
    """
    result = __collapse_literal(node, ctxt)
    if give_raw_result:
        return result
    result = _make_ast_from_literal(result)
    if not isinstance(result, ast.AST):
        return node
    return result


@magic_contract
def _assign_names(node):
    """
    Gets names from a assign-to tuple in flat form, just to know what's affected
    "x=3" -> "x"
    "a,b=4,5" -> ["a", "b"]
    "(x,(y,z)),(a,) = something" -> ["x", "y", "z", "a"]

    :param node: The AST node to resolve to a list of names
    :type node: Name|Tuple
    :return: The flattened list of names referenced in this node
    :rtype: iterable
    """
    if isinstance(node, ast.Name):
        yield node.id
    elif isinstance(node, ast.Tuple):
        for e in node.elts:
            yield from _assign_names(e)
    elif isinstance(node, ast.Subscript):
        raise NotImplemented()


# noinspection PyPep8Naming
class TrackedContextTransformer(ast.NodeTransformer):
    def __init__(self, ctxt=None):
        self.ctxt = ctxt or DictStack()
        super().__init__()

    # def visit(self, node):
    #     orig_node = copy.deepcopy(node)
    #     new_node = super().visit(node)
    #
    #     try:
    #         orig_node_code = astor.to_source(orig_node).strip()
    #         if new_node is None:
    #             print("Deleted >>> {} <<<".format(orig_node_code))
    #         elif isinstance(new_node, ast.AST):
    #             print("Converted >>> {} <<< to >>> {} <<<".format(orig_node_code, astor.to_source(new_node).strip()))
    #         elif isinstance(new_node, list):
    #             print("Converted >>> {} <<< to [[[ {} ]]]".format(orig_node_code, ", ".join(astor.to_source(n).strip() for n in new_node)))
    #     except Exception as ex:
    #         raise AssertionError("Failed on {} >>> {}".format(astor.dump_tree(orig_node), astor.dump_tree(new_node))) from ex
    #         # print("Failed on {} >>> {}".format(astor.dump_tree(orig_node), astor.dump_tree(new_node)))
    #         # return orig_node
    #
    #     return new_node

    def visit_Assign(self, node):
        node.value = self.visit(node.value)
        # print(node.value)
        # TODO: Support tuple assignments
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            nvalue = copy.deepcopy(node.value)
            var = node.targets[0].id
            val = _constant_iterable(nvalue, self.ctxt)
            if val is not None:
                # print("Setting {} = {}".format(var, val))
                self.ctxt[var] = val
            else:
                val = _collapse_literal(nvalue, self.ctxt)
                # print("Setting {} = {}".format(var, val))
                self.ctxt[var] = val
        else:
            for targ in node.targets:
                for assgn in _assign_names(targ):
                    self.ctxt[assgn] = None
        return node

    def visit_AugAssign(self, node):
        for assgn in _assign_names(node.target):
            self.ctxt[assgn] = None
        return super().generic_visit(node)


# noinspection PyPep8Naming
class UnrollTransformer(TrackedContextTransformer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_vars = set()

    def visit_For(self, node):
        result = [node]
        iterable = _constant_iterable(node.iter, self.ctxt)
        if iterable is not None:
            result = []
            loop_var = node.target.id
            orig_loop_vars = self.loop_vars
            # print("Unrolling 'for {} in {}'".format(loop_var, list(iterable)))
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
                # result.extend([self.visit(body_node) for body_node in copy.deepcopy(node.body)])
                self.ctxt.pop()
            self.loop_vars = orig_loop_vars
        return result

    def visit_Name(self, node):
        if node.id in self.loop_vars:
            if node.id in self.ctxt:
                return self.ctxt[node.id]
            raise NameError("'{}' not defined in context".format(node.id))
        return node


# noinspection PyPep8Naming
class CollapseTransformer(TrackedContextTransformer):
    def visit_Name(self, node):
        return _collapse_literal(node, self.ctxt)

    def visit_BinOp(self, node):
        return _collapse_literal(node, self.ctxt)

    def visit_UnaryOp(self, node):
        return _collapse_literal(node, self.ctxt)

    def visit_BoolOp(self, node):
        return _collapse_literal(node, self.ctxt)

    def visit_Compare(self, node):
        return _collapse_literal(node, self.ctxt)

    def visit_Subscript(self, node):
        return _collapse_literal(node, self.ctxt)

    def visit_If(self, node):
        cond = _collapse_literal(node.test, self.ctxt, True)
        # print("Attempting to collapse IF conditioned on {}".format(cond))
        if not isinstance(cond, ast.AST):
            # print("Yes, this IF can be consolidated, condition is {}".format(bool(cond)))
            body = node.body if cond else node.orelse
            result = []
            for subnode in body:
                res = self.visit(subnode)
                if res is None:
                    pass
                elif isinstance(res, list):
                    result += res
                else:
                    result.append(res)
            return result
        else:
            # print("No, this IF cannot be consolidated")
            return super().generic_visit(node)


def _make_function_transformer(transformer_type, name, description):
    @optional_argument_decorator
    @magic_contract
    def transform(return_source=False, save_source=True, function_globals=None, **kwargs):
        """
        :param return_source: Returns the unrolled function's source code instead of compiling it
        :type return_source: bool
        :param save_source: Saves the function source code to a tempfile to make it inspectable
        :type save_source: bool
        :param function_globals: Overridden global name assignments to use when processing the function
        :type function_globals: dict|None
        :param kwargs: Any other environmental variables to provide during unrolling
        :type kwargs: dict
        :return: The unrolled function, or its source code if requested
        :rtype: function
        """

        @magic_contract(f='function', returns='function|str')
        def inner(f):
            f_mod, f_body, f_file = _function_ast(f)
            # Grab function globals
            glbls = f.__globals__
            # Grab function closure variables
            if isinstance(f.__closure__, tuple):
                glbls.update({k: v.cell_contents for k, v in zip(f.__code__.co_freevars, f.__closure__)})
            # Apply manual globals override
            if function_globals is not None:
                glbls.update(function_globals)
            # print({k: v for k, v in glbls.items() if k not in globals()})
            trans = transformer_type(DictStack(glbls, kwargs))
            f_mod.body[0].decorator_list = []
            f_mod = trans.visit(f_mod)
            # print(astor.dump_tree(f_mod))
            if return_source or save_source:
                try:
                    source = astor.to_source(f_mod)
                except ImportError:  # pragma: nocover
                    raise ImportError("miniutils.pragma.{name} requires 'astor' to be installed to obtain source code"
                                      .format(name=name))
                except Exception as ex:  # pragma: nocover
                    raise RuntimeError(astor.dump_tree(f_mod)) from ex
            else:
                source = None

            if return_source:
                return source
            else:
                # func_source = astor.to_source(f_mod)
                f_mod = ast.fix_missing_locations(f_mod)
                if save_source:
                    temp = tempfile.NamedTemporaryFile('w', delete=True)
                    f_file = temp.name
                exec(compile(f_mod, f_file, 'exec'), glbls)
                func = glbls[f_mod.body[0].name]
                if save_source:
                    func.__tempfile__ = temp
                    temp.write(source)
                    temp.flush()
                return func

        return inner

    transform.__name__ = name
    transform.__doc__ = '\n'.join([description, transform.__doc__])
    return transform


# Unroll literal loops
unroll = _make_function_transformer(UnrollTransformer, 'unroll', "Unrolls constant loops in the decorated function")

# Collapse defined literal values, and operations thereof, where possible
collapse_literals = _make_function_transformer(CollapseTransformer, 'collapse_literals',
                                               "Collapses literal expressions in the decorated function into single literals")


# Directly reference elements of constant list, removing literal indexing into that list within a function
@magic_contract
def deindex(iterable, iterable_name, *args, **kwargs):
    """
    :param iterable: The list to deindex in the target function
    :type iterable: iterable
    :param iterable_name: The list's name (must be unique if deindexing multiple lists)
    :type iterable_name: str
    :param args: Other command line arguments (see :func:`unroll` for documentation)
    :type args: tuple
    :param kwargs: Any other environmental variables to provide during unrolling
    :type kwargs: dict
    :return: The unrolled function, or its source code if requested
    :rtype: function
    """

    if hasattr(iterable, 'items'):  # Support dicts and the like
        internal_iterable = {k: '{}_{}'.format(iterable_name, k) for k, val in iterable.items()}
        mapping = {internal_iterable[k]: val for k, val in iterable.items()}
    else:  # Support lists, tuples, and the like
        internal_iterable = {i: '{}_{}'.format(iterable_name, i) for i, val in enumerate(iterable)}
        mapping = {internal_iterable[i]: val for i, val in enumerate(iterable)}

    kwargs[iterable_name] = {k: ast.Name(id=name, ctx=ast.Load()) for k, name in internal_iterable.items()}

    return collapse_literals(*args, function_globals=mapping, **kwargs)

# Inline functions?
# You could do something like:
# args, kwargs = (args_in), (kwargs_in)
# function_body
# result = return_expr
