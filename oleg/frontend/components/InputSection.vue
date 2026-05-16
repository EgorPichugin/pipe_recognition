<script setup lang="ts">
const { generateFromPhotos } = useReportApi()
const emit = defineEmits<{ generated: [] }>()

const context = ref('')
const file = ref<File | null>(null)
const filePreview = ref<string | null>(null)
const fileName = ref<string | null>(null)
const isDragging = ref(false)
const isLoading = ref(false)
const error = ref<string | null>(null)
const lastReportId = ref<string | null>(null)

function onFile(f: File | null) {
  if (!f) {
    file.value = null
    filePreview.value = null
    fileName.value = null
    return
  }
  file.value = f
  fileName.value = f.name
  if (f.type.startsWith('image/')) {
    if (filePreview.value) URL.revokeObjectURL(filePreview.value)
    filePreview.value = URL.createObjectURL(f)
  } else {
    filePreview.value = null
  }
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) onFile(f)
}

function onFileInput(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0] || null
  onFile(f)
}

async function submit() {
  isLoading.value = true
  error.value = null
  lastReportId.value = null
  try {
    const report = await generateFromPhotos(context.value.trim() || undefined)
    lastReportId.value = report.metadata.report_id
    emit('generated')
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e)
    error.value = message.includes('Failed to fetch')
      ? 'Backend unreachable. Start FastAPI on :8000 (uvicorn src.main:app).'
      : message
  } finally {
    isLoading.value = false
  }
}

onUnmounted(() => {
  if (filePreview.value) URL.revokeObjectURL(filePreview.value)
})
</script>

<template>
  <section id="input" class="relative py-24 md:py-32">
    <div class="container-x">
      <div class="mx-auto max-w-2xl text-center">
        <span class="section-eyebrow">// Input</span>
        <h2 class="section-heading mt-3">Drop the brief in, get a report out</h2>
        <p class="mt-4 text-fg-muted">
          Picture is optional for the demo — the backend already has analyzed photos. Add optional
          context for the generator and hit Generate to run Gemini over the photo history.
        </p>
      </div>

      <div class="mt-14 grid gap-6 lg:grid-cols-2">
        <!-- Picture upload -->
        <div class="card p-6">
          <div class="flex items-center justify-between">
            <span class="section-eyebrow">Picture</span>
            <span class="font-mono text-xs text-fg-dim">optional</span>
          </div>

          <label
            class="mt-4 flex h-64 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed transition-colors"
            :class="isDragging ? 'border-neon-cyan bg-neon-cyan/[0.06]' : 'border-ink-500/60 bg-ink-900/40 hover:border-ink-400'"
            @dragover.prevent="isDragging = true"
            @dragleave.prevent="isDragging = false"
            @drop="onDrop"
          >
            <input
              type="file"
              accept="image/*"
              class="sr-only"
              @change="onFileInput"
            />
            <template v-if="filePreview">
              <img :src="filePreview" alt="" class="h-full max-h-60 w-full rounded-lg object-contain" />
            </template>
            <template v-else>
              <svg class="h-10 w-10 text-fg-dim" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              <p class="mt-3 font-mono text-sm text-fg">Drop an image or click to browse</p>
              <p class="mt-1 font-mono text-xs text-fg-dim">PNG · JPG · WEBP</p>
            </template>
          </label>

          <p v-if="fileName" class="mt-3 truncate font-mono text-xs text-fg-dim">{{ fileName }}</p>
        </div>

        <!-- Context -->
        <div class="card p-6">
          <div class="flex items-center justify-between">
            <span class="section-eyebrow">Context</span>
            <span class="font-mono text-xs text-fg-dim">{{ context.length }} / 4000</span>
          </div>

          <textarea
            v-model="context"
            maxlength="4000"
            rows="6"
            placeholder="Optional notes for the generator (site, client, priorities…)"
            class="mt-4 w-full resize-none rounded-xl border border-ink-500/60 bg-ink-900/60 px-4 py-3 font-sans text-fg placeholder:text-fg-dim focus:border-neon-cyan/60 focus:outline-none focus:ring-2 focus:ring-neon-cyan/20"
          />

          <button
            type="button"
            class="btn-primary mt-6 w-full"
            :disabled="isLoading"
            @click="submit"
          >
            <span v-if="isLoading" class="flex items-center gap-2">
              <span class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-ink-950 border-r-transparent"></span>
              Generating with Gemini…
            </span>
            <span v-else>
              Generate report
              <span aria-hidden="true">→</span>
            </span>
          </button>

          <div v-if="error" class="mt-4 rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            <span class="font-mono text-xs uppercase tracking-wider text-red-400">error</span>
            <p class="mt-1">{{ error }}</p>
          </div>

          <div v-else-if="lastReportId" class="mt-4 rounded-lg border border-neon-green/40 bg-neon-green/[0.08] px-4 py-3 text-sm text-fg">
            <span class="font-mono text-xs uppercase tracking-wider text-neon-green">ok</span>
            <p class="mt-1">
              Generated report <span class="font-mono">{{ lastReportId }}</span>. Scroll down to review and edit it.
            </p>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
