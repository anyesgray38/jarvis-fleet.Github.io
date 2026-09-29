import unittest

from orchestrator import AgentSession, Orchestrator


class OrchestratorSessionTests(unittest.TestCase):
    def test_reconnect_retires_previous_session_for_same_hostname(self):
        orchestrator = Orchestrator('secret', 4444, '/tmp/missing.crt', '/tmp/missing.key', 8888)
        previous = AgentSession(None, ('127.0.0.1', 1), 1, {'hostname': 'worker', 'tags': ['old']})
        orchestrator.agents[previous.id] = previous
        orchestrator._next_id = 2

        current = AgentSession(None, ('127.0.0.1', 2), 0, {'hostname': 'worker', 'tags': ['new']})
        replaced = orchestrator._register_session(current)

        self.assertEqual(replaced, [previous])
        self.assertFalse(previous.alive)
        self.assertEqual(list(orchestrator.agents), [2])
        self.assertIs(orchestrator.agents[2], current)

    def test_different_hostnames_remain_registered(self):
        orchestrator = Orchestrator('secret', 4444, '/tmp/missing.crt', '/tmp/missing.key', 8888)
        first = AgentSession(None, ('127.0.0.1', 1), 0, {'hostname': 'worker-a'})
        second = AgentSession(None, ('127.0.0.1', 2), 0, {'hostname': 'worker-b'})

        orchestrator._register_session(first)
        orchestrator._register_session(second)

        self.assertEqual(len(orchestrator.agents), 2)
        self.assertTrue(all(session.alive for session in orchestrator.agents.values()))


if __name__ == '__main__':
    unittest.main()
