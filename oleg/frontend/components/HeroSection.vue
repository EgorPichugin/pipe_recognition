<template>
  <section id="top" class="relative overflow-hidden pt-12 pb-24 md:pt-20 md:pb-32">
    <div
      class="pointer-events-none absolute inset-0 -z-10 opacity-60"
      style="
        background-image:
          linear-gradient(rgba(148,163,184,0.06) 1px, transparent 1px),
          linear-gradient(90deg, rgba(148,163,184,0.06) 1px, transparent 1px);
        background-size: 48px 48px;
        mask-image: radial-gradient(ellipse at 50% 30%, black 30%, transparent 75%);
      "
    />

    <div class="container-x">
      <div class="mx-auto max-w-3xl text-center animate-fade-up">
        <span class="label-tag">
          <span class="h-1.5 w-1.5 rounded-full bg-neon-green shadow-glow"></span>
          Vienna Hackathon · 2026
        </span>

        <h1 class="mt-6 font-sans text-5xl font-extrabold leading-[1.05] tracking-tight md:text-7xl">
          AI-driven
          <span class="gradient-text">inspection reports</span>
          in seconds
        </h1>

        <p class="mx-auto mt-6 max-w-2xl text-balance text-lg text-fg-muted md:text-xl">
          Drop in a site photo and a requirements brief — our pipeline segments, validates,
          and assembles a polished <span class="font-mono text-fg">.docx</span> report end-to-end.
        </p>

        <div class="mt-10 flex flex-wrap items-center justify-center gap-3">
          <a href="#input" class="btn-primary">
            Try the demo
            <span aria-hidden="true">→</span>
          </a>
          <a href="#architecture" class="btn-ghost">See the architecture</a>
        </div>

        <dl class="mx-auto mt-14 grid max-w-2xl grid-cols-3 gap-4 text-left">
          <div class="card px-4 py-3">
            <dt class="section-eyebrow">Pipeline</dt>
            <dd class="mt-1 font-mono text-2xl font-bold text-fg">7</dd>
            <dd class="text-xs text-fg-dim">services</dd>
          </div>
          <div class="card px-4 py-3">
            <dt class="section-eyebrow">Latency</dt>
            <dd class="mt-1 font-mono text-2xl font-bold text-neon-cyan">~4.2s</dd>
            <dd class="text-xs text-fg-dim">per report</dd>
          </div>
          <div class="card px-4 py-3">
            <dt class="section-eyebrow">Output</dt>
            <dd class="mt-1 font-mono text-2xl font-bold text-neon-green">.docx</dd>
            <dd class="text-xs text-fg-dim">→ PDF ready</dd>
          </div>
        </dl>
      </div>
    </div>
  </section>
</template>
