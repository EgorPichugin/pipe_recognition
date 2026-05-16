export interface ReportIssue {
  issue_id: string
  title: string
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  recommendation: string
  image_path?: string | null
}

export interface ReportSection {
  heading: string
  body: string
}

export interface ReportSchema {
  metadata: {
    report_id: string
    title: string
    report_date: string
    prepared_by: string
    status: 'draft' | 'review' | 'final'
  }
  client: { name: string; role: string; email?: string | null }
  location: { site_name: string; address: string; room?: string | null }
  executive_summary: string
  sections: ReportSection[]
  issues: ReportIssue[]
  next_steps: string[]
}

export interface PhotoRecord {
  id: string
  latitude: string
  longitude: string
  image_name: string
  category: string
  status: string
}

export interface EvaluationFinding {
  severity: 'info' | 'low' | 'medium' | 'high'
  target: string
  message: string
}

export interface ReportEvaluation {
  overall_score: number
  summary: string
  findings: EvaluationFinding[]
  recommendations: string[]
}

export function useReportApi() {
  const config = useRuntimeConfig()
  const base = config.public.apiBase || ''

  const getSchema = () => $fetch<ReportSchema>(`${base}/report/schema`)

  const saveSchema = (report: ReportSchema) =>
    $fetch<ReportSchema>(`${base}/report/schema`, {
      method: 'PUT',
      body: report,
    })

  const resetReport = () => $fetch<ReportSchema>(`${base}/report/reset`, { method: 'POST' })

  const generateFromPhotos = (context?: string) =>
    $fetch<ReportSchema>(`${base}/report/generate`, {
      method: 'POST',
      body: { context: context || '' },
    })

  const evaluateReport = () =>
    $fetch<ReportEvaluation>(`${base}/report/evaluate`, { method: 'POST' })

  const downloadPreview = async (): Promise<Blob> =>
    $fetch<Blob>(`${base}/report/preview`, { responseType: 'blob' })

  const downloadPreviewPdf = async (): Promise<Blob> =>
    $fetch<Blob>(`${base}/report/preview.pdf`, { responseType: 'blob' })

  const listPhotos = () =>
    $fetch<{ photos: PhotoRecord[] }>(`${base}/report/photos`)

  const exportPhotosCsv = async (): Promise<Blob> =>
    $fetch<Blob>(`${base}/report/photos/export`, { responseType: 'blob' })

  const applyChange = async (
    requested_changes: string,
  ): Promise<{ blob: Blob; headers: Headers }> => {
    const res = await fetch(`${base}/report/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requested_changes }),
    })
    if (!res.ok) {
      const detail = await res.text().catch(() => res.statusText)
      throw new Error(`${res.status}: ${detail}`)
    }
    const blob = await res.blob()
    return { blob, headers: res.headers }
  }

  return {
    getSchema,
    saveSchema,
    resetReport,
    generateFromPhotos,
    evaluateReport,
    downloadPreview,
    downloadPreviewPdf,
    listPhotos,
    exportPhotosCsv,
    applyChange,
  }
}
