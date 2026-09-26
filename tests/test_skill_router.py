import json
import tempfile
import unittest
from pathlib import Path
from routing import SkillRouter

class SkillRouterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); root = Path(self.tmp.name)
        (root / "capabilities").mkdir(); (root / "skills" / "coding").mkdir(parents=True); (root / "skills" / "website-operation").mkdir()
        registry = {"capabilities": [
            {"id":"core.software_engineering","provider":"aegis","kind":"core","tags":["coding","repository","testing"],"verification":["tests"]},
            {"id":"core.website_generation","provider":"aegis","kind":"core","tags":["website","frontend","coding"],"verification":["browser_check"]},
            {"id":"security.web_assessment","provider":"aegis","kind":"security","tags":["security","assessment","web"],"verification":["scope_check"]}]}
        path=root/"capabilities"/"registry.json"; path.write_text(json.dumps(registry),encoding="utf-8"); self.router=SkillRouter(path,root/"skills")
    def tearDown(self): self.tmp.cleanup()
    def test_routes_by_registered_tags(self):
        result=self.router.route("build and code a website"); self.assertEqual(result[0].capability_id,"core.website_generation"); self.assertEqual(result[0].skill,"website-operation")
    def test_security_route_requires_authorization(self):
        security=next(x for x in self.router.route("security assessment of web target") if x.capability_id=="security.web_assessment"); self.assertTrue(security.requires_authorization); self.assertIn("scope_check",security.verification)
    def test_unknown_objective_fails_closed(self): self.assertEqual(self.router.route("zyxwv unrelated"),[])

if __name__=="__main__": unittest.main()
