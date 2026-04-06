"""Federated Learning Tests (P2-008 - Ollama Worker 5).

Validates the FederatedMath plugin and privacy-preserving aggregation.
"""

import unittest
from copilot_core.architecture.hexagonal_cqrs import FederatedMath

class FederatedLearningTest(unittest.TestCase):
    """Tests for P2-008 Federated Learning Math Library."""

    def test_federated_averaging(self):
        """Test computing the global average from local weights."""
        # Local model weights (e.g. from 3 different nodes)
        local_models = [
            {"brightness_pref": 0.8, "temp_pref": 21.0},
            {"brightness_pref": 0.6, "temp_pref": 22.0},
            {"brightness_pref": 0.7, "temp_pref": 21.5}
        ]
        
        global_model = FederatedMath.federated_average(local_models)
        
        self.assertAlmostEqual(global_model["brightness_pref"], 0.7)
        self.assertAlmostEqual(global_model["temp_pref"], 21.5)
        print("✅ Federated Averaging: Correct global weights computed.")

    def test_empty_models(self):
        """Ensure it handles empty lists gracefully."""
        result = FederatedMath.federated_average([])
        self.assertEqual(result, {})

if __name__ == "__main__":
    unittest.main()
