"""auto_implementation.py — Auto-Implementation für konsens-fähige Tasks.

Pattern-basierte Code-Generierung mit Test-First-Ansatz, Safety-Checks und Auto-Commit.
"""
import os
import re
import json
import subprocess
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(Enum):
    """Risikostufe für Code-Änderungen."""
    LOW = "low"           # Pure additions, no deletions
    MEDIUM = "medium"     # Modifications with tests
    HIGH = "high"         # Deletions, refactoring, no tests


@dataclass
class ImplementationPattern:
    """Pattern für Code-Generierung."""
    name: str
    description: str
    template: str
    test_template: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.LOW
    allowed_extensions: List[str] = field(default_factory=lambda: [".py"])


@dataclass
class SafetyCheck:
    """Safety-Check vor Commit."""
    name: str
    check_fn: callable
    critical: bool = True


@dataclass
class AutoCommitResult:
    """Ergebnis eines Auto-Commits."""
    success: bool
    commit_hash: Optional[str]
    files_changed: List[str]
    risk_level: RiskLevel
    safety_checks_passed: bool
    message: str


class AutoImplementation:
    """Auto-Implementation Engine für konsens-fähige Tasks."""

    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.patterns: Dict[str, ImplementationPattern] = {}
        self.safety_checks: List[SafetyCheck] = []
        self._register_default_patterns()
        self._register_default_safety_checks()

    def _register_default_patterns(self):
        """Registrierte Standard-Patterns."""
        # Sensor Pattern
        self.patterns["sensor"] = ImplementationPattern(
            name="sensor",
            description="Home Assistant Sensor Entity",
            template='''class {class_name}({base_class}):
    """{docstring}."""
    
    _attr_name = "{name}"
    _attr_unique_id = "{unique_id}"
    _attr_icon = "{icon}"
    
    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_device_info = {{
            "identifiers": {{(DOMAIN, config_entry.entry_id)}},
        }}
    
    @property
    def native_value(self):
        """Return the native value."""
        return self.coordinator.data.get("{data_key}", None)
    
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data is not None
''',
            test_template='''async def test_{snake_name}_sensor():
    """Test {class_name} sensor initialization and value."""
    coordinator = MockCoordinator()
    config_entry = MockConfigEntry()
    
    sensor = {class_name}(coordinator, config_entry)
    
    assert sensor.name == "{name}"
    assert sensor.unique_id == "{unique_id}"
    assert sensor.available == True
''',
            risk_level=RiskLevel.LOW
        )

        # Service Pattern
        self.patterns["service"] = ImplementationPattern(
            name="service",
            description="Home Assistant Service Registration",
            template='''async def handle_{service_name}(call):
    """Handle {service_name} service call."""
    data = call.data
    entry_id = data.get("entry_id")
    
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry:
        raise HomeAssistantError(f"Entry {{entry_id}} not found")
    
    coordinator = hass.data[DOMAIN][entry_id][DATA_COORDINATOR]
    await coordinator.{action_method}(data)
    
    return {{"success": True}}
''',
            test_template='''async def test_handle_{service_name}():
    """Test {service_name} service handler."""
    call = MockServiceCall(entry_id="test123", data={{"key": "value"}})
    
    result = await handle_{service_name}(call)
    
    assert result["success"] == True
''',
            risk_level=RiskLevel.MEDIUM
        )

        # Button Pattern
        self.patterns["button"] = ImplementationPattern(
            name="button",
            description="Home Assistant Button Entity",
            template='''class {class_name}({base_class}):
    """{docstring}."""
    
    _attr_name = "{name}"
    _attr_unique_id = "{unique_id}"
    _attr_icon = "{icon}"
    
    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator)
        self._config_entry = config_entry
    
    async def async_press(self) -> None:
        """Handle button press."""
        await self.coordinator.{action_method}()
''',
            test_template='''async def test_{snake_name}_button_press():
    """Test button press action."""
    coordinator = MockCoordinator()
    config_entry = MockConfigEntry()
    
    button = {class_name}(coordinator, config_entry)
    await button.async_press()
    
    coordinator.{action_method}.assert_called_once()
''',
            risk_level=RiskLevel.LOW
        )

        # Config Schema Pattern
        self.patterns["config_schema"] = ImplementationPattern(
            name="config_schema",
            description="Voluptuous Config Schema",
            template='''CONFIG_SCHEMA = vol.Schema({{
    DOMAIN: vol.Schema({{
        vol.Optional("{key}", default={default}): vol.All(
            {validator},
            {range_check}
        ),
    }})
}}, extra=vol.ALLOW_EXTRA)
''',
            risk_level=RiskLevel.LOW
        )

    def _register_default_safety_checks(self):
        """Registrierte Standard-Safety-Checks."""
        self.safety_checks = [
            SafetyCheck(
                name="syntax_check",
                check_fn=self._check_python_syntax,
                critical=True
            ),
            SafetyCheck(
                name="test_coverage",
                check_fn=self._check_tests_exist,
                critical=True
            ),
            SafetyCheck(
                name="no_deletions",
                check_fn=self._check_no_deletions,
                critical=False
            ),
            SafetyCheck(
                name="import_check",
                check_fn=self._check_imports,
                critical=True
            ),
        ]

    def generate_code(self, pattern_name: str, context: Dict[str, Any]) -> str:
        """Generiert Code basierend auf Pattern und Kontext."""
        if pattern_name not in self.patterns:
            raise ValueError(f"Unknown pattern: {pattern_name}")
        
        pattern = self.patterns[pattern_name]
        
        # Template-Variablen vorbereiten
        template_vars = {
            "class_name": context.get("class_name", "Entity"),
            "name": context.get("name", "Entity"),
            "snake_name": self._to_snake_case(context.get("class_name", "Entity")),
            "unique_id": context.get("unique_id", "unique_id"),
            "icon": context.get("icon", "mdi:sensor"),
            "docstring": context.get("docstring", "Auto-generated entity"),
            "base_class": context.get("base_class", "CoordinatorEntity"),
            "data_key": context.get("data_key", "value"),
            "service_name": context.get("service_name", "service"),
            "action_method": context.get("action_method", "async_update"),
            "key": context.get("key", "config_key"),
            "default": context.get("default", "None"),
            "validator": context.get("validator", "str"),
            "range_check": context.get("range_check", "lambda x: x"),
        }
        
        try:
            code = pattern.template.format(**template_vars)
            return code
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")

    def generate_test(self, pattern_name: str, context: Dict[str, Any]) -> Optional[str]:
        """Generiert Test-Code basierend auf Pattern."""
        if pattern_name not in self.patterns:
            return None
        
        pattern = self.patterns[pattern_name]
        if not pattern.test_template:
            return None
        
        template_vars = {
            "class_name": context.get("class_name", "Entity"),
            "name": context.get("name", "Entity"),
            "snake_name": self._to_snake_case(context.get("class_name", "Entity")),
            "unique_id": context.get("unique_id", "unique_id"),
            "action_method": context.get("action_method", "async_update"),
        }
        
        try:
            test_code = pattern.test_template.format(**template_vars)
            return test_code
        except KeyError:
            return None

    def run_safety_checks(self, file_path: str, new_content: str) -> Tuple[bool, List[str]]:
        """Führt Safety-Checks durch. Returns (passed, errors)."""
        errors = []
        passed = True
        
        for check in self.safety_checks:
            try:
                result = check.check_fn(file_path, new_content)
                if not result:
                    error_msg = f"Safety check failed: {check.name}"
                    if check.critical:
                        passed = False
                    errors.append(error_msg)
            except Exception as e:
                error_msg = f"Safety check error ({check.name}): {str(e)}"
                if check.critical:
                    passed = False
                errors.append(error_msg)
        
        return passed, errors

    def _check_python_syntax(self, file_path: str, content: str) -> bool:
        """Check: Python syntax validity."""
        try:
            compile(content, file_path, 'exec')
            return True
        except SyntaxError:
            return False

    def _check_tests_exist(self, file_path: str, content: str) -> bool:
        """Check: Tests exist for new code."""
        # Extrahiere Klassennamen aus dem Code
        class_matches = re.findall(r'class\s+(\w+)\s*\(', content)
        func_matches = re.findall(r'async? def\s+(\w+)\s*\(', content)
        
        if not class_matches and not func_matches:
            return True  # Kein relevanter Code
        
        # Prüfe ob Test-Datei existiert
        test_path = self._find_test_file(file_path)
        if not test_path or not test_path.exists():
            return False
        
        # Prüfe ob Tests für die neuen Klassen/Funktionen existieren
        test_content = test_path.read_text()
        for class_name in class_matches:
            snake_name = self._to_snake_case(class_name)
            if f"test_{snake_name}" not in test_content:
                return False
        
        return True

    def _check_no_deletions(self, file_path: str, content: str) -> bool:
        """Check: Keine Löschungen (nur für Low-Risk)."""
        if not Path(file_path).exists():
            return True  # Neue Datei
        
        existing = Path(file_path).read_text()
        existing_lines = set(existing.splitlines())
        new_lines = set(content.splitlines())
        
        # Wenn mehr als 50% der existing lines gelöscht werden -> High Risk
        deleted = existing_lines - new_lines
        if len(deleted) > len(existing_lines) * 0.5:
            return False
        
        return True

    def _check_imports(self, file_path: str, content: str) -> bool:
        """Check: Alle imports sind verfügbar."""
        import_matches = re.findall(r'^(?:import|from)\s+([\w.]+)', content, re.MULTILINE)
        
        # Standard imports immer OK
        standard_imports = {'os', 'sys', 're', 'json', 'pathlib', 'typing', 'dataclasses', 'datetime'}
        
        for imp in import_matches:
            base_module = imp.split('.')[0]
            if base_module not in standard_imports:
                # Prüfe ob Modul existiert (vereinfacht)
                try:
                    __import__(base_module)
                except ImportError:
                    # HA modules sind im Test-Stub OK
                    if not base_module.startswith('homeassistant'):
                        return False
        
        return True

    def auto_commit(
        self,
        file_path: str,
        content: str,
        test_content: Optional[str] = None,
        commit_message: str = None,
        risk_level: RiskLevel = None
    ) -> AutoCommitResult:
        """Führt Auto-Commit für Low-Risk-Changes durch."""
        file_path = Path(file_path)
        
        # Risk-Level bestimmen falls nicht angegeben
        if risk_level is None:
            risk_level = self._assess_risk(file_path, content)
        
        # Safety-Checks durchführen
        safety_passed, safety_errors = self.run_safety_checks(str(file_path), content)
        
        if not safety_passed and risk_level == RiskLevel.HIGH:
            return AutoCommitResult(
                success=False,
                commit_hash=None,
                files_changed=[],
                risk_level=risk_level,
                safety_checks_passed=False,
                message=f"Safety checks failed: {', '.join(safety_errors)}"
            )
        
        # Datei schreiben
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        
        files_changed = [str(file_path)]
        
        # Test-Datei schreiben falls vorhanden
        if test_content:
            test_path = self._find_test_file(file_path, create=True)
            if test_path:
                test_path.write_text(test_content)
                files_changed.append(str(test_path))
        
        # Git-Status prüfen
        if not self._is_git_repo():
            return AutoCommitResult(
                success=True,
                commit_hash=None,
                files_changed=files_changed,
                risk_level=risk_level,
                safety_checks_passed=safety_passed,
                message="Files written (not a git repo)"
            )
        
        # Nur auto-commit für LOW-Risk
        if risk_level != RiskLevel.LOW:
            return AutoCommitResult(
                success=True,
                commit_hash=None,
                files_changed=files_changed,
                risk_level=risk_level,
                safety_checks_passed=safety_passed,
                message="Files written (manual commit required for medium/high risk)"
            )
        
        # Git add
        self._git_add(files_changed)
        
        # Git commit
        if not commit_message:
            commit_message = f"auto: {file_path.name}"
        
        commit_hash = self._git_commit(commit_message)
        
        return AutoCommitResult(
            success=True,
            commit_hash=commit_hash,
            files_changed=files_changed,
            risk_level=risk_level,
            safety_checks_passed=safety_passed,
            message=f"Auto-committed to {commit_hash or 'working tree'}"
        )

    def _assess_risk(self, file_path: Path, content: str) -> RiskLevel:
        """Bewertet Risiko der Änderung."""
        if not file_path.exists():
            return RiskLevel.LOW  # Neue Datei ist低风险
        
        existing = file_path.read_text()
        existing_lines = existing.splitlines()
        new_lines = content.splitlines()
        
        # Deletions erkennen
        deleted = len(existing_lines) - len(new_lines)
        if deleted > len(existing_lines) * 0.3:
            return RiskLevel.HIGH
        
        # Nur Additions
        if len(new_lines) > len(existing_lines):
            return RiskLevel.LOW
        
        return RiskLevel.MEDIUM

    def _is_git_repo(self) -> bool:
        """Prüft ob Workspace ein Git-Repo ist."""
        git_dir = self.workspace_root / ".git"
        return git_dir.exists() and git_dir.is_dir()

    def _git_add(self, files: List[str]):
        """Git add für Dateien."""
        try:
            subprocess.run(
                ["git", "add"] + files,
                cwd=self.workspace_root,
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Git add failed: {e}")

    def _git_commit(self, message: str) -> Optional[str]:
        """Git commit mit Message. Returns commit hash or None."""
        try:
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.workspace_root,
                check=True,
                capture_output=True,
                text=True
            )
            
            # Hash aus Output extrahieren
            match = re.search(r'\[([^\]]+)\s+([a-f0-9]+)\]', result.stdout)
            if match:
                return match.group(2)
            return None
            
        except subprocess.CalledProcessError as e:
            print(f"Git commit failed: {e}")
            return None

    def _find_test_file(self, source_path: Path, create: bool = False) -> Optional[Path]:
        """Findet oder erstellt Test-Datei für Source-Datei."""
        # Konvertiere Pfad zu Test-Pfad
        rel_path = source_path.relative_to(self.workspace_root)
        test_path = self.workspace_root / "tests" / rel_path
        
        if test_path.exists():
            return test_path
        
        # Alternative: test_<name>.py im tests/ Verzeichnis
        if source_path.suffix == ".py":
            alt_test_path = self.workspace_root / "tests" / f"test_{source_path.name}"
            if alt_test_path.exists():
                return alt_test_path
            
            if create:
                alt_test_path.parent.mkdir(parents=True, exist_ok=True)
                return alt_test_path
        
        return None

    def _to_snake_case(self, name: str) -> str:
        """Konvertiert CamelCase zu snake_case."""
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def implement_task(
        self,
        task_description: str,
        pattern_name: str,
        target_path: str,
        context: Dict[str, Any]
    ) -> AutoCommitResult:
        """Vollständige Implementation eines Tasks."""
        # Code generieren
        code = self.generate_code(pattern_name, context)
        test_code = self.generate_test(pattern_name, context)
        
        # Auto-Commit durchführen
        result = self.auto_commit(
            file_path=target_path,
            content=code,
            test_content=test_code,
            commit_message=f"auto: {task_description}",
            risk_level=self.patterns[pattern_name].risk_level
        )
        
        return result


# Convenience-Funktionen für direkte Nutzung
def quick_implement_sensor(
    class_name: str,
    name: str,
    data_key: str,
    workspace_root: str = None
) -> AutoCommitResult:
    """Quick-Implementation für Sensor."""
    impl = AutoImplementation(workspace_root)
    
    context = {
        "class_name": class_name,
        "name": name,
        "data_key": data_key,
        "unique_id": f"sensor_{class_name.lower()}",
        "icon": "mdi:sensor",
        "docstring": f"Sensor for {name}",
    }
    
    # Pfad absolut machen
    target_path = Path(workspace_root) if workspace_root else Path.cwd()
    target_path = target_path / "custom_components" / "copilot_ha" / f"{class_name.lower()}.py"
    
    return impl.implement_task(
        task_description=f"Add {class_name} sensor",
        pattern_name="sensor",
        target_path=str(target_path),
        context=context
    )


if __name__ == "__main__":
    # Beispiel-Nutzung
    impl = AutoImplementation("/config/clawd")
    
    # Sensor implementieren
    result = quick_implement_sensor(
        class_name="SystemHealth",
        name="System Health",
        data_key="system_health_score"
    )
    
    print(f"Success: {result.success}")
    print(f"Commit: {result.commit_hash}")
    print(f"Files: {result.files_changed}")
    print(f"Risk: {result.risk_level.value}")
    print(f"Message: {result.message}")
