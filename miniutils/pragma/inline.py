import ast
import inspect

from .collapse_literals import collapse_literals
from .core import TrackedContextTransformer, function_ast, constant_dict, make_function_transformer
from .. import magic_contract
from collections import OrderedDict as odict


# stmt = FunctionDef(identifier name, arguments args,
#                        stmt* body, expr* decorator_list, expr? returns)
#           | AsyncFunctionDef(identifier name, arguments args,
#                              stmt* body, expr* decorator_list, expr? returns)
#
#           | ClassDef(identifier name,
#              expr* bases,
#              keyword* keywords,
#              stmt* body,
#              expr* decorator_list)
#           | Return(expr? value)
#
#           | Delete(expr* targets)
#           | Assign(expr* targets, expr value)
#           | AugAssign(expr target, operator op, expr value)
#           -- 'simple' indicates that we annotate simple name without parens
#           | AnnAssign(expr target, expr annotation, expr? value, int simple)
#
#           -- use 'orelse' because else is a keyword in target languages
#           | For(expr target, expr iter, stmt* body, stmt* orelse)
#           | AsyncFor(expr target, expr iter, stmt* body, stmt* orelse)
#           | While(expr test, stmt* body, stmt* orelse)
#           | If(expr test, stmt* body, stmt* orelse)
#           | With(withitem* items, stmt* body)
#           | AsyncWith(withitem* items, stmt* body)
#
#           | Raise(expr? exc, expr? cause)
#           | Try(stmt* body, excepthandler* handlers, stmt* orelse, stmt* finalbody)
#           | Assert(expr test, expr? msg)
#
#           | Import(alias* names)
#           | ImportFrom(identifier? module, alias* names, int? level)
#
#           | Global(identifier* names)
#           | Nonlocal(identifier* names)
#           | Expr(expr value)
#           | Pass | Break | Continue
#
#           -- XXX Jython will be different
#           -- col_offset is the byte offset in the utf8 string the parser uses
#           attributes (int lineno, int col_offset)


class _InlineBodyTransformer(ast.NodeTransformer):
    def __init__(self, func_name, param_names, fmt):
        self.func_name = func_name
        self.param_names = param_names
        self.fmt = fmt

    def visit_Name(self, node):
        if node.id in self.param_names:
            return ast.Subscript(value=ast.Name(self.func_name),
                                 slice=ast.Index(ast.Name(node.id)),
                                 expr_context=getattr(node, 'expr_context', ast.Load()))

    def visit_Return(self, node):
        result = []
        if node.value:
            result.append(ast.Assign(targets=[ast.Subscript(value=ast.name(self.func_name),
                                                            slice=ast.Name('return'),
                                                            expr_context=ast.Store())],
                                     value=node.value))
        result.append(ast.Break())
        return result


class InlineTransformer(TrackedContextTransformer):
    def __init__(self, *args, fun_to_inline=None, fmt=None, **kwargs):
        assert fun_to_inline is not None
        assert fmt is not None
        super().__init__(*args, **kwargs)

        self.fun, self.signature, self.fun_body = fun_to_inline
        self.code_blocks = []


    def nested_visit(self, nodes):
        """When we visit a block of statements, create a new "code block" and push statements into it"""
        lst = []
        self.code_blocks.append(lst)
        for n in nodes:
            res = self.visit(n)
            if res is None:
                continue
            elif isinstance(res, list):
                lst += res
            else:
                lst.append(res)
        self.code_blocks.pop()
        return lst

    def visit_Call(self, node):
        """When we see a function call, insert the function body into the current code block, then replace the call
        with the return expression """
        cur_block = self.code_blocks[-1]

        # Load arguments into their appropriate variables
        args = node.args
        keywords = [(name.id, value) for name, value in node.keywords if name is not None]
        kw_dict = [value for name, value in node.keywords if name is None]
        kw_dict = constant_dict(kw_dict) or {}
        keywords += list(kw_dict.items())
        bound_args = self.signature.bind(*node.args, **odict(keywords))
        self.signature.apply_defaults()

        # Create args dictionary
        # fun_name = {}
        cur_block.append(ast.Assign(targets=[ast.Name(self.fun)], value=ast.Dict(keys=[], values=[])))

        for name, value in bound_args.arguments.items():
            # fun_name['param_name'] = param_value
            cur_block.append(ast.Assign(targets=[ast.Subscript(value=ast.Name(self.fun), slice=ast.Str(name))], value=value))

        # Inline function code
        cur_block += self.fun_body

        # fun_name['return']
        return ast.Subscript(value=ast.Name(self.fun), slice=ast.Str('return'), expr_context=ast.Load())



    ###################################################
    # From here on down, we just have handlers for ever AST node that has a "code block" (stmt*)
    ###################################################

    def visit_FunctionDef(self, node):
        node.body = self.nested_visit(node.body)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        node.body = self.nested_visit(node.body)
        return self.generic_visit(node)

    def visit_ClassDef(self, node):
        node.body = self.nested_visit(node.body)
        return self.generic_visit(node)

    def visit_For(self, node):
        node.body = self.nested_visit(node.body)
        node.orelse = self.nested_visit(node.orelse)
        return self.generic_visit(node)

    def visit_AsyncFor(self, node):
        node.body = self.nested_visit(node.body)
        node.orelse = self.nested_visit(node.orelse)
        return self.generic_visit(node)

    def visit_While(self, node):
        node.body = self.nested_visit(node.body)
        node.orelse = self.nested_visit(node.orelse)
        return self.generic_visit(node)

    def visit_If(self, node):
        node.body = self.nested_visit(node.body)
        node.orelse = self.nested_visit(node.orelse)
        return self.generic_visit(node)

    def visit_With(self, node):
        node.body = self.nested_visit(node.body)
        return self.generic_visit(node)

    def visit_AsyncWith(self, node):
        node.body = self.nested_visit(node.body)
        return self.generic_visit(node)

    def visit_Try(self, node):
        node.body = self.nested_visit(node.body)
        node.body = self.nested_visit(node.orelse)
        node.body = self.nested_visit(node.finalbody)
        return self.generic_visit(node)

    def visit_Module(self, node):
        node.body = self.nested_visit(node.body)
        return self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        node.body = self.nested_visit(node.body)
        return self.generic_visit(node)


# Inline functions?
# You could do something like:
# args, kwargs = (args_in), (kwargs_in)
# function_body
# result = return_expr
@magic_contract
def inline(fun_to_inline):
    """
    :param fun_to_inline: The inner called function that should be inlined in the wrapped function
    :type fun_to_inline: function
    :param args: Other command line arguments (see :func:`collapse_literals` for documentation)
    :type args: tuple
    :param kwargs: Any other environmental variables to provide during unrolling
    :type kwargs: dict
    :return: The unrolled function, or its source code if requested
    :rtype: function
    """
    fname = fun_to_inline.__name__
    fsig = inspect.signature(fun_to_inline)
    _, fbody, _ = function_ast(fun_to_inline)

    new_name = '_{fname}_{name}'

    name_transformer = _InlineBodyTransformer(fname, new_name)
    fbody = [name_transformer.visit(stmt) for stmt in fbody]

    return make_function_transformer(InlineTransformer,
                                     'inline',
                                     'Inline the specified function within the decorated function',
                                     fun_to_inline=(fname, fsig, fbody))
