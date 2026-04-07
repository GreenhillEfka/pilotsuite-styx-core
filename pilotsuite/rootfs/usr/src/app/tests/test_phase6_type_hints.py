"""Type hints validation tests for Phase 5 APIs.

Tests to ensure all API endpoint functions have proper type hints.
Phase 6 Code Quality Improvements.
"""

import ast
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest


def get_function_return_annotation(func) -> Optional[str]:
    """Get the return annotation of a function as a string."""
    sig = inspect.signature(func)
    if sig.return_annotation != inspect.Signature.empty:
        return str(sig.return_annotation)
    return None


def parse_api_file(filepath: Path) -> List[Dict[str, Any]]:
    """Parse a Python file and extract function information.
    
    Args:
        filepath: Path to the Python file.
    
    Returns:
        List of dicts with function name, has_return_annotation, and line number.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read(), filename=str(filepath))
    
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Skip private functions and decorators
            if node.name.startswith('_') and node.name != '__init__':
                continue
            
            has_return_annotation = node.returns is not None
            functions.append({
                'name': node.name,
                'has_return_annotation': has_return_annotation,
                'line': node.lineno,
                'args': [arg.arg for arg in node.args.args if arg.arg != 'self'],
            })
    
    return functions


class TestNotificationsApiTypeHints:
    """Test type hints in Notifications API (v1 version)."""

    @pytest.fixture
    def api_file(self) -> Path:
        """Path to notifications API file."""
        return Path(__file__).parent.parent / 'copilot_core' / 'api' / 'v1' / 'notifications.py'

    def test_all_functions_have_return_annotations(self, api_file: Path) -> None:
        """All endpoint functions should have return type annotations."""
        if not api_file.exists():
            pytest.skip("notifications v1 API file not found")
        functions = parse_api_file(api_file)

        # Filter for endpoint functions (not starting with underscore, not init)
        endpoint_functions = [
            f for f in functions
            if not f['name'].startswith('_') and f['name'] not in ('init_notifications_api',)
        ]

        missing_annotations = [
            f for f in endpoint_functions
            if not f['has_return_annotation']
        ]

        assert len(missing_annotations) == 0, (
            f"Functions without return annotations: {[f['name'] for f in missing_annotations]}"
        )

    def test_endpoint_functions_have_tuple_return(self, api_file: Path) -> None:
        """Endpoint functions should return Tuple[Dict[str, Any], int]."""
        if not api_file.exists():
            pytest.skip("notifications v1 API file not found")
        functions = parse_api_file(api_file)


class TestCollectiveIntelligenceApiTypeHints:
    """Test type hints in Collective Intelligence API."""
    
    @pytest.fixture
    def api_file(self) -> Path:
        """Path to collective intelligence API file."""
        return Path(__file__).parent.parent / 'copilot_core' / 'collective_intelligence' / 'api.py'
    
    def test_all_functions_have_return_annotations(self, api_file: Path) -> None:
        """All endpoint functions should have return type annotations."""
        functions = parse_api_file(api_file)
        
        # Filter for endpoint functions (not starting with underscore, not init)
        endpoint_functions = [
            f for f in functions 
            if not f['name'].startswith('_') and f['name'] != 'init_federated_api'
        ]
        
        missing_annotations = [
            f for f in endpoint_functions 
            if not f['has_return_annotation']
        ]
        
        assert len(missing_annotations) == 0, (
            f"Functions without return annotations: {[f['name'] for f in missing_annotations]}"
        )
    
    def test_endpoint_functions_have_tuple_return(self, api_file: Path) -> None:
        """Endpoint functions should return Tuple[Dict[str, Any], int]."""
        functions = parse_api_file(api_file)
        
        endpoint_names = [
            'get_status',
            'start_service',
            'stop_service',
            'register_node',
            'submit_update',
            'start_round',
            'execute_aggregation',
            'extract_knowledge',
            'transfer_knowledge',
            'get_round_history',
            'get_aggregated_models',
            'get_knowledge_base',
            'get_statistics',
            'save_state',
            'load_state',
        ]
        
        for func_info in functions:
            if func_info['name'] in endpoint_names:
                assert func_info['has_return_annotation'], (
                    f"{func_info['name']} missing return annotation"
                )


class TestSharingApiTypeHints:
    """Test type hints in Sharing API."""
    
    @pytest.fixture
    def api_file(self) -> Path:
        """Path to sharing API file."""
        return Path(__file__).parent.parent / 'copilot_core' / 'sharing' / 'api.py'
    
    def test_all_functions_have_return_annotations(self, api_file: Path) -> None:
        """All endpoint functions should have return type annotations."""
        functions = parse_api_file(api_file)
        
        # Filter for endpoint functions (not starting with underscore, not init)
        endpoint_functions = [
            f for f in functions 
            if not f['name'].startswith('_') and f['name'] != 'init_sharing_api'
        ]
        
        missing_annotations = [
            f for f in endpoint_functions 
            if not f['has_return_annotation']
        ]
        
        assert len(missing_annotations) == 0, (
            f"Functions without return annotations: {[f['name'] for f in missing_annotations]}"
        )


class TestPhase5ApiDocumentation:
    """Test that Phase 5 APIs have proper documentation."""
    
    def test_notifications_api_has_module_docstring(self) -> None:
        """Notifications API should have comprehensive module docstring."""
        api_file = Path(__file__).parent.parent / 'copilot_core' / 'api' / 'v1' / 'notifications.py'
        if not api_file.exists():
            pytest.skip("notifications v1 API file not found")

        with open(api_file, 'r', encoding='utf-8') as f:
            content = f.read()

        assert '"""' in content, "Missing module docstring"
        assert 'Notification' in content or 'notification' in content, (
            "Module docstring should describe purpose"
        )
    
    def test_collective_intelligence_api_has_module_docstring(self) -> None:
        """Collective Intelligence API should have comprehensive module docstring."""
        api_file = Path(__file__).parent.parent / 'copilot_core' / 'collective_intelligence' / 'api.py'
        
        with open(api_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '"""' in content, "Missing module docstring"
        assert 'Phase 5' in content or 'Federated' in content, (
            "Module docstring should describe purpose"
        )
    
    def test_sharing_api_has_module_docstring(self) -> None:
        """Sharing API should have comprehensive module docstring."""
        api_file = Path(__file__).parent.parent / 'copilot_core' / 'sharing' / 'api.py'
        
        with open(api_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '"""' in content, "Missing module docstring"
        assert 'Phase 5' in content or 'Sharing' in content, (
            "Module docstring should describe purpose"
        )
