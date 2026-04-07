"""
Brain Graph data models with privacy-first constraints.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal

# Privacy patterns to redact from string values
PII_PATTERNS = [
    re.compile(r'\b[\w._%+-]+@[\w.-]+\.[A-Z|a-z]{2,}\b'),  # emails
    re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),            # IP addresses
    re.compile(r'\b\d{3}-?\d{3}-?\d{4}\b'),                # phone numbers
    re.compile(r'\bhttps?://[^\s]+'),                       # URLs
]

NodeKind = Literal['entity', 'zone', 'device', 'person', 'concept', 'module', 'event']
EdgeType = Literal['in_zone', 'controls', 'affects', 'correlates', 'triggered_by', 'observed_with', 'mentions']

@dataclass
class GraphNode:
    """A node in the brain graph with bounded metadata."""
    
    id: str
    kind: NodeKind
    label: str
    updated_at_ms: int
    score: float
    domain: Optional[str] = None
    source: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None
    meta: Optional[Dict[str, Any]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate and sanitize node data."""
        if not self.id or not self.label:
            raise ValueError("Node id and label are required")
            
        # Redact PII from label
        self.label = self._redact_pii(self.label)
        
        # Sanitize and bound tags
        if self.tags:
            self.tags = [self._redact_pii(tag)[:50] for tag in self.tags[:10]]
            
        # Bound and sanitize meta
        self.meta = self._sanitize_meta(self.meta or {})
    
    def _redact_pii(self, text: str) -> str:
        """Remove PII patterns from text."""
        if not isinstance(text, str):
            return str(text)[:100]  # Ensure string and bound length
            
        for pattern in PII_PATTERNS:
            text = pattern.sub('[REDACTED]', text)
        return text[:100]  # Max 100 chars
    
    def _sanitize_meta(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize and bound metadata object."""
        if not isinstance(meta, dict):
            return {}
            
        # Limit to 10 keys max
        if len(meta) > 10:
            meta = dict(list(meta.items())[:10])
            
        # Sanitize values and check total size
        sanitized = {}
        total_size = 0
        
        for key, value in meta.items():
            if not isinstance(key, str) or len(key) > 50:
                continue
                
            # Convert value to safe types only
            if isinstance(value, (str, int, float, bool)):
                if isinstance(value, str):
                    value = self._redact_pii(value)
                
                # Estimate JSON size
                json_size = len(json.dumps({key: value}))
                if total_size + json_size > 2048:  # 2KB limit
                    break
                    
                sanitized[key] = value
                total_size += json_size
                
        return sanitized
    
    def effective_score(self, now_ms: Optional[int] = None, half_life_hours: float = 24.0) -> float:
        """Calculate current score with exponential decay."""
        if now_ms is None:
            now_ms = int(time.time() * 1000)
            
        age_hours = (now_ms - self.updated_at_ms) / (1000 * 3600)
        if age_hours <= 0:
            return self.score
            
        # Exponential decay: score * exp(-λ * t), where λ = ln(2) / half_life
        import math
        decay_lambda = math.log(2) / half_life_hours
        return self.score * math.exp(-decay_lambda * age_hours)

@dataclass  
class GraphEdge:
    """An edge in the brain graph with bounded metadata."""
    
    id: str
    from_node: str
    to_node: str
    edge_type: EdgeType
    updated_at_ms: int
    weight: float
    evidence: Optional[Dict[str, str]] = None
    meta: Optional[Dict[str, Any]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate and sanitize edge data."""
        if not self.id or not self.from_node or not self.to_node:
            raise ValueError("Edge id, from_node, and to_node are required")
            
        # Sanitize evidence
        if self.evidence and isinstance(self.evidence, dict):
            # Keep only allowed keys, sanitize values
            allowed_keys = {'kind', 'ref', 'summary'}
            sanitized_evidence = {}
            for key, value in self.evidence.items():
                if key in allowed_keys and isinstance(value, str):
                    sanitized_evidence[key] = self._redact_pii(value[:100])
            self.evidence = sanitized_evidence if sanitized_evidence else None
            
        # Bound and sanitize meta (same as nodes)
        self.meta = self._sanitize_meta(self.meta or {})
    
    def _redact_pii(self, text: str) -> str:
        """Remove PII patterns from text."""
        if not isinstance(text, str):
            return str(text)[:100]
            
        for pattern in PII_PATTERNS:
            text = pattern.sub('[REDACTED]', text)
        return text[:100]
    
    def _sanitize_meta(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize and bound metadata object (same logic as GraphNode)."""
        if not isinstance(meta, dict):
            return {}
            
        # Limit to 10 keys max
        if len(meta) > 10:
            meta = dict(list(meta.items())[:10])
            
        sanitized = {}
        total_size = 0
        
        for key, value in meta.items():
            if not isinstance(key, str) or len(key) > 50:
                continue
                
            if isinstance(value, (str, int, float, bool)):
                if isinstance(value, str):
                    value = self._redact_pii(value)
                
                json_size = len(json.dumps({key: value}))
                if total_size + json_size > 2048:  # 2KB limit
                    break
                    
                sanitized[key] = value
                total_size += json_size
                
        return sanitized
    
    def effective_weight(self, now_ms: Optional[int] = None, half_life_hours: float = 12.0) -> float:
        """Calculate current weight with exponential decay."""
        if now_ms is None:
            now_ms = int(time.time() * 1000)
            
        age_hours = (now_ms - self.updated_at_ms) / (1000 * 3600)
        if age_hours <= 0:
            return self.weight
            
        import math
        decay_lambda = math.log(2) / half_life_hours
        return self.weight * math.exp(-decay_lambda * age_hours)
    
    @classmethod
    def create_id(cls, from_node: str, edge_type: str, to_node: str) -> str:
        """Generate stable edge ID from components."""
        import hashlib
        content = f"{from_node}|{edge_type}|{to_node}"
        return f"e:{hashlib.sha256(content.encode()).hexdigest()[:16]}"