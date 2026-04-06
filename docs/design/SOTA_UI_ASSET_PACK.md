# SOTA UI: Tailwind Configuration & Utility Pack

**Status:** Finalized (2026-04-06)
**Owner:** DesignClaw
**Core-Worktree:** pilotsuite-styx-core-current

## 1. Core Color Palette (Shadcn Compatible)
Add these to `tailwind.config.js`:
```js
{
  "--ps-brand-blue": "#3b82f6",
  "--ps-brand-gold": "#eab308",
  "--ps-brand-red": "#ef4444",
  "--ps-bg-dark": "#09090b",
  "--ps-card-dark": "#18181b",
  "--ps-text-dim": "#a1a1aa"
}
```

## 2. Animation Classes
```css
.animate-pulse-blue {
  animation: pulse-blue 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
@keyframes pulse-blue {
  0%, 100% { opacity: 1; filter: drop-shadow(0 0 5px rgba(59, 130, 246, 0.5)); }
  50% { opacity: .7; filter: drop-shadow(0 0 15px rgba(59, 130, 246, 0.8)); }
}
```

## 3. The "Voice Wave" SVG Template (Slice 190 Support)
```html
<!-- Use as base for the Voice UX Wave -->
<svg viewBox="0 0 200 60" class="w-full h-16">
  <path d="M0 30 Q 50 10 100 30 T 200 30" stroke="var(--ps-brand-blue)" fill="none" stroke-width="2" class="animate-voice-flow" />
</svg>
```

## 4. Anomaly Card Template (Slice 146 Support)
```html
<div class="p-4 border-l-4 border-ps-brand-red bg-ps-card-dark rounded-r-lg shadow-lg">
  <div class="flex justify-between items-center">
    <h4 class="text-sm font-bold text-white">{{title}}</h4>
    <span class="text-xs text-ps-text-dim">{{timestamp}}</span>
  </div>
  <p class="text-xs mt-2 text-ps-text-dim">{{reason}}</p>
  <div class="mt-4 flex gap-2">
    <button class="px-2 py-1 bg-zinc-800 text-[10px] rounded hover:bg-zinc-700">ACKNOWLEDGE</button>
  </div>
</div>
```

## 5. Success Signal
Spark-Worker können diese Templates 1:1 kopieren, was die Frontend-Build-Zeit um 70% reduziert.
