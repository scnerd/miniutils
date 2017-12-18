from .core import *
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

DICT_FMT = "_{fname}_{n}"

# @magic_contract
def make_name(fname, var, n, ctx=ast.Load):
    """
    Create an AST node to represent the given argument name in the given function
    :param fname: Function name
    :type fname: str
    :param var: Argument name
    :type var: str
    :param ctx: Context of this name (LOAD or STORE)
    :type ctx: Load|Store
    :param n: The number to append to this name (to allow for finite recursion)
    :type n: int
    :param fmt: Name format (if not stored in a dictionary)
    :type fmt: str
    :return: An AST node representing this argument
    :rtype: Subscript|Call
    """
    return ast.Subscript(value=ast.Name(id=DICT_FMT.format(fname=fname, n=n), ctx=ast.Load()),
                         slice=ast.Index(ast.Str(var)),
                         ctx=ctx())


def make_return(fname, n, ctx):
    return ast.Name(id=DICT_FMT.format(fname=fname, n=n), ctx=ctx())


class _InlineBodyTransformer(TrackedContextTransformer):
    def __init__(self, func_name, param_names, n):
        self.func_name = func_name
        # print("Func {} takes parameters {}".format(func_name, param_names))
        self.param_names = param_names
        self.in_break_block = False
        self.n = n
        self.had_return = False
        self.had_yield = False
        super().__init__()

    def visit_Name(self, node):
        # Check if this is a parameter, and hasn't had another value assigned to it
        if node.id in self.param_names:
            # print("Found parameter reference {}".format(node.id))
            if node.id not in self.ctxt:
                # If so, get its value from the argument dictionary
                return make_name(self.func_name, node.id, self.n, ctx=type(getattr(node, 'ctx', ast.Load())))
            else:
                # print("But it's been overwritten to {} = {}".format(node.id, self.ctxt[node.id]))
                pass
        return node

    def visit_Return(self, node):
        if self.in_break_block:
            raise NotImplementedError("miniutils.pragma.inline cannot handle returns from within a loop")
        result = []
        if node.value:
            result.append(ast.Assign(targets=[make_name(self.func_name, 'return', self.n, ctx=ast.Store)],
                                     value=self.visit(node.value)))
        result.append(ast.Break())
        self.had_return = True
        return result

    def visit_Yield(self, node):
        self.had_yield = True
        if node.value:
            return ast.Call(func=ast.Attribute(value=make_name(self.func_name, 'yield', self.n, ctx=ast.Load),
                                               attr='append',
                                               ctx=ast.Load),
                            args=[self.visit(node.value)],
                            keywords=[])
        return node

    def visit_YieldFrom(self, node):
        self.had_yield = True
        return ast.Call(func=ast.Attribute(value=make_name(self.func_name, 'yield', self.n, ctx=ast.Load),
                                           attr='extend',
                                           ctx=ast.Load),
                        args=[self.visit(node.value)],
                        keywords=[])

    def visit_For(self, node):
        orig_in_break_block = self.in_break_block
        self.in_break_block = True
        res = self.generic_visit(node)
        self.in_break_block = orig_in_break_block
        return res

    def visit_While(self, node):
        orig_in_break_block = self.in_break_block
        self.in_break_block = True
        res = self.generic_visit(node)
        self.in_break_block = orig_in_break_block
        return res

    def visit_FunctionDef(self, node):
        return node

    def visit_AsyncFunctionDef(self, node):
        return node

    def visit_ClassDef(self, node):
        return node


class InlineTransformer(TrackedContextTransformer):
    def __init__(self, *args, funs=None, max_depth=1, **kwargs):
        assert funs is not None
        super().__init__(*args, **kwargs)

        self.funs = funs
        self.code_blocks = []
        self.max_depth = max_depth

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
        node = self.generic_visit(node)
        node_fun = resolve_name_or_attribute(resolve_literal(node.func, self.ctxt), self.ctxt)

        for (fun, fname, fsig, fbody) in self.funs:
            if fun != node_fun:
                continue

            n = 0
            for i in range(self.max_depth):
                args_dict_name = DICT_FMT.format(fname=fname, n=i)
                n = i  # This is redundant, but a bit clearer and safer than just referencing i later
                if args_dict_name not in self.ctxt:
                    break
            else:
                warnings.warn("Inline hit recursion limit, using normal function call")
                return node

            print([k for k in self.ctxt if k not in globals()])
            print("Inlining {}".format(args_dict_name))
            func_for_inlining = _InlineBodyTransformer(fname, fsig.parameters, n)
            fbody = list(func_for_inlining.visit_many(copy.deepcopy(fbody)))

            # TODO: Check if function is generator, and if so produce its list instead of a return value
            cur_block = self.code_blocks[-1]
            new_code = []

            # Load arguments into their appropriate variables
            args = node.args
            keywords = [(kw.arg, kw.value) for kw in node.keywords if kw.arg is not None]
            kw_dict = [kw.value for kw in node.keywords if kw.arg is None]
            kw_dict = kw_dict[0] if kw_dict else None
            bound_args = fsig.bind(*node.args, **odict(keywords))
            bound_args.apply_defaults()

            # Create args dictionary
            # fun_name = {}
            new_code.append(ast.Assign(targets=[ast.Name(id=args_dict_name, ctx=ast.Store())],
                                       value=ast.Dict(keys=[], values=[])))

            for arg_name, arg_value in bound_args.arguments.items():
                if isinstance(arg_value, tuple):
                    arg_value = ast.Tuple(elts=list(arg_value), ctx=ast.Load())
                elif isinstance(arg_value, dict):
                    keys, values = zip(*list(arg_value.items()))
                    keys = [ast.Str(k) for k in keys]
                    values = list(values)
                    arg_value = ast.Dict(keys=keys, values=values)
                # fun_name['param_name'] = param_value
                new_code.append(ast.Assign(targets=[make_name(fname, arg_name, n, ast.Store)],
                                           value=arg_value))

            if kw_dict:
                # fun_name.update(kwargs)
                new_code.append(ast.Call(func=ast.Attribute(value=ast.Name(args_dict_name, ctx=ast.Load()),
                                                            attr='update',
                                                            ctx=ast.Load()),
                                          args=[kw_dict],
                                          keywords=[]))

            if func_for_inlining.had_yield:
                new_code.append(ast.Assign(targets=[make_name(fname, 'yield', n, ast.Store)],
                                           value=ast.List(elts=[])))
            if func_for_inlining.had_return:
                new_code.append(ast.Assign(targets=[make_name(fname, 'return', n, ast.Store)],
                                           value=ast.NameConstant(None)))

            # Process assignments before resolving body
            cur_block.extend(self.visit_many(new_code))

            # Inline function code
            new_body = list(self.visit_many(fbody))

            # cur_block.append(self.visit(ast.For(target=ast.Name(id='____', ctx=ast.Store()),
            #                                     iter=ast.List(elts=[ast.NameConstant(None)], ctx=ast.Load()),
            #                                     body=new_body,
            #                                     orelse=[])))
            cur_block.append(ast.For(target=ast.Name(id='____', ctx=ast.Store()),
                                    iter=ast.List(elts=[ast.NameConstant(None)], ctx=ast.Load()),
                                    body=new_body,
                                    orelse=[]))

            # fun_name['return']
            if func_for_inlining.had_yield or func_for_inlining.had_return:
                for j in range(100000):
                    output_name = DICT_FMT.format(fname=fname + '_return', n=j)
                    if output_name not in self.ctxt:
                        break
                else:
                    raise RuntimeError("Function {} called and returned too many times during inlining, not able to "
                                       "put the return value into a uniquely named variable".format(fname))

                if func_for_inlining.had_yield:
                    cur_block.append(self.visit(ast.Assign(targets=[ast.Name(id=output_name, ctx=ast.Store())],
                                                           value=make_name(fname, 'yield', n))))
                elif func_for_inlining.had_return:
                    cur_block.append(self.visit(ast.Assign(targets=[ast.Name(id=output_name, ctx=ast.Store())],
                                                           value=make_name(fname, 'return', n))))

                cur_block.append(self.visit(ast.Delete(targets=[ast.Name(id=args_dict_name, ctx=ast.Del())])))
                return ast.Name(id=output_name, ctx=ast.Load())
            else:
                return ast.NameConstant(None)
                # return ast.Pass()

        else:
            return node



    ###################################################
    # From here on down, we just have handlers for ever AST node that has a "code block" (stmt*)
    ###################################################

    def visit_FunctionDef(self, node):
        self.ctxt.push({}, False)
        node.body = self.nested_visit(node.body)
        self.ctxt.pop()
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.ctxt.push({}, False)
        node.body = self.nested_visit(node.body)
        self.ctxt.pop()
        return self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.ctxt.push({}, False)
        node.body = self.nested_visit(node.body)
        self.ctxt.pop()
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


# @magic_contract
def inline(*funs_to_inline, max_depth=1, **kwargs):
    """
    :param funs_to_inline: The inner called function that should be inlined in the wrapped function
    :type funs_to_inline: tuple(function)
    :param max_depth: The maximum number of times to inline the provided function (limits recursion)
    :type max_depth: int
    :return: The unrolled function, or its source code if requested
    :rtype: function
    """
    funs = []
    for fun_to_inline in funs_to_inline:
        fname = fun_to_inline.__name__
        fsig = inspect.signature(fun_to_inline)
        _, fbody, _ = function_ast(fun_to_inline)

        funs.append((fun_to_inline, fname, fsig, fbody))

    return make_function_transformer(InlineTransformer,
                                     'inline',
                                     'Inline the specified function within the decorated function',
                                     funs=funs, max_depth=max_depth)(**kwargs)
