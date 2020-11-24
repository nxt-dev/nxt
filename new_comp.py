import time

LAYER = {}

ARO = ['instance', 'parent']


class Node(object):
    def __init__(self, parent_path, name):
        self.parent_path = parent_path
        self.name = name
        self._instance = None

    @property
    def path(self):
        if self.parent_path == '/':
            return '/' + self.name
        return self.parent_path + '/' + self.name

    @property
    def parent(self):
        global LAYER
        parent = self.parent_path
        return LAYER.get(parent, None)

    @property
    def instance(self):
        global LAYER
        instance = self._instance
        return LAYER.get(instance, None)

    def fib():
        x1 = 0
        x2 = 1

        def get_next_number():
            nonlocal x1, x2
            x3 = x1 + x2
            x1, x2 = x2, x3
            return x3

        return get_next_number

    def _get_attr(self, attr):
        arc = 0

        def get():
            global ARO
            nonlocal arc, attr
            try:
                arc_name = ARO[arc]
            except IndexError:
                attr = 0
                return
            arc_node = getattr(self, arc_name, None)
            arc += 1
            return getattr(arc_node, attr, None)
        return get

    def get_attr(self, attr):
        global ARO
        for _ in ARO:
            val = self._get_attr(attr)
            if val:
                return val


# /parent
parent = Node('/', 'parent')
parent.attr1 = 1

# /child
child = Node('/parent', 'child')
child.attr2 = 2
child._instance = '/src'

# /src
src = Node('/', 'src')
src.attr3 = 3

LAYER = {'/parent': parent,
         '/parent/child': child,
         '/src': src}


def new():
    for _ in range(10000):
        ret = child.get_attr('attr1')


class Parent(object):
    attr1 = 1


class Src(object):
    attr3 = 3


class Child(Src, Parent):
    attr2 = 2


def old():
    for _ in range(10000):
        ret = Child().attr1


def recurse(node):
    def _recurse():
        val = getattr(node, 'attr1', None)
        if val:
            return val
        i = -1
        for arc in ['_instance', 'parent_path']:
            i += 1
            np = getattr(node, arc, None)
            if not np:
                continue
            n = LAYER.get(np, None)
            if not n:
                continue
            val = recurse(n)
            if val:
                return val

    for _ in range(1000):
        ret = _recurse()


start = time.time()
for _ in range(10):
    recurse(child)
print('RECURSE: Good ol\' recursion', time.time() - start)


start = time.time()
for _ in range(10):
    old()
print('CURRENT: Using type objects', time.time() - start)

start = time.time()
for _ in range(10):
    new()
print('NEW: Using closure', time.time() - start)
