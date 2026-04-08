# Tag System v0.2 — PilotSuite Core Add-on
"""
Tag System v0.2 Implementation

Based on Decision Matrix Recommendations (2026-02-14):
- HA-Labels materialisieren: nur ausgewählte Facetten (role.*, state.*)
- Subjects: alle HA-Label-Typen (entity, device, area, automation, scene, script, helper)
- Subject IDs: Mix aus Registry-ID + Fallback
- Namespace: user.* NICHT als interner Namespace (nur HA-Labels importieren)
- Lokalisierung: nur display.de + en
- Learned Tags → HA-Labels: NIE automatisch (explizite Bestätigung nötig)
- Farben/Icons: HA als UI-Quelle
- Konflikte: existierende HA-Labels ohne aicp.* ignorieren
- Habitus-Zonen: eigene interne Objekte mit Policies
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class SubjectType(str, Enum):
    """Alle unterstützten HA-Label-Typen (Decision Matrix P1)."""
    ENTITY = "entity"
    DEVICE = "device"
    AREA = "area"
    AUTOMATION = "automation"
    SCENE = "scene"
    SCRIPT = "script"
    HELPER = "helper"


class TagFacet(str, Enum):
    """Facetten für Tag-Klassifizierung."""
    PLACE = "place"       # Ort/Zone
    KIND = "kind"         # Art: light, sensor, switch
    DOMAIN = "domain"     # HA-Domain
    CAP = "cap"           # Capabilities
    ROLE = "role"         # Behavior (safety_critical, primary_light, etc.)
    STATE = "state"       # Zustände: candidate, broken, needs_repair
    INV = "inv"           # Inventory/Lifecycle


class TagNamespace(str, Enum):
    """Tag-Namespaces (Policy: user.* NICHT als intern, Decision Matrix P1)."""
    AICP = "aicp"         # PilotSuite verwaltet (empfohlen)
    SYS = "sys"           # Reserviert (intern, nie als HA-Label)
    HA = "ha"             # Mapping für vorhandene HA-Labels


@dataclass
class TagMetadata:
    """Metadaten für einen Tag (Lokalisierung: de/en only, Decision Matrix P1)."""
    display_de: Optional[str] = None
    display_en: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None  # HA als UI-Quelle (Decision Matrix P1)
    description: Optional[str] = None
    created_at: float = field(default_factory=lambda: __import__("time").time())
    updated_at: float = field(default_factory=lambda: __import__("time").time())


@dataclass
class Tag:
    """
    Tag-Objekt (intern, Core Add-on).
    
    Decision Matrix P1:
    - Learned Tags → HA-Labels: NIE automatisch
    - Nur ausgewählte Facetten materialisieren (role.*, state.*)
    """
    id: str  # Format: <namespace>.<facet>.<key>
    facet: TagFacet
    metadata: TagMetadata = field(default_factory=TagMetadata)
    is_learned: bool = False  # True = wurde vorgeschlagen, braucht Bestätigung
    is_materialized: bool = False  # True = als HA-Label materialisiert
    provenance: str = "system"  # "system", "user", "learned"
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
    
    @property
    def namespace(self) -> str:
        """Extrahiert Namespace aus ID."""
        return self.id.split(".")[0] if "." in self.id else ""
    
    def should_materialize(self) -> bool:
        """
        Entscheidung: Soll dieser Tag als HA-Label materialisiert werden?
        
        Decision Matrix P1:
        - Nur ausgewählte Facetten (role.*, state.*)
        - Learned Tags NIE automatisch
        """
        if self.is_learned:
            return False
        if self.facet in (TagFacet.ROLE, TagFacet.STATE):
            return True
        return False


@dataclass  
class Subject:
    """
    Subject — ein HA-Objekt das getaggt werden kann.
    
    Decision Matrix P1:
    - Alle HA-Label-Typen unterstützen (entity, device, area, automation, scene, script, helper)
    - IDs: Mix aus Registry-ID + Fallback
    """
    ha_id: str  # entity_id, device_id, area_id, etc. (Fallback)
    ha_type: SubjectType
    unique_id: Optional[str] = None  # Registry-ID (wenn verfügbar)
    device_id: Optional[str] = None   # Für entities/devices
    area_id: Optional[str] = None     # Für location
    name: Optional[str] = None
    domain: Optional[str] = None      # light, switch, sensor, etc.
    
    @property
    def canonical_id(self) -> str:
        """
        Liefert die kanonische Subject-ID.
        
        Decision Matrix P1: Mix aus Registry-ID + Fallback
        """
        # Priority: unique_id > device_id > ha_id
        if self.unique_id:
            return self.unique_id
        if self.device_id:
            return self.device_id
        return self.ha_id


@dataclass
class HabitusZone:
    """
    Habitus-Zone (eigene interne Objekte mit Policies).
    
    Decision Matrix P1: Als eigene Objekte modellieren, nicht als Tags.
    """
    id: str
    name: str
    description: Optional[str] = None
    policy_ids: list[str] = field(default_factory=list)
    member_subject_ids: list[str] = field(default_factory=list)
    is_active: bool = True


@dataclass
class TagAssignment:
    """Verknüpfung Tag → Subject."""
    tag_id: str
    subject_canonical_id: str
    assigned_at: float = field(default_factory=lambda: __import__("time").time())
    assigned_by: str = "system"  # "system", "learner", "user"


class TagRegistry:
    """
    Interne Tag-Registry (Brain Graph).
    
    Decision Matrix P1:
    - sys.* nie als HA-Label materialisieren
    - existierende HA-Labels ohne aicp.* ignorieren
    """
    
    def __init__(self):
        self._tags: dict[str, Tag] = {}
        self._assignments: list[TagAssignment] = []
        self._subjects: dict[str, Subject] = {}
        self._zones: dict[str, HabitusZone] = {}
    
    # === Tag CRUD ===
    
    def create_tag(
        self,
        tag_id: str,
        facet: TagFacet,
        display_de: Optional[str] = None,
        display_en: Optional[str] = None,
        provenance: str = "system",
    ) -> Tag:
        """Erstellt einen neuen Tag."""
        metadata = TagMetadata(display_de=display_de, display_en=display_en)
        tag = Tag(id=tag_id, facet=facet, metadata=metadata, provenance=provenance)
        self._tags[tag_id] = tag
        return tag
    
    def get_tag(self, tag_id: str) -> Optional[Tag]:
        """Liefert einen Tag nach ID."""
        return self._tags.get(tag_id)
    
    def list_tags(self, facet: Optional[TagFacet] = None) -> list[Tag]:
        """Listet Tags auf (optional gefiltert nach Facette)."""
        tags = list(self._tags.values())
        if facet:
            tags = [t for t in tags if t.facet == facet]
        return tags
    
    def list_tags_to_materialize(self) -> list[Tag]:
        """
        Listet Tags die als HA-Label materialisiert werden sollten.
        
        Decision Matrix P1: Nur role.* und state.*, NIE learned Tags
        """
        return [t for t in self._tags.values() if t.should_materialize()]
    
    def suggest_learned_tag(
        self,
        facet: TagFacet,
        key: str,
        namespace: str = "sys",
        display_de: Optional[str] = None,
    ) -> Tag:
        """
        Erstellt einen "Learned Tag" — braucht explizite Bestätigung.
        
        Decision Matrix P1: Learned Tags → HA-Labels NIE automatisch
        """
        tag_id = f"{namespace}.{facet.value}.{key}"
        tag = self.create_tag(
            tag_id=tag_id,
            facet=facet,
            display_de=display_de,
            provenance="learned",
        )
        tag.is_learned = True
        return tag
    
    def confirm_learned_tag(self, tag_id: str) -> Optional[Tag]:
        """Bestätigt einen Learned Tag (macht ihn正式)."""
        tag = self._tags.get(tag_id)
        if tag and tag.is_learned:
            tag.is_learned = False
            tag.provenance = "user"
            tag.metadata.updated_at = __import__("time").time()
            return tag
        return None
    
    # === Subject CRUD ===
    
    def register_subject(
        self,
        ha_id: str,
        ha_type: SubjectType,
        unique_id: Optional[str] = None,
        device_id: Optional[str] = None,
        area_id: Optional[str] = None,
        name: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> Subject:
        """Registriert ein Subject (Entity, Device, Area, etc.)."""
        subject = Subject(
            ha_id=ha_id,
            ha_type=ha_type,
            unique_id=unique_id,
            device_id=device_id,
            area_id=area_id,
            name=name,
            domain=domain,
        )
        self._subjects[subject.canonical_id] = subject
        return subject
    
    def get_subject(self, canonical_id: str) -> Optional[Subject]:
        """Liefert ein Subject nach kanonischer ID."""
        return self._subjects.get(canonical_id)
    
    # === Tag Assignment ===
    
    def assign_tag(
        self,
        tag_id: str,
        subject_canonical_id: str,
        assigned_by: str = "system",
    ) -> Optional[TagAssignment]:
        """Weist einem Subject einen Tag zu."""
        if tag_id not in self._tags:
            return None
        if subject_canonical_id not in self._subjects:
            return None
        
        assignment = TagAssignment(
            tag_id=tag_id,
            subject_canonical_id=subject_canonical_id,
            assigned_by=assigned_by,
        )
        self._assignments.append(assignment)
        return assignment
    
    def get_subject_tags(self, subject_canonical_id: str) -> list[Tag]:
        """Liefert alle Tags für ein Subject."""
        tag_ids = [
            a.tag_id for a in self._assignments 
            if a.subject_canonical_id == subject_canonical_id
        ]
        return [self._tags[tid] for tid in tag_ids if tid in self._tags]
    
    def get_tag_subjects(self, tag_id: str) -> list[Subject]:
        """Liefert alle Subjects für einen Tag."""
        subject_ids = [
            a.subject_canonical_id for a in self._assignments 
            if a.tag_id == tag_id
        ]
        return [self._subjects[sid] for sid in subject_ids if sid in self._subjects]
    
    # === Habitus Zones ===
    
    def create_zone(
        self,
        zone_id: str,
        name: str,
        policy_ids: Optional[list[str]] = None,
    ) -> HabitusZone:
        """Erstellt eine Habitus-Zone."""
        zone = HabitusZone(
            id=zone_id,
            name=name,
            policy_ids=policy_ids or [],
        )
        self._zones[zone_id] = zone
        return zone
    
    def add_to_zone(self, zone_id: str, subject_canonical_id: str) -> bool:
        """Fügt ein Subject zu einer Zone hinzu."""
        zone = self._zones.get(zone_id)
        if zone and subject_canonical_id in self._subjects:
            zone.member_subject_ids.append(subject_canonical_id)
            return True
        return False
    
    # === Export für HA Labels ===
    
    def export_ha_labels(self) -> list[dict]:
        """
        Exportiert Tags als HA-Label-Format.
        
        Decision Matrix P1:
        - Nur ausgewählte Facetten (role.*, state.*)
        - sys.* NICHT exportieren
        - HA-Labels ohne aicp.* ignorieren (nicht überschreiben)
        """
        labels = []
        for tag in self._tags.values():
            if tag.namespace == "sys":
                continue  # sys.* nie als HA-Label
            if not tag.should_materialize():
                continue  # Nur role.* und state.*
            
            labels.append({
                "name": tag.id,
                "icon": tag.metadata.icon,
                "color": tag.metadata.color,  # HA als UI-Quelle
                "description": tag.metadata.description,
            })
        return labels


# === Service Interface ===

def create_tag_service(registry: TagRegistry):
    """Erstellt das Tag Service Interface."""
    
    def create_tag(
        tag_id: str,
        facet: str,
        display_de: Optional[str] = None,
        display_en: Optional[str] = None,
    ) -> dict:
        """Erstellt einen neuen Tag."""
        tag = registry.create_tag(
            tag_id=tag_id,
            facet=TagFacet(facet),
            display_de=display_de,
            display_en=display_en,
        )
        return {"status": "created", "tag_id": tag.id}
    
    def suggest_tag(
        facet: str,
        key: str,
        namespace: str = "sys",
        display_de: Optional[str] = None,
    ) -> dict:
        """Schlägt einen Learned Tag vor (braucht Bestätigung)."""
        tag = registry.suggest_learned_tag(
            facet=TagFacet(facet),
            key=key,
            namespace=namespace,
            display_de=display_de,
        )
        return {
            "status": "suggested",
            "tag_id": tag.id,
            "is_learned": tag.is_learned,
            "message": "Learned tag — requires explicit confirmation before materialization",
        }
    
    def confirm_tag(tag_id: str) -> dict:
        """Bestätigt einen Learned Tag."""
        tag = registry.confirm_learned_tag(tag_id)
        if tag:
            return {"status": "confirmed", "tag_id": tag.id}
        return {"status": "error", "message": "Tag not found or not learned"}
    
    def list_tags(facet: Optional[str] = None) -> dict:
        """Listet Tags auf."""
        facet_enum = TagFacet(facet) if facet else None
        tags = registry.list_tags(facet=facet_enum)
        return {
            "tags": [
                {
                    "id": t.id,
                    "facet": t.facet.value,
                    "display_de": t.metadata.display_de,
                    "display_en": t.metadata.display_en,
                    "is_learned": t.is_learned,
                }
                for t in tags
            ]
        }
    
    def register_subject(
        ha_id: str,
        ha_type: str,
        name: Optional[str] = None,
        domain: Optional[str] = None,
        **kwargs,
    ) -> dict:
        """Registriert ein Subject."""
        subject = registry.register_subject(
            ha_id=ha_id,
            ha_type=SubjectType(ha_type),
            name=name,
            domain=domain,
            unique_id=kwargs.get("unique_id"),
            device_id=kwargs.get("device_id"),
            area_id=kwargs.get("area_id"),
        )
        return {"status": "registered", "subject_id": subject.canonical_id}
    
    def assign_tag(tag_id: str, subject_id: str) -> dict:
        """Weist einem Subject einen Tag zu."""
        result = registry.assign_tag(tag_id, subject_id)
        if result:
            return {"status": "assigned", "tag_id": tag_id, "subject_id": subject_id}
        return {"status": "error", "message": "Tag or subject not found"}
    
    def export_labels() -> dict:
        """Exportiert Tags für HA-Label-Sync."""
        return {"labels": registry.export_ha_labels()}
    
    return {
        "create_tag": create_tag,
        "suggest_tag": suggest_tag,
        "confirm_tag": confirm_tag,
        "list_tags": list_tags,
        "register_subject": register_subject,
        "assign_tag": assign_tag,
        "export_labels": export_labels,
    }
