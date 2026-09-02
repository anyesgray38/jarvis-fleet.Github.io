import unittest
import fleet

class FleetExportsTests(unittest.TestCase):
    def test_core_primitives_are_importable(self):
        self.assertTrue(hasattr(fleet, "FleetNode"))
        self.assertTrue(hasattr(fleet, "FleetScheduler"))
        self.assertTrue(hasattr(fleet, "NetworkPolicy"))
        self.assertTrue(hasattr(fleet, "Workload"))

if __name__ == "__main__":
    unittest.main()
