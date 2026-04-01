"""Orakel Archive Integration — ECHTE Research laden (SOTA 2026).

Lädt und integriert ECHTE Orakel Research aus Archiven:
1. Orakel Worker Claims (Pull-Loop Runs)
2. Perplexity Research Reports
3. SOTA Reviews
4. Gap Analysis

Integration:
- Archive → OracleResearchEngine
- Real Findings → Tasks
- Validation → Implementation Tracking
"""

from __future__ import annotations

import logging
import os
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path
import threading

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# ARCHIVE LOADER
# =============================================================================

class OrakelArchiveLoader:
    """Lädt ECHTE Orakel Research aus Archiven."""
    
    def __init__(self, archive_base: str = "/config/clawd"):
        self._archive_base = Path(archive_base)
        self._loaded_research: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
    
    def load_orakel_claims(self) -> List[Dict[str, Any]]:
        """Orakel Worker Claims laden."""
        claims = []
        
        # Path: /config/clawd/pilotsuite_ops/continuous-2026-03/claims/orakel.md
        orakel_claim_path = self._archive_base / "pilotsuite_ops" / "continuous-2026-03" / "claims" / "orakel.md"
        
        if orakel_claim_path.exists():
            with open(orakel_claim_path, 'r') as f:
                content = f.read()
            
            # Parse Pull-Loop Runs
            pull_runs = re.findall(
                r'## Pull-Loop Run @ (.*?)\n\n(.*?)(?=\n## Pull-Loop Run|$)',
                content,
                re.DOTALL
            )
            
            for timestamp, run_content in pull_runs:
                claims.append({
                    "type": "orakel_pull_loop",
                    "timestamp": timestamp.strip(),
                    "content": run_content.strip(),
                    "source": str(orakel_claim_path),
                })
            
            _LOGGER.info(f"Loaded {len(claims)} Orakel Pull-Loop Runs")
        
        return claims
    
    def load_perplexity_research(self) -> List[Dict[str, Any]]:
        """Perplexity Research Reports laden."""
        research = []
        
        # Search for perplexity research files
        search_patterns = [
            "**/perplexity_research_*.md",
            "**/research_*.md",
            "**/deep_research_*.md",
        ]
        
        for pattern in search_patterns:
            for file_path in self._archive_base.glob(pattern):
                if "perplexity" in file_path.name or "research" in file_path.name:
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Parse sections
                    sections = re.findall(
                        r'## (.*?)\n\n(.*?)(?=\n## |\Z)',
                        content,
                        re.DOTALL
                    )
                    
                    for section_title, section_content in sections:
                        research.append({
                            "type": "perplexity_research",
                            "topic": section_title.strip(),
                            "content": section_content.strip(),
                            "source": str(file_path),
                            "file_date": self._extract_date_from_filename(file_path.name),
                        })
        
        _LOGGER.info(f"Loaded {len(research)} Perplexity Research sections")
        return research
    
    def load_sota_reviews(self) -> List[Dict[str, Any]]:
        """SOTA Reviews laden."""
        reviews = []
        
        # Look for SOTA review files
        sota_paths = [
            self._archive_base / "archive" / "**" / "*sota*.md",
            self._archive_base / "archive" / "**" / "*research*.md",
        ]
        
        for pattern in sota_paths:
            for file_path in self._archive_base.glob(str(pattern)):
                if file_path.exists():
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Look for Gap Analysis tables
                    gap_tables = re.findall(
                        r'\| Modell \| CoPilot \| State of the Art \| Gap \|.*?\|',
                        content,
                        re.DOTALL
                    )
                    
                    if gap_tables:
                        reviews.append({
                            "type": "sota_review",
                            "gap_analysis": gap_tables,
                            "content": content,
                            "source": str(file_path),
                        })
        
        _LOGGER.info(f"Loaded {len(reviews)} SOTA Reviews")
        return reviews
    
    def _extract_date_from_filename(self, filename: str) -> Optional[str]:
        """Datum aus Filename extrahieren."""
        match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        return match.group(1) if match else None
    
    def get_all_research(self) -> List[Dict[str, Any]]:
        """Alle Research laden."""
        all_research = []
        
        all_research.extend(self.load_orakel_claims())
        all_research.extend(self.load_perplexity_research())
        all_research.extend(self.load_sota_reviews())
        
        with self._lock:
            self._loaded_research = all_research
        
        return all_research


# =============================================================================
# RESEARCH TO TASKS CONVERTER
# =============================================================================

class ResearchToTasksConverter:
    """Konvertiert ECHTE Research in Tasks."""
    
    # Mapping von Research Topics zu Tasks
    TOPIC_TASK_MAP: Dict[str, List[Dict[str, Any]]] = {
        "Local-First AI": [
            {
                "title": "Integrate Ollama LLM runtime",
                "description": "Add Ollama integration for local LLM inference",
                "priority": "critical",
                "research_source": "perplexity_research_2026-02-16.md",
            },
            {
                "title": "Add llama.cpp support",
                "description": "Support quantized models for edge deployment",
                "priority": "high",
                "research_source": "perplexity_research_2026-02-16.md",
            },
        ],
        "Presence Detection": [
            {
                "title": "Implement Bayesian Presence Detection",
                "description": "Probabilistic presence detection with multi-sensor fusion",
                "priority": "high",
                "research_source": "perplexity_research_2026-02-16.md",
            },
            {
                "title": "Add Wi-Fi/BLE Fingerprinting",
                "description": "Device tracking via RSSI and MAC probing",
                "priority": "medium",
                "research_source": "perplexity_research_2026-02-16.md",
            },
        ],
        "Energy Management": [
            {
                "title": "Implement LSTM-based Energy Forecasting",
                "description": "Time-series prediction for energy consumption",
                "priority": "high",
                "research_source": "perplexity_research_2026-02-16.md",
            },
            {
                "title": "Add Multi-Agent Energy Optimization",
                "description": "Multi-agent RL for solar/battery/grid coordination",
                "priority": "medium",
                "research_source": "perplexity_research_2026-02-16.md",
            },
        ],
        "Pattern Recognition": [
            {
                "title": "Upgrade from Rules to LSTM/Transformer",
                "description": "Replace association rules with deep learning",
                "priority": "high",
                "research_source": "research_2026-02-17.md",
            },
        ],
        "Voice Recognition": [
            {
                "title": "Integrate Whisper Tiny",
                "description": "Local speech-to-text with Whisper",
                "priority": "critical",
                "research_source": "research_2026-02-17.md",
            },
            {
                "title": "Add Piper TTS",
                "description": "Local text-to-speech synthesis",
                "priority": "high",
                "research_source": "research_2026-02-17.md",
            },
        ],
    }
    
    def convert(self, research_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Research in Tasks konvertieren."""
        tasks = []
        
        for item in research_items:
            topic = item.get("topic", "")
            
            # Find matching tasks
            for keyword, task_list in self.TOPIC_TASK_MAP.items():
                if keyword.lower() in topic.lower():
                    for task in task_list:
                        tasks.append({
                            **task,
                            "derived_from": item.get("source", "unknown"),
                            "research_topic": topic,
                        })
        
        return tasks


# =============================================================================
# ORAKEL ARCHIVE INTEGRATION (Main Class)
# =============================================================================

class OrakelArchiveIntegration:
    """Integration für ECHTE Orakel Research."""
    
    def __init__(self, oracle_research_engine, archive_base: str = "/config/clawd"):
        self._oracle_engine = oracle_research_engine
        self._loader = OrakelArchiveLoader(archive_base)
        self._converter = ResearchToTasksConverter()
        self._lock = threading.Lock()
        _LOGGER.info("OrakelArchiveIntegration initialized")
    
    def load_and_integrate(self) -> Dict[str, Any]:
        """Research laden und integrieren."""
        # Load all research
        all_research = self._loader.get_all_research()
        
        # Convert to tasks
        tasks = self._converter.convert(all_research)
        
        # Add to Oracle Research Engine
        topic_ids = []
        for research_item in all_research:
            topic_id = self._oracle_engine.add_research(
                topic_name=f"archive_{research_item.get('type', 'unknown')}_{research_item.get('file_date', 'unknown')}",
                findings=[{
                    "title": research_item.get("topic", "Unknown"),
                    "description": research_item.get("content", "")[:500],  # Truncate
                    "confidence": 0.9,  # High confidence (archive research)
                    "source": "archive",
                    "metadata": {
                        "source_file": research_item.get("source"),
                        "research_type": research_item.get("type"),
                    },
                }],
                recommendations=[t["title"] for t in tasks if t.get("research_source") == research_item.get("source")],
            )
            topic_ids.append(topic_id)
        
        # Derive tasks from topics
        all_task_ids = []
        for topic_id in topic_ids:
            task_ids = self._oracle_engine.derive_tasks(topic_id)
            all_task_ids.extend(task_ids)
        
        return {
            "research_loaded": len(all_research),
            "topics_created": len(topic_ids),
            "tasks_derived": len(all_task_ids),
            "tasks": tasks,
        }
    
    def get_gap_analysis(self) -> Dict[str, Any]:
        """Gap Analysis aus SOTA Reviews."""
        reviews = self._loader.load_sota_reviews()
        
        gaps = []
        for review in reviews:
            # Parse gap table
            for table in review.get("gap_analysis", []):
                # Parse markdown table
                lines = table.strip().split('\n')
                if len(lines) >= 3:
                    headers = [h.strip() for h in lines[0].split('|')]
                    for row in lines[2:]:
                        cells = [c.strip() for c in row.split('|')]
                        if len(cells) >= 4:
                            gaps.append({
                                "modell": cells[0],
                                "copilot": cells[1],
                                "sota": cells[2],
                                "gap": cells[3],
                            })
        
        return {
            "gaps": gaps,
            "critical_gaps": [g for g in gaps if "HOCH" in g.get("gap", "")],
            "medium_gaps": [g for g in gaps if "MITTEL" in g.get("gap", "")],
        }


# =============================================================================
# Singleton Factory
# =============================================================================

_integration_instance: Optional[OrakelArchiveIntegration] = None


def get_orakel_archive_integration(oracle_research_engine) -> OrakelArchiveIntegration:
    """Singleton-Zugriff."""
    global _integration_instance
    
    if _integration_instance is None:
        _integration_instance = OrakelArchiveIntegration(oracle_research_engine)
    
    return _integration_instance
