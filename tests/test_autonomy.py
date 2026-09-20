import unittest
from jarvis.autonomy import *

class AutonomyTests(unittest.TestCase):
    def test_universal_id_and_queue_lifecycle(self):
        e=TaskEnvelope.create("build site","website.create",{"name":"x"})
        q=JobQueue(); j=q.enqueue(e); self.assertEqual(j.status,TaskStatus.QUEUED)
        q.transition(e.task_id,TaskStatus.AUTHORIZED); self.assertEqual(q.get(e.task_id).status,TaskStatus.AUTHORIZED)
    def test_duplicate_id_rejected(self):
        e=TaskEnvelope("fixed","x","x"); q=JobQueue(); q.enqueue(e)
        with self.assertRaises(ValueError): q.enqueue(e)
    def test_layered_memory(self):
        m=MemoryStore(); m.put("project","repo","jarvis",source="test"); self.assertEqual(m.get("project","repo"),"jarvis")
        with self.assertRaises(ValueError): m.put("bad","x",1)
    def test_capability_contract_requirements(self):
        c=CapabilityContract("build","build",requirements=("python",))
        self.assertEqual(len(CapabilityMatcher([c]).compatible("build",{"python"})),1)
        self.assertEqual(len(CapabilityMatcher([c]).compatible("build",set())),0)
    def test_failure_doctor_is_bounded(self):
        d=FailureDoctor()
        self.assertEqual(d.diagnose("timeout",1,3).action,"retry")
        self.assertEqual(d.diagnose("unknown",1,3).action,"escalate")
        self.assertEqual(d.diagnose("timeout",3,3).action,"escalate")
    def test_trust_and_dry_run(self):
        e=TaskEnvelope.create("deploy","website.deploy",trust_required=TrustLevel.EXECUTE_EXTERNAL)
        self.assertFalse(simulate(e,AutonomyController(TrustLevel.EXECUTE_LOCAL)).would_execute)
        self.assertTrue(simulate(e,AutonomyController(TrustLevel.EXECUTE_EXTERNAL)).would_execute)
    def test_rollback_and_activity(self):
        r=[]; rb=RollbackRegistry(); rb.register("t",lambda:r.append("rolled"))
        rb.rollback("t"); self.assertEqual(r,["rolled"])
        f=ActivityFeed(); f.emit("started","t",phase=1); self.assertEqual(f.list("t")[0]["phase"],1)

if __name__=="__main__": unittest.main()
