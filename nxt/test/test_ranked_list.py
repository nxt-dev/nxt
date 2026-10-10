# Builtin
import random
import unittest

# Internal
from nxt.nxt_layer import RankedList


class RankedListMatchesAList(unittest.TestCase):
    """RankedList stands in for a plain list in Stage.sort_instances.

    It only has to support what that code does: ask where an item is, remove
    an item, and insert an item at an index. Every one of those has to give
    the same answer a list would, because the resulting order feeds proxy
    creation order during a comp.
    """

    def test_starts_as_given(self):
        items = [["a"], ["b"], ["c"]]
        ranked = RankedList(items)
        self.assertEqual(ranked.to_list(), items)
        for i, item in enumerate(items):
            self.assertEqual(ranked.index(item), i)

    def test_empty(self):
        ranked = RankedList([])
        self.assertEqual(ranked.to_list(), [])

    def test_insert_into_empty(self):
        ranked = RankedList([])
        item = ["only"]
        ranked.insert(0, item)
        self.assertEqual(ranked.to_list(), [item])
        self.assertEqual(ranked.index(item), 0)

    def test_move_to_front(self):
        items = [["a"], ["b"], ["c"]]
        ranked = RankedList(items)
        ranked.remove(items[2])
        ranked.insert(0, items[2])
        self.assertEqual(ranked.to_list(), [items[2], items[0], items[1]])

    def test_insert_past_the_end_appends(self):
        items = [["a"], ["b"]]
        ranked = RankedList(items)
        ranked.remove(items[0])
        ranked.insert(99, items[0])
        self.assertEqual(ranked.to_list(), [items[1], items[0]])

    def test_matches_a_list_over_random_moves(self):
        """The move sort_instances makes, over and over, on random shapes."""
        random.seed(1979)
        for _ in range(400):
            size = random.randint(0, 30)
            items = [["item%d" % i] for i in range(size)]
            plain = items[:]
            ranked = RankedList(items)
            for _ in range(random.randint(1, 50)):
                if not plain:
                    break
                source = random.choice(plain)
                item = random.choice(plain)
                idx = plain.index(source)
                # sort_instances always inserts a little after the source.
                insert_idx = idx + random.randint(1, 5)
                self.assertEqual(ranked.index(source), idx)
                plain.remove(item)
                plain.insert(insert_idx, item)
                ranked.remove(item)
                ranked.insert(insert_idx, item)
                self.assertEqual(ranked.to_list(), plain)


if __name__ == "__main__":
    unittest.main()
