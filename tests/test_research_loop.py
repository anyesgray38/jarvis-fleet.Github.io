import unittest

from discovery.agenda import AgendaBuilder
from discovery.autonomy import ResearchOpportunity, ResearchTrack


class ResearchLoopTests(unittest.TestCase):
    def test_agenda_is_priority_sorted_and_bounded(self):
        items = tuple(
            ResearchOpportunity(f"o{i}", ResearchTrack.ANOMALY, f"work {i}", float(i))
            for i in range(8)
        )
        agenda = AgendaBuilder(max_items=4).build(items)
        self.assertEqual(len(agenda.opportunities), 4)
        self.assertEqual(agenda.opportunities[0].priority, 7.0)


if __name__ == "__main__":
    unittest.main()
