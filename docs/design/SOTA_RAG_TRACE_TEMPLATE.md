# SOTA RAG Search & Trace UI: Frontend Template

**Status:** Finalized (2026-04-06)
**Owner:** DesignClaw
**Core-Worktree:** pilotsuite-styx-core-current
**Support for:** Slice 140 / 153

## 1. Trace Timeline Component (Shadcn/Tailwind)
```html
<div class="space-y-4 font-mono text-xs">
  <div class="flex gap-4 items-start border-l-2 border-ps-brand-blue pl-4">
    <div class="bg-ps-brand-blue/20 p-1 rounded">INGEST</div>
    <div class="flex-1 text-ps-text-dim">
      <p>User Query: "Licht im Bad gestern Abend"</p>
      <span class="text-[10px] opacity-50">T+0ms | Tokens: 12</span>
    </div>
  </div>
  
  <div class="flex gap-4 items-start border-l-2 border-ps-brand-gold pl-4 ml-2">
    <div class="bg-ps-brand-gold/20 p-1 rounded">RETRIEVAL</div>
    <div class="flex-1 text-ps-text-dim">
      <p>Source Match: memory/event_log_2026-04-05.md (Sim: 0.94)</p>
      <p class="italic">"22:45: light.bath set to on by user_andreas"</p>
    </div>
  </div>

  <div class="flex gap-4 items-start border-l-2 border-ps-brand-green pl-4">
    <div class="bg-ps-brand-green/20 p-1 rounded">REASONING</div>
    <div class="flex-1 text-ps-text-dim">
      <p>LLM: "Based on the retrieved log, Andreas turned the light on but no off-event was recorded."</p>
      <span class="text-[10px] opacity-50">T+450ms | Model: qwen3.5:9b</span>
    </div>
  </div>
</div>
```

## 2. Interactive Source Link
```html
<div class="mt-2 p-2 bg-zinc-900/50 rounded border border-white/5 flex justify-between items-center group cursor-pointer hover:border-ps-brand-blue transition-colors">
  <span class="text-[10px]">Source: memory/event_log_2026-04-05.md#L452</span>
  <svg class="w-3 h-3 opacity-0 group-hover:opacity-100" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" stroke-width="2" />
  </svg>
</div>
```

## 3. Success Signal
Spark-Worker can immediately use these templates for the "Intelligence" Tab, ensuring a unified SOTA look for RAG Traces.
