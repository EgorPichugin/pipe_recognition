<script setup lang="ts">
interface Metric {
  label: string
  value: string
  unit?: string
  trend?: number
  spark?: number[]
  hint: string
  accent: 'green' | 'cyan' | 'violet' | 'magenta'
}

const metrics: Metric[] = [
  {
    label: 'Reports generated',
    value: '1,284',
    trend: 12.4,
    spark: [4, 6, 5, 8, 7, 9, 10, 12, 11, 13, 14, 16],
    hint: 'rolling 7-day window',
    accent: 'green',
  },
  {
    label: 'Avg. latency',
    value: '4.2',
    unit: 's',
    trend: -8.1,
    spark: [12, 10, 9, 8, 8, 6, 7, 6, 5, 5, 4, 4.2],
    hint: 'photo → .docx, p50',
    accent: 'cyan',
  },
  {
    label: 'Compliance pass rate',
    value: '97.8',
    unit: '%',
    trend: 2.1,
    spark: [88, 90, 91, 90, 93, 94, 94, 95, 96, 96, 97, 97.8],
    hint: 'last 1k reports',
    accent: 'violet',
  },
  {
    label: 'Validation rejections',
    value: '2.2',
    unit: '%',
    trend: -1.3,
    spark: [6, 5, 5, 4, 4, 3, 3, 2.5, 2.2, 2.3, 2.2, 2.2],
    hint: 'patches blocked by safety layer',
    accent: 'magenta',
  },
]

function sparkPath(values: number[]): string {
  if (!values.length) return ''
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const w = 120
  const h = 40
  const step = w / (values.length - 1)
  return values
    .map((v, i) => {
      const x = (i * step).toFixed(2)
      const y = (h - ((v - min) / range) * h).toFixed(2)
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
}

const accentClasses: Record<Metric['accent'], { stroke: string; blob: string }> = {
  green: { stroke: 'stroke-neon-green', blob: 'bg-neon-green' },
  cyan: { stroke: 'stroke-neon-cyan', blob: 'bg-neon-cyan' },
  violet: { stroke: 'stroke-neon-violet', blob: 'bg-neon-violet' },
  magenta: { stroke: 'stroke-neon-magenta', blob: 'bg-neon-magenta' },
}
</script>

<template>
  <section id="metrics" class="relative py-24 md:py-32">
    <div class="container-x">
      <div class="mx-auto max-w-2xl text-center">
        <span class="section-eyebrow">// Metrics</span>
        <h2 class="section-heading mt-3">Live pipeline health</h2>
        <p class="mt-4 text-fg-muted">
          What the validation and metrics services emit on every run. Placeholders for the demo —
          wire in real telemetry next.
        </p>
      </div>

      <div class="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <div
          v-for="m in metrics"
          :key="m.label"
          class="card card-hover relative overflow-hidden p-6"
        >
          <div class="flex items-center justify-between">
            <span class="section-eyebrow">{{ m.label }}</span>
            <span
              v-if="m.trend !== undefined"
              :class="['font-mono text-xs font-semibold', m.trend >= 0 ? 'text-neon-green' : 'text-neon-cyan']"
            >
              {{ m.trend >= 0 ? '+' : '' }}{{ m.trend }}%
            </span>
          </div>

          <div class="mt-4 flex items-baseline gap-1">
            <span class="font-mono text-4xl font-bold text-fg">{{ m.value }}</span>
            <span v-if="m.unit" class="font-mono text-lg text-fg-muted">{{ m.unit }}</span>
          </div>

          <p class="mt-1 text-xs text-fg-dim">{{ m.hint }}</p>

          <svg
            v-if="m.spark"
            viewBox="0 0 120 40"
            class="mt-5 h-10 w-full"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path
              :d="sparkPath(m.spark)"
              fill="none"
              :class="['stroke-[1.5]', accentClasses[m.accent].stroke]"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>

          <div
            :class="['pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full opacity-30 blur-2xl', accentClasses[m.accent].blob]"
          ></div>
        </div>
      </div>

      <!-- Per-service status row -->
      <div class="mt-8 card p-6">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <span class="section-eyebrow">// Service status</span>
          <span class="font-mono text-xs text-fg-dim">last check 3s ago</span>
        </div>
        <div class="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div
            v-for="svc in ['Segmentation', 'Compliance', 'Manipulation', 'Completeness', 'Validation', 'Metrics', 'Report Gen', 'Storage']"
            :key="svc"
            class="flex items-center justify-between rounded-lg border border-ink-500/40 bg-ink-800/40 px-3 py-2"
          >
            <span class="font-mono text-sm text-fg">{{ svc }}</span>
            <span class="flex items-center gap-1.5">
              <span class="h-2 w-2 rounded-full bg-neon-green shadow-glow animate-pulse"></span>
              <span class="font-mono text-xs text-fg-dim">ok</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
