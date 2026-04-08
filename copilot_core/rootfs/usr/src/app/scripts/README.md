# PilotSuite Core Scripts

Utility scripts for development, profiling, and maintenance.

---

## 📊 Startup Profiling

**Script:** `profile_startup.py`

Identifies bottlenecks during service initialization by measuring import times, service initialization times, and memory usage.

### Usage

```bash
# Basic profiling (outputs to console + reports/startup-profile.json)
python scripts/profile_startup.py

# Custom output path
python scripts/profile_startup.py --output reports/my-profile.json

# Show only top 5 bottlenecks
python scripts/profile_startup.py --top 5

# Enable verbose logging
python scripts/profile_startup.py --verbose

# Use cProfile for detailed function-level profiling
python scripts/profile_startup.py --cprofile

# Disable JSON output (console only)
python scripts/profile_startup.py --no-output
```

### Output

**Console:**
```
======================================================================
📊 STARTUP PROFILING RESULTS
======================================================================

⏱️  Total Startup Time: 1847.32ms
💾 Peak Memory Usage: 256.45MB
🐍 Python Version: 3.11.6
🖥️  Platform: Linux-6.1.0-x86_64

📈 Category Summary:
  core           :  15 modules,  1234.56ms total,  82.30ms avg
  ml             :   5 modules,   456.78ms total,  91.36ms avg
  api            :  10 modules,   123.45ms total,  12.35ms avg
  service        :   8 modules,    32.53ms total,   4.07ms avg

🔥 Top 10 Bottlenecks:
   1. copilot_core.brain_graph.service         456.78ms (core)
   2. copilot_core.vector_store                234.56ms (core)
   3. copilot_core.energy.service              189.23ms (core)
   4. copilot_core.ml.timeseries               156.78ms (ml)
   5. copilot_core.embedding_engine            123.45ms (core)
  ...

💾 Detailed results saved to: reports/startup-profile.json
======================================================================
```

**JSON Output:** Structured data with:
- Total startup time
- Per-module timing breakdown
- Category summaries (count, total, avg, max)
- Memory usage deltas
- Success/failure status
- Platform info

### When to Use

- **Before optimization:** Establish baseline metrics
- **After adding new modules:** Check impact on startup time
- **Performance regression:** Identify what slowed down
- **Production readiness:** Verify startup time <5s target

### Target Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Total Startup Time | <5000ms | TBD |
| Import Time (slowest module) | <500ms | TBD |
| Memory Peak | <512MB | TBD |

---

## 🔧 Future Scripts (Planned)

### Model Conversion
**Script:** `convert_models.py` (Phase 7 P2)

Convert PyTorch models to TFLite/ONNX for on-device inference.

```bash
python scripts/convert_models.py --input models/mood.pt --output models/mood.onnx
```

### Cache Warming
**Script:** `warm_cache.py` (Phase 7 P1)

Pre-populate cache with frequently accessed data.

```bash
python scripts/warm_cache.py --sensors --habitus --rag
```

### Performance Benchmark
**Script:** `benchmark_endpoints.py` (Phase 7 P1)

Load test API endpoints to measure latency under load.

```bash
python scripts/benchmark_endpoints.py --endpoint /api/v1/sensors --requests 1000
```

---

## 📝 Notes

- All scripts should be idempotent (safe to run multiple times)
- Scripts should not modify production data without explicit confirmation
- Use `--dry-run` flag when implementing destructive operations
- Log output should be machine-parseable (JSON option available)
