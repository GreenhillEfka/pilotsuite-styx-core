"""Tests for Styx Onboarding & Greeting Flow (v5.22.0)."""

import pytest

from copilot_core.onboarding import (
    OnboardingState,
    OnboardingStep,
    WelcomeMessage,
    complete_step,
    get_onboarding_state,
    get_welcome_message,
    init_onboarding,
    skip_step,
    _get_onboarding_steps,
    _onboarding_state,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Clear onboarding state between tests."""
    _onboarding_state.clear()
    yield
    _onboarding_state.clear()


@pytest.fixture
def config():
    return {
        "version": "5.22.0",
        "conversation": {
            "assistant_name": "Styx",
            "character": "copilot",
            "enabled": True,
        },
    }


@pytest.fixture
def config_butler():
    return {
        "version": "5.22.0",
        "conversation": {
            "assistant_name": "Alfred",
            "character": "butler",
        },
    }


# ── Test initialization ──────────────────────────────────────────────────


class TestInit:
    def test_init(self, config):
        init_onboarding(config=config)

    def test_init_none(self):
        init_onboarding(config=None)


# ── Test onboarding steps ────────────────────────────────────────────────


class TestOnboardingSteps:
    def test_step_count(self):
        steps = _get_onboarding_steps()
        assert len(steps) == 8

    def test_step_ids(self):
        steps = _get_onboarding_steps()
        ids = [s.step_id for s in steps]
        assert "welcome" in ids
        assert "llm_check" in ids
        assert "conversation_agent" in ids
        assert "regional_config" in ids
        assert "energy_setup" in ids
        assert "dashboard_check" in ids
        assert "test_conversation" in ids
        assert "complete" in ids

    def test_steps_have_both_languages(self):
        steps = _get_onboarding_steps()
        for s in steps:
            assert len(s.title_de) > 0
            assert len(s.title_en) > 0
            assert len(s.description_de) > 0
            assert len(s.description_en) > 0

    def test_steps_ordered(self):
        steps = _get_onboarding_steps()
        for i, s in enumerate(steps):
            assert s.order == i

    def test_steps_have_icons(self):
        steps = _get_onboarding_steps()
        for s in steps:
            assert s.icon.startswith("mdi:")

    def test_steps_have_actions(self):
        valid_actions = {"info", "configure", "verify", "done"}
        steps = _get_onboarding_steps()
        for s in steps:
            assert s.action in valid_actions


# ── Test onboarding state ────────────────────────────────────────────────


class TestOnboardingState:
    def test_initial_state(self, config):
        init_onboarding(config=config)
        state = get_onboarding_state("test")
        assert isinstance(state, OnboardingState)
        assert state.current_step == 0
        assert state.total_steps == 8
        assert state.is_complete is False

    def test_complete_first_step(self, config):
        init_onboarding(config=config)
        get_onboarding_state("test")
        state = complete_step("test", "welcome")
        assert state.current_step == 1

    def test_complete_multiple_steps(self, config):
        init_onboarding(config=config)
        get_onboarding_state("test")
        complete_step("test", "welcome")
        complete_step("test", "llm_check")
        state = complete_step("test", "conversation_agent")
        assert state.current_step == 3

    def test_skip_step(self, config):
        init_onboarding(config=config)
        get_onboarding_state("test")
        complete_step("test", "welcome")
        state = skip_step("test", "llm_check")
        assert state.current_step == 2

    def test_complete_all(self, config):
        init_onboarding(config=config)
        get_onboarding_state("test")
        steps = _get_onboarding_steps()
        for s in steps:
            complete_step("test", s.step_id)
        state = get_onboarding_state("test")
        assert state.is_complete is True
        assert len(state.completed_at) > 0

    def test_separate_sessions(self, config):
        init_onboarding(config=config)
        get_onboarding_state("session1")
        get_onboarding_state("session2")
        complete_step("session1", "welcome")
        state1 = get_onboarding_state("session1")
        state2 = get_onboarding_state("session2")
        assert state1.current_step == 1
        assert state2.current_step == 0


# ── Test welcome message ─────────────────────────────────────────────────


class TestWelcomeMessage:
    def test_german_welcome(self, config):
        init_onboarding(config=config)
        msg = get_welcome_message("de")
        assert isinstance(msg, WelcomeMessage)
        assert msg.language == "de"
        assert "Styx" in msg.greeting
        assert "Styx" in msg.message
        assert len(msg.quick_actions) >= 3

    def test_english_welcome(self, config):
        init_onboarding(config=config)
        msg = get_welcome_message("en")
        assert msg.language == "en"
        assert "Styx" in msg.greeting

    def test_custom_agent_name(self, config_butler):
        init_onboarding(config=config_butler)
        msg = get_welcome_message("de")
        assert "Alfred" in msg.greeting

    def test_personality(self, config):
        init_onboarding(config=config)
        msg = get_welcome_message("de")
        assert msg.personality == "Hilfsbereit und proaktiv"

    def test_butler_personality(self, config_butler):
        init_onboarding(config=config_butler)
        msg = get_welcome_message("de")
        assert msg.personality == "Stilvoll und diskret"

    def test_quick_actions_have_labels(self, config):
        init_onboarding(config=config)
        msg = get_welcome_message("de")
        for action in msg.quick_actions:
            assert "label" in action
            assert "action" in action
            assert "payload" in action

    def test_quick_actions_types(self, config):
        init_onboarding(config=config)
        msg = get_welcome_message("de")
        action_types = {a["action"] for a in msg.quick_actions}
        assert "chat" in action_types
        assert "navigate" in action_types
