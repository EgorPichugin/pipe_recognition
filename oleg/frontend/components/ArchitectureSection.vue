<script setup lang="ts">
type NodeKind = 'input' | 'process' | 'parallel' | 'validate' | 'metrics' | 'output' | 'sink'

interface PipelineNode {
  id: string
  label: string
  detail: string
  kind: NodeKind
  glyph: string
}

const inputs: PipelineNode[] = [
  { id: 'picture', label: 'Picture', detail: 'site photo', kind: 'input', glyph: 'IMG' },
  { id: 'requirements', label: 'Requirements', detail: 'natural language', kind: 'input', glyph: 'TXT' },
]

const segmentation: PipelineNode = {
  id: 'segmentation',
  label: 'Segmentation',
  detail: 'parse + chunk',
  kind: 'process',
  glyph: '01',
}

const parallel: PipelineNode[] = [
  { id: 'compliance', label: 'Compliance', detail: 'regulatory checks', kind: 'parallel', glyph: '02' },
  { id: 'manipulation', label: 'Manipulation', detail: 'image tampering', kind: 'parallel', glyph: '03' },
  { id: 'completeness', label: 'Completeness', detail: 'gap detection', kind: 'parallel', glyph: '04' },
]

const tail: PipelineNode[] = [
  { id: 'validation', label: 'Validation', detail: 'merge + verify', kind: 'validate', glyph: '05' },
  { id: 'metrics', label: 'Metrics', detail: 'score + grade', kind: 'metrics', glyph: '06' },
  { id: 'report', label: 'Report Gen', detail: 'render .docx', kind: 'output', glyph: '07' },
]

function colorFor(kind: NodeKind): string {
  switch (kind) {
    case 'input':
      return 'border-neon-cyan/40 bg-neon-cyan/[0.06]'
    case 'process':
      return 'border-neon-violet/40 bg-neon-violet/[0.06]'
    case 'parallel':
      return 'border-fg-muted/30 bg-ink-700/40'
    case 'validate':
      return 'border-neon-magenta/40 bg-neon-magenta/[0.06]'
    case 'metrics':
      return 'border-neon-cyan/40 bg-neon-cyan/[0.06]'
    case 'output':
      return 'border-neon-green/40 bg-neon-green/[0.06]'
    case 'sink':
      return 'border-neon-green/60 bg-neon-green/[0.10]'
  }
}
</script>

<template>
  <section id="architecture" class="relative py-24 md:py-32">
    <div class="container-x">
      <div class="mx-auto max-w-2xl text-center">
        <span class="section-eyebrow">// Architecture</span>
        <h2 class="section-heading mt-3">From photo to PDF in seven services</h2>
        <p class="mt-4 text-fg-muted">
          A modular pipeline. Each box is an isolated service — swap models, scale independently,
          observe failures in one place.
        </p>
      </div>

      <div
        class="mt-14 overflow-x-auto pb-4"
        style="scrollbar-width: thin"
      >
        <div class="mx-auto flex min-w-[1080px] items-stretch gap-4 px-2 lg:min-w-0">
          <!-- Inputs (stacked) -->
          <div class="flex flex-1 flex-col justify-center gap-3">
            <div
              v-for="node in inputs"
              :key="node.id"
              :class="['card px-4 py-3 transition-colors', colorFor(node.kind)]"
            >
              <div class="flex items-center justify-between">
                <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">{{ node.glyph }}</span>
                <span class="h-1.5 w-1.5 rounded-full bg-neon-cyan animate-pulse"></span>
              </div>
              <div class="mt-1 font-semibold text-fg">{{ node.label }}</div>
              <div class="font-mono text-xs text-fg-dim">{{ node.detail }}</div>
            </div>
          </div>

          <Arrow />

          <!-- Segmentation -->
          <div class="flex flex-1 items-center">
            <div :class="['card w-full px-4 py-5', colorFor(segmentation.kind)]">
              <div class="flex items-center justify-between">
                <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">{{ segmentation.glyph }}</span>
                <span class="h-1.5 w-1.5 rounded-full bg-neon-violet animate-pulse"></span>
              </div>
              <div class="mt-1 font-semibold text-fg">{{ segmentation.label }}</div>
              <div class="font-mono text-xs text-fg-dim">{{ segmentation.detail }}</div>
            </div>
          </div>

          <ArrowFan />

          <!-- Parallel services -->
          <div class="flex flex-1 flex-col justify-center gap-3">
            <div
              v-for="(node, i) in parallel"
              :key="node.id"
              :class="['card px-4 py-3 transition-colors', colorFor(node.kind)]"
              :style="{ animationDelay: `${i * 80}ms` }"
            >
              <div class="flex items-center justify-between">
                <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">{{ node.glyph }}</span>
                <span class="font-mono text-[10px] text-fg-dim">parallel</span>
              </div>
              <div class="mt-1 font-semibold text-fg">{{ node.label }}</div>
              <div class="font-mono text-xs text-fg-dim">{{ node.detail }}</div>
            </div>
          </div>

          <ArrowFanIn />

          <!-- Validation + Metrics + Report -->
          <div
            v-for="node in tail"
            :key="node.id"
            class="flex flex-1 items-center"
          >
            <div :class="['card w-full px-4 py-5', colorFor(node.kind)]">
              <div class="flex items-center justify-between">
                <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">{{ node.glyph }}</span>
                <span class="h-1.5 w-1.5 rounded-full bg-current opacity-70"></span>
              </div>
              <div class="mt-1 font-semibold text-fg">{{ node.label }}</div>
              <div class="font-mono text-xs text-fg-dim">{{ node.detail }}</div>
            </div>
          </div>

          <Arrow />

          <!-- PDF sink -->
          <div class="flex items-center">
            <div class="card px-5 py-5 border-neon-green/60 bg-neon-green/[0.10] shadow-glow">
              <div class="font-mono text-[10px] uppercase tracking-widest text-neon-green">output</div>
              <div class="mt-1 font-mono text-2xl font-bold text-neon-green">PDF</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Legend -->
      <div class="mt-10 flex flex-wrap items-center justify-center gap-3 text-xs">
        <span class="label-tag">
          <span class="h-2 w-2 rounded-full bg-neon-cyan"></span>
          Input
        </span>
        <span class="label-tag">
          <span class="h-2 w-2 rounded-full bg-neon-violet"></span>
          Process
        </span>
        <span class="label-tag">
          <span class="h-2 w-2 rounded-full bg-neon-magenta"></span>
          Validation
        </span>
        <span class="label-tag">
          <span class="h-2 w-2 rounded-full bg-neon-green"></span>
          Output
        </span>
      </div>
    </div>
  </section>
</template>
