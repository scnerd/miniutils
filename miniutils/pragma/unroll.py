import copy

from .core import TrackedContextTransformer, make_function_transformer, constant_iterable


# noinspection PyPep8Naming
class UnrollTransformer(TrackedContextTransformer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_vars = set()

    def visit_For(self, node):
        result = [node]
        iterable = constant_iterable(node.iter, self.ctxt)
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


# Unroll literal loops
unroll = make_function_transformer(UnrollTransformer, 'unroll', "Unrolls constant loops in the decorated function")
