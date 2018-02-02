import multiprocessing as mp
import queue
import itertools
import os
import traceback
from functools import wraps
from miniutils import logs_base as log

_cpu_count = mp.cpu_count()
_sentinel = (None, None)


def _iter_q(q):
    try:
        yield from iter(q.get, _sentinel)
        q.close()
    except queue.Empty:
        pass


class _Executor(mp.Process):
    def __init__(self, target, *args, **kwargs):
        self.mgmt_q = mp.Queue()
        super().__init__(*args, target=self.wrap(target), **kwargs)

    def wrap(self, f):
        mgmt_q = self.mgmt_q
        del self

        @wraps(f)
        def inner(in_qs, out_qs):
            pid = os.getpid()
            log.debug("Process {} starting".format(pid))
            try:
                f(in_qs, out_qs)
            except Exception as ex:
                log.error("Process {} failed:\n{}".format(pid, traceback.format_exc()))
                mgmt_q.put(ex)
            log.debug("Process {} passing sentinels".format(pid))
            if not isinstance(out_qs, (list, tuple)):
                out_qs = [out_qs]
            for q in out_qs:
                q.put(_sentinel)
            log.debug("Process {} complete".format(pid))
            mgmt_q.put(None)

        return inner

    def __repr__(self):
        return "<Process {}>".format(self.pid or "???")


class _DummyExecutor:
    def __init__(self, *args, **kwargs):
        log.warning("Attempted to initialize dummy executor")

    def start(self):
        log.warning("Attempted to start dummy executor")

    def join(self):
        log.warning("Attempted to join dummy executor")

    def terminate(self):
        log.warning("Attempted to terminate dummy executor")

    def __repr__(self):
        return "<Dummy Process>"

    @property
    def pid(self):
        return None


# TODO: Split Pipeline from BasePipelineElement. Trying to make these the same thing is too complicated, just require all elements to belong to a pipeline (like a tensorflow graph)


class BasePipelineElement:
    def __init__(self, in_qs, out_qs, parents, nprocs=1, daemonize=True, single_output=False):
        self.i = itertools.count()
        self.procs = {}
        self.daemonize = daemonize
        self.in_qs = in_qs
        self.out_qs = out_qs
        self.parents = [p if not isinstance(p, Pipeline) else p.exit for p in parents]
        self._all_parent_checks = {}
        self.single_output = single_output

        self.started = False
        self.closed = False
        self.joined = False

        self._target_nprocs = None
        self.scale = nprocs

    def start(self, recursive=False):
        log.debug("Element {} started".format(self))
        if not self.started:
            self.started = True

            for p in self.procs.values():
                p.start()
                log.debug("Process {}_{} started".format(self, p))

            if recursive:
                for p in self.parents:
                    p.start(recursive=recursive)

    def put(self, *item, queue_num=0):
        # log.debug("{} added to {}:{}".format(item, self, queue_num))
        self.in_qs[queue_num].put((next(self.i), item))

    def put_all(self, *items, queue_num=0, make_tuple=True):
        for item in items:
            if make_tuple:
                self.put(item, queue_num=queue_num)
            else:
                self.put(*item, queue_num=queue_num)

    def close(self, recursive=False):
        if not self.closed and not self.joined:
            log.debug("Element {} closing".format(self))
            self.closed = True

            for in_q in self.in_qs:
                in_q.put(_sentinel)
                in_q.close()

            if recursive:
                for p in self.parents:
                    p.close(recursive=recursive)

    def join(self, recursive=False):
        log.debug("Element {} joining".format(self))
        if not self.joined:
            self.started = False
            self.joined = True

            for p in self.procs.values():
                p.join()
                log.debug("Process {}_{} joined".format(self, p))

            if recursive:
                for p in self.parents:
                    p.join(recursive=recursive)

    def finish(self, recursive=False):
        if not self.closed:
            self.close(recursive=recursive)
            self.join(recursive=recursive)

    def terminate(self, recursive=False):
        log.debug("Element {} terminating".format(self))
        self.started = False

        for p in self.procs.values():
            p.terminate()
            log.debug("Process {}_{} terminated".format(self, p))

        if recursive:
            for p in self.parents:
                p.terminate(recursive=recursive)

    def __del__(self):
        log.debug("Element {} being deleted".format(self))
        self.finish()

    def _get_output_queue(self, i=None):
        return self.out_qs[i or 0]

    def __iter__(self):
        results = (item for i, item in _iter_q(self._get_output_queue()))
        if self.single_output:
            results = (item for (item,) in results)
        return results

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
                log.debug("Process {}_{} found with exit code {}".format(self, self.procs[i], self.procs[i].exitcode))
                self.procs[i].join()
                log.debug("Process {}_{} reaped".format(self, self.procs[i]))
                del self.procs[i]

    def _new_proc(self, i=None):
        proc = self._make_proc(i=i)
        log.debug("Creating new process {}_{} for id={}".format(self, proc, i))
        if self.started:
            proc.start()
            log.debug("Process {}_{} started".format(self, proc))
        return proc

    def _make_proc(self, i):
        return _DummyExecutor()

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
            # kill_keys = list(sorted(self.procs.keys(), reverse=True))[:self.nprocs - self._target_nprocs]
            # for k in kill_keys:
            for _ in range(self.nprocs - self._target_nprocs):
                self.put(_sentinel)

    def __repr__(self):
        return "<{} {}>".format(type(self).__name__, id(self))

    def graphviz(self):
        return """
digraph {{

{nodes}

{edges}

}}
        """.format(nodes="\n".join(sorted(set(self._dot_nodes()))),
                   edges="\n".join(sorted(set(self._dot_edges()))))

    def _dot_id(self):
        return str(id(self))

    def _dot_nodes(self):
        yield '{} [label="{}"];'.format(self._dot_id(), repr(self))
        for p in self.parents:
            yield from p._dot_nodes()

    def _dot_edges(self):
        for p in self.parents:
            yield '{} -> {};'.format(p._dot_id(), self._dot_id())
            yield from p._dot_edges()

    def map(self, *args, **kwargs):
        return Pipeline(self, Map(*args, **kwargs, previous_element=self))

    def reduce(self, *args, **kwargs):
        return Pipeline(self, Reduce(*args, **kwargs, previous_element=self))

    def filter(self, *args, **kwargs):
        return Pipeline(self, Filter(*args, **kwargs, previous_element=self))

    def group(self, *args, **kwargs):
        return Pipeline(self, Group(*args, **kwargs, previous_element=self))

    def key(self, *args, **kwargs):
        return Pipeline(self, Key(*args, **kwargs, previous_element=self))

    def tee(self, *args, **kwargs):
        return Pipeline(self, Tee(*args, **kwargs, previous_element=self))

    def progbar(self, *args, **kwargs):
        return Pipeline(self, ProgressBar(*args, **kwargs, previous_element=self))


class Pipeline(BasePipelineElement):
    def __init__(self, entry, exit, **kwargs):
        super().__init__(in_qs=entry.in_qs, out_qs=exit.out_qs, parents=entry.parents, **kwargs, nprocs=0)
        entry = entry if not isinstance(entry, Pipeline) else entry.entry
        self.entry = entry
        self.exit = exit
        self.contains = set(self.get_all_parents())
        if self.entry not in self.contains:
            raise ValueError("'{}' is not a parent of '{}'".format(entry, exit))

        log.debug("Created new pipeline of {} -> {} (also contains {})".format(entry, exit, self.contains - {entry, exit}))

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
        self.entry.close(*args, **kwargs)

    def finish(self, *args, **kwargs):
        self.close()
        self.join()

    def __del__(self):
        pass

    def join(self, *args, **kwargs):
        for c in self.contains:
            c.join(*args, **kwargs)

    def terminate(self, *args, **kwargs):
        for c in self.contains:
            c.terminate(*args, **kwargs)

    def has_parent(self, node):
        return any(c.has_parent(node) for c in self.contains)

    def _get_output_queue(self, i=None):
        return self.exit._get_output_queue(i=i)

    def _dot_id(self):
        return self.exit._dot_id()

    def _dot_nodes(self):
        return self.exit._dot_nodes()

    def _dot_edges(self):
        return self.exit._dot_edges()


def _get_queue(element, limit=None):
    if element is None:
        return mp.Queue(limit or 0)
    elif isinstance(element, BasePipelineElement):
        return element._get_output_queue()
    elif isinstance(element, mp.Queue):
        return element
    else:
        raise TypeError("Unknown type '{}' for input element to a Pipeline".format(type(element)))


class PipelineElement(BasePipelineElement):
    def __init__(self, previous_element=None, in_limit=None, out_limit=None, **kwargs):

        parents = [previous_element] if previous_element else []

        self.in_q = _get_queue(previous_element, in_limit)

        self.out_q = _get_queue(None, out_limit)

        super().__init__(in_qs=[self.in_q], out_qs=[self.out_q], parents=parents, **kwargs)

    @property
    def _target_func(self):
        del self

        def inner(in_q, out_q):
            for e in _iter_q(in_q):
                out_q.put(e)
        return inner

    def _make_proc(self, i):
        return _Executor(target=self._target_func, args=(self.in_q, self.out_q), daemon=self.daemonize)

    def __repr__(self):
        return "<{} ({}) {}>".format(type(self).__name__, self._target_func.__name__, id(self))


class Source(BasePipelineElement):
    def __init__(self, cache_limit=None, **kwargs):
        self.q = _get_queue(None, cache_limit)

        super().__init__(in_qs=[self.q], out_qs=[self.q], parents=[], **kwargs, nprocs=0)


class ProgressBar(PipelineElement):
    def __init__(self, *args, total=None, **kwargs):
        from miniutils.progress_bar import progbar
        self.progbar = progbar(itertools.count(), total=total)
        super().__init__(*args, **kwargs)

    @property
    def _target_func(self):
        progbar = iter(self.progbar)
        del self

        def inner(in_q, out_q):
            for e in _iter_q(in_q):
                next(progbar)
                out_q.put(e)

        return inner


class Map(PipelineElement):
    def __init__(self, map_func, init_func=None, init_kwargs=None, *, flatmap=False, keyed=False, **kwargs):
        self.map_func = map_func
        self.init_func = init_func
        self.init_kwargs = init_kwargs or {}
        self.flatmap = flatmap
        self.keyed = keyed
        super().__init__(**kwargs)

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
        flatmap = self.flatmap
        del self

        if flatmap:
            @wraps(map_func)
            def inner(in_q, out_q):
                key = None
                if init_func:
                    init_func(**init_kwargs)
                for (i, item) in _iter_q(in_q):
                    if keyed:
                        key, item = item
                    # log.debug("Mapper {} processing {}".format(os.getpid(), item))
                    for j, result in enumerate(map_func(*item)):
                        result = (key, result) if keyed else result
                        result = result if isinstance(result, tuple) else (result,)
                        out_q.put(((i, j), result))
        else:
            @wraps(map_func)
            def inner(in_q, out_q):
                key = None
                if init_func:
                    init_func(**init_kwargs)
                for (i, item) in _iter_q(in_q):
                    if keyed:
                        key, item = item
                    log.debug("Mapper {} processing {}".format(os.getpid(), item))
                    result = map_func(*item)
                    result = (key, result) if keyed else result
                    result = result if isinstance(result, tuple) else (result,)
                    out_q.put((i, result))

        return inner


class Key(Map):
    def __init__(self, key_func, *args, **kwargs):
        super().__init__(lambda x: (key_func(x), x), *args, **kwargs)


class Reduce(PipelineElement):
    def __init__(self, reduce_func, reduce_init, *args, keyed=False, **kwargs):
        self.reduce_func = reduce_func
        self.reduce_init = reduce_init
        self.keyed = keyed
        if keyed:
            self.manager = mp.Manager()
            self.dct = self.manager.dict()
            self.dct_lock = self.manager.Lock()
        super().__init__(*args, **kwargs)

    @property
    def _target_func(self):
        reduce_func = self.reduce_func
        reduce_init = self.reduce_init

        if self.keyed:
            dct = self.dct
            dct_lock = self.dct_lock
            del self

            def inner(in_q, out_q):
                reduce_initer = reduce_init if callable(reduce_init) else lambda: reduce_init
                for i, (next_key, next_val) in _iter_q(in_q):
                    log.debug("Reducer {} processing {}".format(os.getpid(), (next_key, next_val)))
                    with dct_lock:
                        dct[next_key] = reduce_func(dct.get(next_key, reduce_initer()), *next_val)
                with dct_lock:
                    try:
                        for i in itertools.count():  # Only a single process here, so no need to sync
                            key, val = dct.popitem()
                            val = val if isinstance(val, tuple) else (val,)
                            out_q.put((i, (key, val)))
                    except KeyError:
                        pass  # Done iterating over dict

        else:
            del self

            def inner(in_q, out_q):
                reduce_initer = reduce_init if callable(reduce_init) else lambda: reduce_init
                val = reduce_initer()
                for i, next_val in _iter_q(in_q):
                    log.debug("Reducer {} processing {}".format(os.getpid(), next_val))
                    val = reduce_func(val, *next_val)

                val = val if isinstance(val, tuple) else (val,)
                out_q.put((0, val))

        return inner


class Group(Reduce):
    def __init__(self, *args, **kwargs):
        super().__init__(list.append, list)


class Filter(PipelineElement):
    def __init__(self, filter_func, *args, keyed=False, **kwargs):
        self.filter_func = filter_func
        self.keyed = keyed
        super().__init__(*args, **kwargs)

    @property
    def _target_func(self):
        filter_func = self.filter_func
        keyed = self.keyed
        del self

        @wraps(filter_func)
        def inner(in_q, out_q):
            new_count = itertools.count()
            for i, e in _iter_q(in_q):
                # log.debug("Filter {} processing {}".format(os.getpid(), e))
                if filter_func(e[1]) if keyed else filter_func(e):
                    out_q.put(next(new_count), e)

        return inner


class Tee(BasePipelineElement):
    def __init__(self, n_out, previous_element=None, in_limit=None, out_limit=None, **kwargs):

        parents = [previous_element] if previous_element else []

        self.in_q = _get_queue(previous_element, in_limit)
        self.out_counter = iter(range(n_out))

        super().__init__(in_qs=[self.in_q], out_qs=[_get_queue(None, out_limit) for _ in range(n_out)], parents=parents,
                         **kwargs, nprocs=1)

    def _make_proc(self, i):
        return _Executor(target=self._tee_func, args=(self.in_qs[0], self.out_qs))

    @staticmethod
    def _tee_func(in_q, out_qs):
        for e in _iter_q(in_q):
            # log.debug("Tee {} duplicating {} {} ways".format(os.getpid(), e, len(out_qs)))
            for out_q in out_qs:
                out_q.put(e)

    def _get_output_queue(self, i=None):
        if i is None:
            i = next(self.out_counter)
        return self.out_qs[i]


class Merge(BasePipelineElement):
    def __init__(self, *previous_elements, in_limit=None, out_limit=None, **kwargs):

        self.out_q = _get_queue(None, out_limit)

        super().__init__(in_qs=[_get_queue(e, in_limit) for e in previous_elements],
                         out_qs=[self.out_q], parents=previous_elements, **kwargs, nprocs=len(previous_elements))

    def _make_proc(self, i):
        return _Executor(target=self._merge_func, args=(self.in_qs[i], self.out_qs[0]))

    @staticmethod
    def _merge_func(in_q, out_q):
        for e in _iter_q(in_q):
            # log.debug("Merger {} received {} from {}".format(os.getpid(), e, in_q))
            out_q.put(e)

























