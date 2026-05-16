<script setup lang="ts">
import type {
  EvaluationFinding,
  ReportEvaluation,
  ReportIssue,
  ReportSchema,
} from '~/composables/useReportApi'

const {
  getSchema,
  saveSchema,
  resetReport,
  downloadPreview,
  downloadPreviewPdf,
  evaluateReport,
} = useReportApi()

const props = defineProps<{ refreshKey?: number }>()

const report = ref<ReportSchema | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const isResetting = ref(false)
const isDownloadingDocx = ref(false)
const isDownloadingPdf = ref(false)
const isSaving = ref(false)
const isEvaluating = ref(false)
const isEditing = ref(false)
const evaluation = ref<ReportEvaluation | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    report.value = await getSchema()
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e)
    error.value = message.includes('Failed to fetch')
      ? 'Backend unreachable. Start FastAPI on :8000.'
      : message
  } finally {
    loading.value = false
  }
}

async function reset() {
  isResetting.value = true
  evaluation.value = null
  try {
    report.value = await resetReport()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    isResetting.value = false
  }
}

async function downloadDocx() {
  isDownloadingDocx.value = true
  try {
    const blob = await downloadPreview()
    triggerDownload(blob, 'inspection-report.docx')
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    isDownloadingDocx.value = false
  }
}

async function downloadPdf() {
  isDownloadingPdf.value = true
  try {
    const blob = await downloadPreviewPdf()
    triggerDownload(blob, 'inspection-report.pdf')
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    isDownloadingPdf.value = false
  }
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function save() {
  if (!report.value) return
  isSaving.value = true
  error.value = null
  try {
    report.value = await saveSchema(report.value)
    isEditing.value = false
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    isSaving.value = false
  }
}

async function runEvaluation() {
  isEvaluating.value = true
  evaluation.value = null
  error.value = null
  try {
    evaluation.value = await evaluateReport()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    isEvaluating.value = false
  }
}

function addSection() {
  if (!report.value) return
  report.value.sections.push({ heading: 'New section', body: '' })
}

function removeSection(index: number) {
  if (!report.value) return
  report.value.sections.splice(index, 1)
}

function addIssue() {
  if (!report.value) return
  const nextNumber = (report.value.issues.length + 1).toString().padStart(3, '0')
  report.value.issues.push({
    issue_id: `ISS-${nextNumber}`,
    title: 'New issue',
    description: '',
    severity: 'low',
    recommendation: '',
    image_path: null,
  })
}

function removeIssue(index: number) {
  if (!report.value) return
  report.value.issues.splice(index, 1)
}

function addNextStep() {
  if (!report.value) return
  report.value.next_steps.push('')
}

function removeNextStep(index: number) {
  if (!report.value) return
  report.value.next_steps.splice(index, 1)
}

onMounted(load)
watch(
  () => props.refreshKey,
  () => {
    evaluation.value = null
    load()
  },
)

const severityClass = (sev: ReportIssue['severity']) => {
  switch (sev) {
    case 'critical':
      return 'border-red-500/60 bg-red-500/[0.12] text-red-300'
    case 'high':
      return 'border-neon-magenta/60 bg-neon-magenta/[0.10] text-neon-magenta'
    case 'medium':
      return 'border-yellow-500/60 bg-yellow-500/[0.10] text-yellow-300'
    case 'low':
    default:
      return 'border-neon-cyan/60 bg-neon-cyan/[0.10] text-neon-cyan'
  }
}

const statusClass = (status: string) => {
  switch (status) {
    case 'final':
      return 'text-neon-green border-neon-green/60'
    case 'review':
      return 'text-neon-cyan border-neon-cyan/60'
    case 'draft':
    default:
      return 'text-fg-muted border-ink-500'
  }
}

const findingClass = (severity: EvaluationFinding['severity']) => {
  switch (severity) {
    case 'high':
      return 'border-red-500/60 bg-red-500/[0.08] text-red-200'
    case 'medium':
      return 'border-yellow-500/60 bg-yellow-500/[0.08] text-yellow-200'
    case 'low':
      return 'border-neon-cyan/60 bg-neon-cyan/[0.08] text-neon-cyan'
    case 'info':
    default:
      return 'border-ink-500/60 bg-ink-700/40 text-fg-muted'
  }
}

const scoreClass = (score: number) => {
  if (score >= 80) return 'text-neon-green'
  if (score >= 60) return 'text-neon-cyan'
  if (score >= 40) return 'text-yellow-300'
  return 'text-red-300'
}

const inputClass =
  'w-full rounded-lg border border-ink-500/60 bg-ink-900/60 px-3 py-2 text-fg placeholder:text-fg-dim focus:border-neon-cyan/60 focus:outline-none focus:ring-2 focus:ring-neon-cyan/20'
</script>

<template>
  <section id="output" class="relative py-24 md:py-32">
    <div class="container-x">
      <div class="mx-auto max-w-2xl text-center">
        <span class="section-eyebrow">// Output</span>
        <h2 class="section-heading mt-3">The generated report</h2>
        <p class="mt-4 text-fg-muted">
          Pulled live from <code class="font-mono text-fg">GET /report/schema</code>. Edit inline,
          download as PDF / DOCX, or run a Gemini QA pass.
        </p>
      </div>

      <div class="mt-10 flex flex-wrap items-center justify-center gap-3">
        <button type="button" class="btn-ghost" :disabled="loading" @click="load">
          <span v-if="loading" class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-fg border-r-transparent"></span>
          Refresh
        </button>
        <button type="button" class="btn-ghost" :disabled="isResetting" @click="reset">
          <span v-if="isResetting" class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-fg border-r-transparent"></span>
          Reset to dummy
        </button>
        <button
          type="button"
          class="btn-ghost"
          :class="isEditing ? 'border-neon-cyan/60 text-neon-cyan' : ''"
          @click="isEditing = !isEditing"
        >
          {{ isEditing ? 'Stop editing' : 'Edit' }}
        </button>
        <button v-if="isEditing" type="button" class="btn-primary" :disabled="isSaving" @click="save">
          <span v-if="isSaving" class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-ink-950 border-r-transparent"></span>
          Save changes
        </button>
        <button type="button" class="btn-ghost" :disabled="isEvaluating" @click="runEvaluation">
          <span v-if="isEvaluating" class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-fg border-r-transparent"></span>
          Evaluate with Gemini
        </button>
        <button type="button" class="btn-ghost" :disabled="isDownloadingDocx" @click="downloadDocx">
          <span v-if="isDownloadingDocx" class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-fg border-r-transparent"></span>
          Download .docx ↓
        </button>
        <button type="button" class="btn-primary" :disabled="isDownloadingPdf" @click="downloadPdf">
          <span v-if="isDownloadingPdf" class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-ink-950 border-r-transparent"></span>
          Download PDF ↓
        </button>
      </div>

      <div v-if="error" class="mx-auto mt-8 max-w-2xl rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-3 text-center text-sm text-red-200">
        {{ error }}
      </div>

      <div v-if="evaluation" class="mx-auto mt-10 max-w-4xl card p-6">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <span class="section-eyebrow">QA report (Gemini)</span>
            <p class="mt-1 text-sm text-fg-muted">{{ evaluation.summary }}</p>
          </div>
          <div class="text-right">
            <div :class="['font-mono text-3xl font-bold', scoreClass(evaluation.overall_score)]">
              {{ evaluation.overall_score }}<span class="text-base text-fg-dim">/100</span>
            </div>
            <p class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">overall score</p>
          </div>
        </div>
        <div v-if="evaluation.findings.length" class="mt-4 grid gap-2">
          <div
            v-for="(finding, i) in evaluation.findings"
            :key="i"
            :class="['rounded-lg border px-3 py-2 text-sm', findingClass(finding.severity)]"
          >
            <span class="font-mono text-[10px] uppercase tracking-widest">[{{ finding.severity }}]</span>
            <span class="ml-2 font-mono text-xs text-fg-dim">{{ finding.target }}</span>
            <p class="mt-1 text-fg">{{ finding.message }}</p>
          </div>
        </div>
        <div v-if="evaluation.recommendations.length" class="mt-4">
          <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Recommended edits</span>
          <ul class="mt-2 list-disc space-y-1 pl-5 text-sm text-fg">
            <li v-for="(rec, i) in evaluation.recommendations" :key="i">{{ rec }}</li>
          </ul>
        </div>
      </div>

      <!-- VIEW MODE -->
      <div v-if="report && !isEditing" class="mt-12 grid gap-6 lg:grid-cols-3">
        <div class="space-y-6 lg:col-span-2">
          <div class="card p-6">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p class="font-mono text-xs uppercase tracking-widest text-fg-dim">
                  {{ report.metadata.report_id }}
                </p>
                <h3 class="mt-1 text-2xl font-bold text-fg">{{ report.metadata.title }}</h3>
              </div>
              <span
                :class="['inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-xs uppercase tracking-wider', statusClass(report.metadata.status)]"
              >
                {{ report.metadata.status }}
              </span>
            </div>

            <dl class="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div>
                <dt class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Date</dt>
                <dd class="mt-0.5 font-mono text-fg">{{ report.metadata.report_date }}</dd>
              </div>
              <div>
                <dt class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Prepared by</dt>
                <dd class="mt-0.5 text-fg">{{ report.metadata.prepared_by }}</dd>
              </div>
              <div>
                <dt class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Client</dt>
                <dd class="mt-0.5 text-fg">{{ report.client.name }} <span class="text-fg-dim">· {{ report.client.role }}</span></dd>
              </div>
              <div>
                <dt class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Location</dt>
                <dd class="mt-0.5 text-fg">{{ report.location.site_name }}<span v-if="report.location.room" class="text-fg-dim"> · {{ report.location.room }}</span></dd>
                <dd class="text-xs text-fg-dim">{{ report.location.address }}</dd>
              </div>
            </dl>
          </div>

          <div class="card p-6">
            <span class="section-eyebrow">Executive summary</span>
            <p class="mt-3 leading-relaxed text-fg">{{ report.executive_summary }}</p>
          </div>

          <div v-for="section in report.sections" :key="section.heading" class="card p-6">
            <span class="section-eyebrow">{{ section.heading }}</span>
            <p class="mt-3 leading-relaxed text-fg">{{ section.body }}</p>
          </div>
        </div>

        <div class="space-y-6">
          <div class="card p-6 lg:sticky lg:top-24">
            <span class="section-eyebrow">Next steps</span>
            <ol class="mt-4 space-y-3">
              <li
                v-for="(step, i) in report.next_steps"
                :key="i"
                class="flex gap-3"
              >
                <span class="grid h-6 w-6 shrink-0 place-items-center rounded-full border border-neon-green/40 bg-neon-green/[0.08] font-mono text-[10px] text-neon-green">
                  {{ i + 1 }}
                </span>
                <span class="text-sm leading-relaxed text-fg">{{ step }}</span>
              </li>
            </ol>
          </div>
        </div>
      </div>

      <!-- EDIT MODE -->
      <div v-else-if="report && isEditing" class="mt-12 grid gap-6">
        <div class="card p-6">
          <span class="section-eyebrow">Metadata</span>
          <div class="mt-4 grid gap-4 md:grid-cols-2">
            <label class="block text-sm">
              <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Title</span>
              <input v-model="report.metadata.title" :class="['mt-1', inputClass]" />
            </label>
            <label class="block text-sm">
              <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Date</span>
              <input v-model="report.metadata.report_date" type="date" :class="['mt-1', inputClass]" />
            </label>
            <label class="block text-sm">
              <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Prepared by</span>
              <input v-model="report.metadata.prepared_by" :class="['mt-1', inputClass]" />
            </label>
            <label class="block text-sm">
              <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Status</span>
              <select v-model="report.metadata.status" :class="['mt-1', inputClass]">
                <option value="draft">draft</option>
                <option value="review">review</option>
                <option value="final">final</option>
              </select>
            </label>
            <label class="block text-sm">
              <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Client name</span>
              <input v-model="report.client.name" :class="['mt-1', inputClass]" />
            </label>
            <label class="block text-sm">
              <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Client role</span>
              <input v-model="report.client.role" :class="['mt-1', inputClass]" />
            </label>
            <label class="block text-sm md:col-span-2">
              <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Location address</span>
              <input v-model="report.location.address" :class="['mt-1', inputClass]" />
            </label>
            <label class="block text-sm">
              <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Site name</span>
              <input v-model="report.location.site_name" :class="['mt-1', inputClass]" />
            </label>
            <label class="block text-sm">
              <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Room</span>
              <input v-model="report.location.room" :class="['mt-1', inputClass]" />
            </label>
          </div>
        </div>

        <div class="card p-6">
          <span class="section-eyebrow">Executive summary</span>
          <textarea
            v-model="report.executive_summary"
            rows="4"
            :class="['mt-3 resize-none', inputClass]"
          />
        </div>

        <div class="card p-6">
          <div class="flex items-center justify-between">
            <span class="section-eyebrow">Sections</span>
            <button type="button" class="btn-ghost" @click="addSection">+ section</button>
          </div>
          <div class="mt-4 grid gap-4">
            <div
              v-for="(section, i) in report.sections"
              :key="i"
              class="rounded-xl border border-ink-500/40 bg-ink-900/40 p-4"
            >
              <div class="flex items-center justify-between gap-3">
                <input
                  v-model="section.heading"
                  placeholder="Heading"
                  :class="inputClass"
                />
                <button type="button" class="text-xs text-red-300 hover:underline" @click="removeSection(i)">remove</button>
              </div>
              <textarea
                v-model="section.body"
                rows="3"
                placeholder="Body"
                :class="['mt-3 resize-none', inputClass]"
              />
            </div>
          </div>
        </div>

        <div class="card p-6">
          <div class="flex items-center justify-between">
            <span class="section-eyebrow">Inspection issues</span>
            <button type="button" class="btn-ghost" @click="addIssue">+ issue</button>
          </div>
          <div class="mt-4 grid gap-4">
            <div
              v-for="(issue, i) in report.issues"
              :key="i"
              class="rounded-xl border border-ink-500/40 bg-ink-900/40 p-4"
            >
              <div class="grid gap-3 md:grid-cols-2">
                <label class="block text-sm">
                  <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">ID</span>
                  <input v-model="issue.issue_id" :class="['mt-1', inputClass]" />
                </label>
                <label class="block text-sm">
                  <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Title</span>
                  <input v-model="issue.title" :class="['mt-1', inputClass]" />
                </label>
                <label class="block text-sm md:col-span-2">
                  <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Description</span>
                  <textarea v-model="issue.description" rows="2" :class="['mt-1 resize-none', inputClass]" />
                </label>
                <label class="block text-sm">
                  <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Severity</span>
                  <select v-model="issue.severity" :class="['mt-1', inputClass]">
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                    <option value="critical">critical</option>
                  </select>
                </label>
                <label class="block text-sm">
                  <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Image path</span>
                  <input v-model="issue.image_path" placeholder="src/docs/images/..." :class="['mt-1', inputClass]" />
                </label>
                <label class="block text-sm md:col-span-2">
                  <span class="font-mono text-[10px] uppercase tracking-widest text-fg-dim">Recommendation</span>
                  <textarea v-model="issue.recommendation" rows="2" :class="['mt-1 resize-none', inputClass]" />
                </label>
              </div>
              <button type="button" class="mt-3 text-xs text-red-300 hover:underline" @click="removeIssue(i)">remove issue</button>
            </div>
          </div>
        </div>

        <div class="card p-6">
          <div class="flex items-center justify-between">
            <span class="section-eyebrow">Next steps</span>
            <button type="button" class="btn-ghost" @click="addNextStep">+ step</button>
          </div>
          <div class="mt-4 grid gap-2">
            <div v-for="(_, i) in report.next_steps" :key="i" class="flex items-center gap-3">
              <input v-model="report.next_steps[i]" :class="inputClass" />
              <button type="button" class="text-xs text-red-300 hover:underline" @click="removeNextStep(i)">remove</button>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="!error && loading" class="mt-12 text-center font-mono text-sm text-fg-dim">
        Loading report…
      </div>
    </div>
  </section>
</template>
