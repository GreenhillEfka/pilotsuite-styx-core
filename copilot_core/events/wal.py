import os
import json
import gzip
import time
from datetime import datetime
from pathlib import Path

class WAL:
    def __init__(self, log_dir: str = "./wal_logs", max_size_mb: int = 10, rotation_interval_hours: int = 24):
        self.log_dir = Path(log_dir)
        self.max_size_mb = max_size_mb * 1024 * 1024  # Convert to bytes
        self.rotation_interval_hours = rotation_interval_hours
        self.current_log_file = None
        self.last_rotation_time = time.time()
        
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize first log file
        self._rotate_if_needed()
    
    def _get_current_log_path(self) -> Path:
        now = datetime.now()
        return self.log_dir / f"wal_{now.strftime('%Y%m%d_%H%M%S')}.log.gz"
    
    def _rotate_if_needed(self):
        current_time = time.time()
        
        # Check if we need to rotate based on time
        if (current_time - self.last_rotation_time) >= (self.rotation_interval_hours * 3600):
            self.current_log_file = self._get_current_log_path()
            self.last_rotation_time = current_time
            return True
        
        # Check if we need to rotate based on size
        if self.current_log_file and self.current_log_file.exists():
            if self.current_log_file.stat().st_size >= self.max_size_mb:
                self.current_log_file = self._get_current_log_path()
                self.last_rotation_time = current_time
                return True
        
        # Initialize if no current log file
        if not self.current_log_file:
            self.current_log_file = self._get_current_log_path()
            return True
        
        return False
    
    def write_event(self, event_type: str, data: dict):
        """Write a semantic event to the WAL."""
        # Ensure we have a current log file
        self._rotate_if_needed()
        
        # Create event record
        event_record = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data
        }
        
        # Write to compressed log file
        try:
            with gzip.open(self.current_log_file, 'at', encoding='utf-8') as f:
                f.write(json.dumps(event_record) + '\n')
        except Exception as e:
            print(f"Error writing to WAL: {e}")
    
    def replay_events(self, start_time: str = None, end_time: str = None):
        """Replay events from the WAL for crash recovery."""
        events = []
        
        # Get all log files in directory, sorted by name (which includes timestamp)
        log_files = sorted(self.log_dir.glob("*.log.gz"))
        
        for log_file in log_files:
            try:
                with gzip.open(log_file, 'rt', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            
                            # Filter by time range if specified
                            if start_time and event["timestamp"] < start_time:
                                continue
                            if end_time and event["timestamp"] > end_time:
                                continue
                            
                            events.append(event)
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Error reading log file {log_file}: {e}")
        
        return events
    
    def get_last_event(self):
        """Get the last recorded event for recovery purposes."""
        events = self.replay_events()
        return events[-1] if events else None