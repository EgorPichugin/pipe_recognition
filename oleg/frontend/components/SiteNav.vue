<script setup lang="ts">
const items = [
  { href: '#architecture', label: 'Architecture' },
  { href: '#metrics', label: 'Metrics' },
  { href: '#input', label: 'Try it' },
  { href: '#history', label: 'History' },
  { href: '#output', label: 'Output' },
]
</script>

<template>
  <header class="sticky top-0 z-50 border-b border-ink-500/30 bg-ink-950/70 backdrop-blur-lg">
    <div class="container-x flex h-16 items-center justify-between">
      <a href="#top" class="flex items-center gap-2">
        <span class="grid h-8 w-8 place-items-center rounded-lg bg-neon-gradient font-mono text-sm font-bold text-ink-950">IA</span>
        <span class="font-mono text-sm font-semibold tracking-wider text-fg">INSPECTION_AI</span>
      </a>
      <nav class="hidden items-center gap-1 md:flex">
        <a
          v-for="item in items"
          :key="item.href"
          :href="item.href"
          class="rounded-lg px-3 py-2 text-sm text-fg-muted transition-colors hover:bg-ink-800/60 hover:text-fg"
        >
          {{ item.label }}
        </a>
      </nav>
      <a href="#input" class="hidden md:inline-flex btn-primary !py-2 !px-4 !text-sm">
        Run demo
        <span aria-hidden="true">→</span>
      </a>
    </div>
  </header>
</template>
