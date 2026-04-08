"""
Tests for Dialog State Machine (Slice 74)
"""

import pytest
import os
import json
import time
import tempfile
import shutil

from copilot_core.voice.dialog_state import (
    DialogStateMachine,
    DialogState,
    get_dialog_machine,
)


class TestDialogStateMachine:
    @pytest.fixture
    def temp_data_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def machine(self, temp_data_dir):
        return DialogStateMachine(data_dir=temp_data_dir)
    
    def test_initial_state_is_idle(self, machine):
        state = machine.get_state()
        assert state.state == 'IDLE'
        assert state.active_intent is None
    
    def test_activate_intent(self, machine):
        state = machine.activate_intent(
            intent='climate.set_temperature',
            slots={'room': 'kitchen', 'target_temp': 22},
        )
        assert state.state == 'ACTIVE'
        assert state.active_intent == 'climate.set_temperature'
    
    def test_context_stack_on_interruption(self, machine):
        machine.activate_intent('light.turn_on', {'room': 'kitchen'})
        machine.activate_intent('weather.get', {})
        
        state = machine.get_state()
        assert state.state == 'INTERRUPTED'
        assert len(state.context_stack) == 1
    
    def test_timeout_decay(self, machine):
        machine.activate_intent('light.turn_on', {})
        machine.state.last_activity_ts = time.time() - 31
        
        assert machine.check_timeout() == True
        
        state = machine.decay()
        assert state.state == 'IDLE'
    
    def test_persistence(self, temp_data_dir):
        machine1 = DialogStateMachine(data_dir=temp_data_dir)
        machine1.activate_intent('climate.set_temperature', {'target_temp': 22})
        
        machine2 = DialogStateMachine(data_dir=temp_data_dir)
        state = machine2.get_state()
        
        assert state.active_intent == 'climate.set_temperature'
    
    def test_german_confirmation(self, machine):
        machine.activate_intent('climate.set_temperature', {'room': 'kitchen'})
        machine.set_confirming()
        
        question = machine.generate_confirmation_question()
        assert question is not None
        assert 'Temperatur' in question or 'kitchen' in question


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
