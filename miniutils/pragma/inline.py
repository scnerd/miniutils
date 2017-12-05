import ast

from .collapse_literals import collapse_literals
from .core import TrackedContextTransformer


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
    def __init__(self, func_name):
        self.func_name = func_name

    def visit_Name(self, node):
        return ast.Name("_{}_{}".format(self.func_name, node.id))


class InlineTransformer(TrackedContextTransformer):
    def __init__(self, *args, fun_to_inline=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fun, self.signature, self.fun_body = fun_to_inline
        self.code_blocks = []

    def nested_visit(self, nodes):
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

    def visit_Call(self, node):
        cur_block = self.code_blocks[-1]
        cur_block.append()


# Inline functions?
# You could do something like:
# args, kwargs = (args_in), (kwargs_in)
# function_body
# result = return_expr
def inline(function, *args, **kwargs):
    """
    :param function: The inner called function that should be inlined in the wrapped function
    :type function: function
    :param iterable_name: The list's name (must be unique if deindexing multiple lists)
    :type iterable_name: str
    :param args: Other command line arguments (see :func:`unroll` for documentation)
    :type args: tuple
    :param kwargs: Any other environmental variables to provide during unrolling
    :type kwargs: dict
    :return: The unrolled function, or its source code if requested
    :rtype: function
    """

    return collapse_literals(*args, **kwargs)
