<script setup lang="ts">
import type { PhotoRecord } from '~/composables/useReportApi'

const { listPhotos, exportPhotosCsv } = useReportApi()

const photos = ref<PhotoRecord[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const isExporting = ref(false)

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await listPhotos()
    photos.value = res.photos
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e)
    error.value = message.includes('Failed to fetch')
      ? 'Backend unreachable. Start FastAPI on :8000.'
      : message
  } finally {
    loading.value = false
  }
}

async function exportCsv() {
  isExporting.value = true
  try {
    const blob = await exportPhotosCsv()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'photo-history.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    isExporting.value = false
  }
}

const categoryClass = (category: string) => {
  if (category.includes('crack') || category.includes('damage')) {
    return 'border-red-500/50 bg-red-500/[0.10] text-red-300'
  }
  if (category.includes('missing')) {
    return 'border-neon-magenta/50 bg-neon-magenta/[0.08] text-neon-magenta'
  }
  if (category.includes('uneven') || category.includes('loose')) {
    return 'border-yellow-500/50 bg-yellow-500/[0.10] text-yellow-300'
  }
  return 'border-neon-cyan/50 bg-neon-cyan/[0.08] text-neon-cyan'
}

const statusClass = (status: string) => {
  switch (status) {
    case 'detected':
      return 'text-yellow-300 border-yellow-500/50'
    case 'flagged':
      return 'text-red-300 border-red-500/50'
    case 'ok':
      return 'text-neon-green border-neon-green/50'
    default:
      return 'text-fg-muted border-ink-500'
  }
}

onMounted(load)
</script>

<template>
  <section id="history" class="relative py-20 md:py-28">
    <div class="container-x">
      <div class="mx-auto max-w-2xl text-center">
        <span class="section-eyebrow">// Photo analysis history</span>
        <h2 class="section-heading mt-3">What the model has seen</h2>
        <p class="mt-4 text-fg-muted">
          Each row is a photo that already ran through OCR + categorization. The generator above
          uses this list as its source.
        </p>
      </div>

      <div class="mt-10 flex flex-wrap items-center justify-center gap-3">
        <button type="button" class="btn-ghost" :disabled="loading" @click="load">
          <span v-if="loading" class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-fg border-r-transparent"></span>
          Refresh
        </button>
        <button type="button" class="btn-ghost" :disabled="isExporting" @click="exportCsv">
          <span v-if="isExporting" class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-fg border-r-transparent"></span>
          Download CSV ↓
        </button>
      </div>

      <div v-if="error" class="mx-auto mt-6 max-w-2xl rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-3 text-center text-sm text-red-200">
        {{ error }}
      </div>

      <div v-if="photos.length" class="card mt-10 overflow-x-auto">
        <table class="w-full min-w-[720px] text-sm">
          <thead class="border-b border-ink-500/40 text-left font-mono text-[10px] uppercase tracking-widest text-fg-dim">
            <tr>
              <th class="px-4 py-3">ID</th>
              <th class="px-4 py-3">Image</th>
              <th class="px-4 py-3">Category</th>
              <th class="px-4 py-3">Status</th>
              <th class="px-4 py-3">Lat</th>
              <th class="px-4 py-3">Lon</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="photo in photos"
              :key="photo.id"
              class="border-b border-ink-500/20 hover:bg-ink-700/30"
            >
              <td class="px-4 py-3 font-mono text-xs text-fg-dim">{{ photo.id }}</td>
              <td class="px-4 py-3 font-mono text-xs text-fg">{{ photo.image_name }}</td>
              <td class="px-4 py-3">
                <span :class="['inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider', categoryClass(photo.category)]">
                  {{ photo.category }}
                </span>
              </td>
              <td class="px-4 py-3">
                <span :class="['inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider', statusClass(photo.status)]">
                  {{ photo.status }}
                </span>
              </td>
              <td class="px-4 py-3 font-mono text-xs text-fg-muted">{{ photo.latitude }}</td>
              <td class="px-4 py-3 font-mono text-xs text-fg-muted">{{ photo.longitude }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="!loading" class="mt-8 text-center font-mono text-sm text-fg-dim">
        No photos analyzed yet.
      </div>
    </div>
  </section>
</template>
