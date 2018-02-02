import multiprocessing as mp
import itertools
from functools import wraps
from collections import defaultdict

_cpu_count = mp.cpu_count()
_sentinel = (None, None)

def _iter_q(q):
    return iter(q.get, _sentinel)


class BasePipelineElement:
    def __init__(self, daemonize, in_qs, out_qs, parents, nprocs):
        self.i = itertools.count()
        self.procs = {}
        self.daemonize = daemonize
        self.in_qs = in_qs
        self.out_qs = out_qs
        self.parents = parents
        self._all_parent_checks = {}
        self.started = False
        self.closed = False

        self._target_nprocs = None
        self.scale = nprocs

    def start(self, recursive=False):
        self.started = True

        for p in self.procs.values():
            p.daemon = self.daemonize
            p.start()

        if recursive:
            for p in self.parents:
                p.start(recursive=recursive)

    def put(self, *item, queue_num=0):
        self.in_qs[queue_num].put((next(self.i), item))

    def close(self, recursive=False):
        if not self.closed:
            self.closed = True
            for _ in self.procs.values():
                for in_q in self.in_qs:
                    in_q.put(_sentinel)

            for in_q in self.in_qs:
                in_q.close()

        if recursive:
            for p in self.parents:
                p.close(recursive=recursive)

    def join(self, recursive=False):
        self.started = False

        for p in self.procs.values():
            p.join()

        if recursive:
            for p in self.parents:
                p.join(recursive=recursive)

    def finish(self, recursive=False):
        self.close(recursive=recursive)
        self.join(recursive=recursive)

    def terminate(self, recursive=False):
        self.started = False

        for p in self.procs.values():
            p.terminate()

        if recursive:
            for p in self.parents:
                p.terminate(recursive=recursive)

    def __del__(self):
        self.finish()
        self.join()

    def _get_output_queue(self, i=0):
        return self.out_qs[i]

    def __iter__(self):
        return (item for i, item in _iter_q(self._get_output_queue()))

    def has_parent(self, node):
        if node not in self._all_parent_checks:
            self._all_parent_checks[node] = self._has_parent(node)
        return self._all_parent_checks[node]

    def _has_parent(self, node):
        return bool(self.parents and (node in self.parents or any(p.has_parent(node) for p in self.parents)))

    def __hash__(self):
        return hash(id(self))

    @property
    def nprocs(self):
        return len(self.procs)

    def _reap_zombies(self):
        keys = tuple(self.procs.keys())
        for i in keys:
            if self.procs[i].exitcode is not None:
                self.procs[i].join()
                del self.procs[i]

    def _new_proc(self, i=None):
        proc = self._make_proc(i=i)
        if self.started:
            proc.start()
        return proc

    def _make_proc(self, i):
        raise NotImplementedError("{} must implement, or be extended to implement, _make_proc".format(type(self)))

    @property
    def scale(self):
        return self._target_nprocs

    @scale.setter
    def scale(self, value):
        self._target_nprocs = value

        self._reap_zombies()

        if self.nprocs < self._target_nprocs:
            make_keys = set(range(self._target_nprocs)) - set(self.procs.keys())
            for k in make_keys:
                self.procs[k] = self._new_proc()

        elif self.nprocs > self._target_nprocs:
            kill_keys = list(sorted(self.procs.keys(), reverse=True))[:self.nprocs - self._target_nprocs]
            for k in kill_keys:
                self.put(_sentinel)


class Pipeline(BasePipelineElement):
    def __init__(self, entry, exit, inp_queue_num=0, out_queue_num=0):
        super().__init__(daemonize=None, in_qs=[entry.in_qs[inp_queue_num]], out_qs=[exit.out_qs[out_queue_num]],
                         parents=entry.parents, nprocs=0)
        self.entry = entry
        self.exit = exit
        self.contains = set(self.get_all_parents())
        if self.entry not in self.contains:
            raise ValueError("'{}' is not a parent of '{}'".format(entry, exit))

    def get_all_parents(self):
        def required_parents(node):
            if node is self.entry:
                yield node
            elif node.has_parent(self.entry):
                yield node
                for p in node.parents:
                    yield from required_parents(p)
        return set(required_parents(self.exit))

    def start(self, *args, **kwargs):
        for c in self.contains:
            c.start(*args, **kwargs)

    def close(self, *args, **kwargs):
        for c in self.contains:
            c.close(*args, **kwargs)

    def join(self, *args, **kwargs):
        for c in self.contains:
            c.close(*args, **kwargs)

    def terminate(self, *args, **kwargs):
        for c in self.contains:
            c.close(*args, **kwargs)

    def has_parent(self, node):
        return any(c.has_parent(node) for c in self.contains)

    def _make_proc(self, i):
        super()._make_proc()


def _get_queue(element, limit=None):
    if element is None:
        return mp.Queue(limit)
    elif isinstance(element, BasePipelineElement):
        return element._get_output_queue()
    elif isinstance(element, mp.Queue):
        return element
    else:
        raise TypeError("Unknown type '{}' for input element to a Pipeline".format(type(element)))


class PipelineElement(BasePipelineElement):
    def __init__(self, previous_element=None, nprocs=1, in_limit=None, out_limit=None,
                 daemonize=True):

        parents = [previous_element] if previous_element else []

        self.in_q = _get_queue(previous_element, in_limit)

        self.out_q = mp.Queue(out_limit)

        super().__init__(daemonize=daemonize, in_qs=[self.in_q], out_qs=[self.out_q], parents=parents, nprocs=nprocs)

    @property
    def _target_func(self):
        def inner(in_q, out_q):
            for e in _iter_q(in_q.get):
                out_q.put(e)
        return inner

    def _make_proc(self, i):
        return mp.Process(target=self._target_func, args=(self.in_q, self.out_q), daemon=self.daemonize)


class PipelineMap(PipelineElement):
    def __init__(self, map_func, *args, init_func=None, init_kwargs=None, flatmap=False, keyed=False, **kwargs):
        self.map_func = map_func
        self.init_func = init_func
        self.init_kwargs = init_kwargs or {}
        self.flatmap = flatmap
        self.keyed = keyed
        super().__init__(*args, **kwargs)

    @property
    def _target_func(self):
        # Heh, this is sneaky... a property that returns a function
        # This is perhaps a bit fidgety, but means that the function is statically defined with a closure
        # Thus, changes to self won't affect functions that were already defined
        # This is important because the child processes get spawned with this returned function
        # It's therefore important to make sure that this entire pipeline element doesn't get copied, just the
        #  attributes that are needed to run the child process
        map_func = self.map_func
        init_func = self.init_func
        init_kwargs = self.init_kwargs
        keyed = self.keyed

        if self.flatmap:
            @wraps(self.map_func)
            def inner(in_q, out_q):
                key = None
                if init_func:
                    init_func(**init_kwargs)
                for (i, item) in _iter_q(in_q.get):
                    if keyed:
                        key, item = item
                    for j, result in enumerate(map_func(*item)):
                        result = (key, result) if keyed else result
                        out_q.put(((i, j), result))
        else:
            @wraps(self.map_func)
            def inner(in_q, out_q):
                key = None
                if init_func:
                    init_func(**init_kwargs)
                for (i, item) in _iter_q(in_q.get):
                    if keyed:
                        key, item = item
                    result = map_func(*item)
                    result = (key, result) if keyed else result
                    out_q.put((i, result))

        return inner


class PipelineKey(PipelineMap):
    def __init__(self, key_func, *args, **kwargs):
        super().__init__(lambda x: (key_func(x), x), *args, **kwargs)


class PipelineReduce(PipelineElement):
    def __init__(self, reduce_func, reduce_init, *args, **kwargs):
        self.reduce_func = reduce_func
        self.reduce_init = reduce_init
        super().__init__(*args, **kwargs)

    @property
    def _target_func(self):
        reduce_func = self.reduce_func
        reduce_init = self.reduce_init

        # TODO: Implement when values are keyed

        def inner(in_q, out_q):
            val = reduce_init
            for i, next_val in _iter_q(in_q.get):
                val = reduce_func(val, next_val)
            out_q.put((0, val))

        return inner


class PipelineFilter(PipelineElement):
    def __init__(self, filter_func, *args, **kwargs):
        self.filter_func = filter_func
        super().__init__(*args, **kwargs)

    @property
    def _target_func(self):
        filter_func = self.filter_func

        # TODO: Implement when values are keyed

        @wraps(filter_func)
        def inner(in_q, out_q):
            new_count = itertools.count()
            for i, e in _iter_q(in_q):
                if filter_func(e):
                    out_q.put(next(new_count), e)

        return inner


class PipelineTee(BasePipelineElement):
    def __init__(self, n_out, previous_element=None, in_limit=None, out_limit=None, daemonize=True):

        parents = [previous_element] if previous_element else []

        self.in_q = _get_queue(previous_element, in_limit)

        super().__init__(daemonize=daemonize, in_qs=[self.in_q],
                         out_qs=[mp.Queue(out_limit) for _ in range(n_out)], parents=parents, nprocs=1)

    def _make_proc(self, i):
        return mp.Process(target=self._tee_func, args=(self.in_qs[0], self.out_qs))

    @staticmethod
    def _tee_func(in_q, out_qs):
        for e in _iter_q(in_q):
            for out_q in out_qs:
                out_q.put(e)


class PipelineMerge(BasePipelineElement):
    def __init__(self, *previous_elements, in_limit=None, out_limit=None, daemonize=True):

        self.out_q = mp.Queue(out_limit)

        super().__init__(daemonize=daemonize, in_qs=[_get_queue(e, in_limit) for e in previous_elements],
                         out_qs=[self.out_q], parents=previous_elements, nprocs=len(previous_elements))

    def _make_proc(self, i):
        return mp.Process(target=self._merge_func, args=(self.in_qs[i], self.out_qs[0]))

    @staticmethod
    def _merge_func(in_q, out_q):
        for e in _iter_q(in_q):
            out_q.put(e)




























