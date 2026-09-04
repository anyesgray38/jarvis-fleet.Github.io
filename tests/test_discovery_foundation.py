import unittest

from discovery.autonomy import ResearchOpportunity, ResearchTrack
from discovery.experiment_factory import ExperimentFactory, ExperimentTemplate
from discovery.knowledge_graph import GraphNode, KnowledgeGraph


class DiscoveryFoundationTests(unittest.TestCase):
    def test_graph_relationships(self):
        graph = KnowledgeGraph()
        graph.add_node(GraphNode("c1", "claim", "claim", {}))
        graph.add_node(GraphNode("e1", "evidence", "evidence", {}))
        graph.relate("c1", "supported_by", "e1")
        self.assertEqual(graph.neighbors("c1")[0].node_id, "e1")

    def test_factory_requires_falsification(self):
        opportunity = ResearchOpportunity("o1", ResearchTrack.ANOMALY, "investigate", 0.8)
        template = ExperimentTemplate(("baseline",), ("accuracy",), ("accuracy decreases",))
        experiment = ExperimentFactory().build(opportunity, hypothesis_id="h1", procedure=("run baseline",), template=template)
        self.assertEqual(experiment.hypothesis_id, "h1")
        self.assertIn("provenance", experiment.required_evidence)


if __name__ == "__main__":
    unittest.main()
