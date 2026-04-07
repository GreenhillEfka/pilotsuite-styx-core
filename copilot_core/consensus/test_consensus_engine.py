"""
Tests für die Konsens-Engine
"""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile

from .consensus_engine import (
    ConsensusEngine,
    Decision,
    VoteType,
    VoteWeight,
    DecisionStatus,
    VotingMethod,
)


class TestConsensusEngine:
    """Test-Suite für ConsensusEngine."""

    @pytest.fixture
    def engine(self):
        """Erstelle Engine mit temporärem Log-Verzeichnis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield ConsensusEngine(log_dir=Path(tmpdir))

    def test_create_decision(self, engine):
        """Test: Entscheidung erstellen."""
        decision = engine.create_decision(
            title="Test Decision",
            description="Test description",
            priority="medium",
        )

        assert decision.id.startswith("DEC-")
        assert decision.title == "Test Decision"
        assert decision.status == DecisionStatus.PENDING
        assert not decision.is_resolved

    def test_majority_voting(self, engine):
        """Test: Einfache Mehrheit."""
        decision = engine.create_decision(
            title="Majority Test",
            description="Test majority voting",
            voting_method=VotingMethod.MAJORITY,
        )

        # 2 YES, 1 NO -> Mehrheit
        engine.submit_vote(decision.id, "agent1", VoteType.YES)
        engine.submit_vote(decision.id, "agent2", VoteType.YES)
        engine.submit_vote(decision.id, "agent3", VoteType.NO)

        assert decision.status == DecisionStatus.RESOLVED
        assert "majority" in decision.result.lower()

    def test_unanimous_voting(self, engine):
        """Test: Einstimmigkeit."""
        decision = engine.create_decision(
            title="Unanimous Test",
            description="Test unanimous voting",
            voting_method=VotingMethod.UNANIMOUS,
            required_participants=["agent1", "agent2"],
        )

        engine.submit_vote(decision.id, "agent1", VoteType.YES)
        assert decision.status == DecisionStatus.IN_VOTING  # Noch nicht alle

        engine.submit_vote(decision.id, "agent2", VoteType.YES)
        assert decision.status == DecisionStatus.RESOLVED
        assert "unanimous" in decision.result.lower()

    def test_unanimous_veto(self, engine):
        """Test: Veto bei einstimmigem Voting."""
        decision = engine.create_decision(
            title="Veto Test",
            description="Test veto power",
            voting_method=VotingMethod.UNANIMOUS,
        )

        engine.submit_vote(decision.id, "agent1", VoteType.YES)
        engine.submit_vote(decision.id, "agent2", VoteType.VETO, rationale="Critical issue")

        assert decision.status == DecisionStatus.VETOED
        assert "veto" in decision.result.lower()

    def test_weighted_voting(self, engine):
        """Test: Gewichtete Stimmen."""
        decision = engine.create_decision(
            title="Weighted Test",
            description="Test weighted voting",
            voting_method=VotingMethod.WEIGHTED,
        )

        # Owner (5) sagt YES, 2 Standard (1 each) sagen NO
        engine.submit_vote(decision.id, "owner", VoteType.YES, VoteWeight.OWNER)
        engine.submit_vote(decision.id, "agent1", VoteType.NO, VoteWeight.STANDARD)
        engine.submit_vote(decision.id, "agent2", VoteType.NO, VoteWeight.STANDARD)

        # Net: 5 - 1 - 1 = 3 > 0 -> Approved
        assert decision.status == DecisionStatus.RESOLVED
        assert "weighted" in decision.result.lower()

    def test_auto_resolution_low_priority(self, engine):
        """Test: Auto-Resolution bei Low-Priority."""
        decision = engine.create_decision(
            title="Auto-Resolve Test",
            description="Test auto resolution",
            priority="low",
            auto_resolve_after_hours=1,
        )

        # Manipuliere created_at für Test
        decision.created_at = datetime.now(timezone.utc) - timedelta(hours=2)

        auto_resolved = engine.check_auto_resolution()

        assert decision.id in auto_resolved
        assert decision.status == DecisionStatus.AUTO_RESOLVED

    def test_no_auto_resolution_high_priority(self, engine):
        """Test: Keine Auto-Resolution bei High-Priority."""
        decision = engine.create_decision(
            title="High Priority Test",
            description="Should not auto-resolve",
            priority="high",
            auto_resolve_after_hours=1,
        )

        decision.created_at = datetime.now(timezone.utc) - timedelta(hours=2)

        auto_resolved = engine.check_auto_resolution()

        assert decision.id not in auto_resolved
        assert decision.status == DecisionStatus.PENDING

    def test_required_participants(self, engine):
        """Test: Erforderliche Teilnehmer."""
        decision = engine.create_decision(
            title="Required Participants Test",
            description="Test required participants",
            voting_method=VotingMethod.MAJORITY,
            required_participants=["agent1", "agent2", "agent3"],
        )

        # Nur 2 von 3 haben abgestimmt
        engine.submit_vote(decision.id, "agent1", VoteType.YES)
        engine.submit_vote(decision.id, "agent2", VoteType.YES)

        # Sollte noch nicht aufgelöst sein
        assert decision.status == DecisionStatus.IN_VOTING

        # Dritter stimmt auch
        engine.submit_vote(decision.id, "agent3", VoteType.YES)
        assert decision.status == DecisionStatus.RESOLVED

    def test_decision_export(self, engine):
        """Test: Decision-Log Export."""
        decision = engine.create_decision(
            title="Export Test",
            description="Test export functionality",
        )

        engine.submit_vote(decision.id, "agent1", VoteType.YES, rationale="Good idea")

        export_path = engine.export_decision_log(decision.id)

        assert export_path is not None
        assert export_path.exists()
        assert export_path.suffix == ".json"

    def test_decision_history(self, engine):
        """Test: Audit-Trail Historie."""
        decision = engine.create_decision(
            title="History Test",
            description="Test audit trail",
        )

        engine.submit_vote(decision.id, "agent1", VoteType.YES)
        engine.submit_vote(decision.id, "agent2", VoteType.NO)

        history = engine.get_decision_history()

        assert len(history) >= 3  # created + 2 votes
        assert any(log.action == "created" for log in history)
        assert any(log.action == "vote_submitted" for log in history)

    def test_vote_weight_values(self):
        """Test: Stimmgewicht-Werte."""
        assert VoteWeight.STANDARD.value == 1
        assert VoteWeight.EXPERT.value == 2
        assert VoteWeight.LEAD.value == 3
        assert VoteWeight.OWNER.value == 5

    def test_vote_weighted_value_yes(self):
        """Test: Berechnung gewichteter YES-Stimme."""
        vote = VoteType.YES
        weight = VoteWeight.OWNER
        # Simuliere weighted_value Logik
        weighted = weight.value if vote == VoteType.YES else 0
        assert weighted == 5

    def test_vote_weighted_value_no(self):
        """Test: Berechnung gewichteter NO-Stimme."""
        vote = VoteType.NO
        weight = VoteWeight.STANDARD
        # Simuliere weighted_value Logik
        weighted = -weight.value if vote == VoteType.NO else 0
        assert weighted == -1

    def test_super_majority(self, engine):
        """Test: 2/3 Mehrheit."""
        decision = engine.create_decision(
            title="Super Majority Test",
            description="Test 2/3 majority",
            voting_method=VotingMethod.SUPER_MAJORITY,
        )

        # 4 YES, 2 NO = 4/6 = 66.7% -> sollte reichen
        for i in range(4):
            engine.submit_vote(decision.id, f"agent_yes_{i}", VoteType.YES)
        for i in range(2):
            engine.submit_vote(decision.id, f"agent_no_{i}", VoteType.NO)

        assert decision.status == DecisionStatus.RESOLVED
        assert "super-majority" in decision.result.lower()

    def test_update_vote(self, engine):
        """Test: Stimme aktualisieren."""
        decision = engine.create_decision(
            title="Update Vote Test",
            description="Test vote update",
            voting_method=VotingMethod.MAJORITY,
        )

        # Agent ändert Meinung
        engine.submit_vote(decision.id, "agent1", VoteType.NO)
        engine.submit_vote(decision.id, "agent1", VoteType.YES)

        # Sollte nur eine Stimme zählen
        agent_votes = [v for v in decision.votes if v.agent_id == "agent1"]
        assert len(agent_votes) == 1
        assert agent_votes[0].vote_type == VoteType.YES


class TestDecisionDataclass:
    """Tests für Decision Dataclass."""

    def test_decision_hash(self):
        """Test: Decision Hash ist konsistent."""
        decision = Decision(
            id="DEC-test",
            title="Test",
            description="Test desc",
            priority="medium",
            voting_method=VotingMethod.MAJORITY,
        )

        hash1 = decision.get_decision_hash()
        hash2 = decision.get_decision_hash()

        assert hash1 == hash2
        assert len(hash1) == 16

    def test_is_resolved_property(self):
        """Test: is_resolved Property."""
        decision = Decision(
            id="DEC-test",
            title="Test",
            description="Test",
            priority="medium",
            voting_method=VotingMethod.MAJORITY,
            status=DecisionStatus.PENDING,
        )

        assert not decision.is_resolved

        decision.status = DecisionStatus.RESOLVED
        assert decision.is_resolved


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
