"""
Group mode
"""
from boltons.typeutils import make_sentinel

from .core import glom, MODE, SKIP, STOP


ACC = make_sentinel('ACC')
ACC.__doc__ = """
current accumulator for aggregation;
structure roughly corresponds to the result,
but is not 1:1; instead the main purpose is to ensure
data is kept until the Group() finishes executing
"""


class Group(object):
    """
    supports nesting grouping operations --
    think of a glom-style recursive boltons.iterutils.bucketize

    the "branches" of a Group spec are dicts;
    the leaves are lists, or an Aggregation object
    an Aggregation object is any object that defines the
    method agg(target, accumulator)

    target is the current target, accumulator is a dict
    maintained by Group mode

    unlike Iter(), Group() converts an iterable target
    into a single result; Iter() converts an iterable
    target into an iterable result
    """
    def __init__(self, spec):
        self.spec = spec

    def glomit(self, target, scope):
        scope[MODE] = _group
        scope[ACC] = {}
        ret = None
        for t in target:
            last, ret = ret, scope[glom](t, self.spec, scope)
            if ret is STOP:
                return last
        return ret


def _group(target, spec, scope):
    """
    Group mode dispatcher
    """
    recurse = lambda spec: scope[glom](target, spec, scope)
    acc2 = scope[ACC]  # current acuumulator support structure
    if callable(getattr(spec, "agg", None)):
        return spec.agg(target, acc2)
    elif callable(spec):
        return spec(target)
    if type(spec) not in (dict, list):
        raise TypeError("not a valid spec")
    if id(spec) in acc2:
        acc = acc2[id(spec)]  # current accumulator
    else:
        acc = acc2[id(spec)] = type(spec)()
    if type(spec) is dict:
        done = True
        for keyspec, valspec in spec.items():
            if acc2.get(keyspec, None) is STOP:
                continue
            key = recurse(keyspec)
            if key is SKIP:
                done = False  # SKIP means we still want more vals
                continue
            if key is STOP:
                acc2[keyspec] = STOP
                continue
            if key not in acc:
                # TODO: guard against key == id(spec)
                acc2[key] = {}
            scope[ACC] = acc2[key]
            result = recurse(valspec)
            if result is STOP:
                acc2[keyspec] = STOP
                continue
            done = False  # SKIP or returning a value means we still want more vals
            if result is not SKIP:
                acc[key] = result
        if done:
            return STOP
        return acc
    elif type(spec) is list:
        for valspec in spec:
            assert type(valspec) is not dict
            # dict inside list is not valid
            result = recurse(valspec)
            if result is STOP:
                return STOP
            if result is not SKIP:
                acc.append(result)
        return acc


class First(object):
    """
    holds onto the first value

    >>> glom([1, 2, 3], Group(First()))
    1
    """
    __slots__ = ()

    def agg(self, target, acc2):
        if self not in acc2:
            acc2[self] = STOP
            return target
        return STOP


class Avg(object):
    """
    takes the numerical average of all values;
    raises exception on non-numeric value

    >>> glom([1, 2, 3], Group(Avg()))
    2.0
    """
    __slots__ = ()

    def agg(self, target, acc2):
        if self not in acc2:
            acc2[self] = [0, 0.0]
        acc2[self][0] += target
        acc2[self][1] += 1
        return acc2[self][0] / acc2[self][1]


class Sum(object):
    """
    takes the sum of all values;
    raises exception on values incompatible with addition operator

    >>> glom([1, 2, 3], Group(Sum()))
    6
    """
    __slots__ = ()

    def agg(self, target, acc2):
        if self not in acc2:
            acc2[self] = 0
        acc2[self] += target
        return acc2[self]


class Max(object):
    """
    takes the maximum of all values;
    raises exception on values that are not comparable

    >>> glom([1, 2, 3], Group(Max()))
    3
    """
    __slots__ = ()

    def agg(self, target, acc2):
        if self not in acc2:
            acc2[self] = target
        if target > acc2[self]:
            acc2[self] = target
        return acc2[self]


class Min(object):
    """
    takes the minimum of all values;
    raises exception on values that are not comparable

    >>> glom([1, 2, 3], Group(Min()))
    1
    """
    __slots__ = ()

    def agg(self, target, acc2):
        if self not in acc2:
            acc2[self] = target
        if target < acc2[self]:
            acc2[self] = target
        return acc2[self]


class Count(object):
    """
    takes a count of how many values occurred

    >>> glom([1, 2, 3], Group(Count()))
    3
    """
    __slots__ = ()

    def agg(self, target, acc2):
        if self not in acc2:
            acc2[self] = 0
        acc2[self] += 1
        return acc2[self]


'''
NOTE: this cannot be done as an aggregator since they are
not recursive; enable when recursion is available again
once grouping / reduction merge is complete

class Limit(object):
    """
    limits the number of values passed to sub-accumulator

    >>> glom([1, 2, 3], Group(T))
    3
    >>> glom([1, 2, 3], Group(Limit(1, T)))
    1
    """
    __slots__ = ('n', 'agg')

    def __init__(self, n, agg):
        self.n, self.agg = n, agg

    def agg(self, target, acc2):
        if self not in acc2:
            acc2[self] = 0
        acc2[self] += 1
        if acc2[self] > self.n:
            return STOP
        return self.agg.agg(target, acc2)
'''
