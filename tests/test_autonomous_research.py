import unittest

from discovery.autonomy import AutonomousResearchPlanner, ResearchTrack
from discovery.ledger import EpistemicLedger
from discovery.models import Anomaly, AnomalyKind, KnowledgeCandidate, KnowledgeState


class AutonomousResearchTests(unittest.TestCase):
    def test_anomaly_creates_bounded_research(self):
        ledger = EpistemicLedger()
        planner = AutonomousResearchPlanner(ledger)
        anomaly = Anomaly("a1", AnomalyKind.EXPECTATION_MISMATCH, "result differs from prediction", "high", evidence_ids=("e1",))
        items = planner.generate([anomaly])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].track, ResearchTrack.ANOMALY)
        self.assertEqual(items[0].safety_class, "bounded")

    def test_unresolved_claim_creates_reproduction(self):
        ledger = EpistemicLedger()
        ledger.record(KnowledgeCandidate("test claim", KnowledgeState.OBSERVED, ("e1",), ("lab-a",), 0.6))
        items = AutonomousResearchPlanner(ledger).generate()
        self.assertEqual(items[0].track, ResearchTrack.REPRODUCTION)

    def test_verified_claim_is_not_auto_scheduled(self):
        ledger = EpistemicLedger()
        ledger.record(KnowledgeCandidate("verified claim", KnowledgeState.VERIFIED, ("e1",), ("a", "b"), 0.95))
        self.assertEqual(AutonomousResearchPlanner(ledger).generate(), ())


if __name__ == "__main__":
    unittest.main()
