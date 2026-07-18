import { useEffect, useState } from 'react'
import { RotateCcw, Timer } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { getMetricsSummary, type MetricsSummary } from '@/lib/api'

const STAGE_LABEL: Record<string, string> = {
  enrich: 'Enrich · Sonnet',
  vector_match: 'Vector match',
  string_match: 'String match',
  dedup: 'Dedup',
  classify: 'Classify · Opus',
}

const STAGE_ORDER = ['enrich', 'vector_match', 'string_match', 'dedup', 'classify']

const STAGE_COLOR: Record<string, string> = {
  enrich: '#6366f1', // indigo (LLM)
  vector_match: '#0ea5e9', // sky
  string_match: '#14b8a6', // teal
  dedup: '#94a3b8', // slate
  classify: '#8b5cf6', // violet (LLM)
}
const color = (s: string) => STAGE_COLOR[s] ?? '#94a3b8'

function fmt(ms?: number | null): string {
  if (ms === null || ms === undefined) return '—'
  return ms >= 1000 ? (ms / 1000).toFixed(1) + 's' : Math.round(ms) + 'ms'
}

function ago(ts: number): string {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-card px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  )
}

// Per-stage time-series (a mini line chart auto-scaled to THIS stage's own range).
function StageTrend({ stage, points }: { stage: string; points: number[] }) {
  const w = 280
  const h = 60
  const pad = 6
  const max = Math.max(...points, 1)
  const min = Math.min(...points)
  const range = max - min || 1
  const n = points.length
  const stepX = n > 1 ? (w - 2 * pad) / (n - 1) : 0
  const xy = points.map(
    (p, i) => [pad + i * stepX, h - pad - ((p - min) / range) * (h - 2 * pad)] as const,
  )
  const path = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ')
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color(stage) }} />
          {STAGE_LABEL[stage] ?? stage}
        </span>
        <span className="text-muted-foreground">
          last <b className="text-foreground">{fmt(points[n - 1])}</b> · {n} runs
        </span>
      </div>
      <div className="relative rounded bg-muted/40">
        <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="block">
          {n > 1 && (
            <path d={path} fill="none" stroke={color(stage)} strokeWidth={2} vectorEffect="non-scaling-stroke" />
          )}
          {xy.map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r={2.2} fill={color(stage)} />
          ))}
        </svg>
        <span className="absolute right-1.5 top-0.5 text-[9px] text-muted-foreground">{fmt(max)}</span>
        <span className="absolute right-1.5 bottom-0.5 text-[9px] text-muted-foreground">{fmt(min)}</span>
      </div>
    </div>
  )
}

export default function Metrics() {
  const [m, setM] = useState<MetricsSummary | null>(null)

  function load() {
    getMetricsSummary().then(setM).catch(() => {})
  }
  useEffect(() => {
    load()
    const id = setInterval(load, 4000) // live-refresh while pipelines run
    return () => clearInterval(id)
  }, [])

  const stages = m
    ? [...m.per_stage].sort((a, b) => STAGE_ORDER.indexOf(a.stage) - STAGE_ORDER.indexOf(b.stage))
    : []
  const maxAvg = Math.max(1, ...stages.map((s) => s.avg_ms))
  const runAvg = stages.reduce((sum, s) => sum + s.avg_ms, 0)
  const slowest = stages.reduce((a, b) => (b.avg_ms > (a?.avg_ms ?? 0) ? b : a), stages[0])
  const recent = m ? [...m.recent].reverse() : [] // oldest → newest (left → right)
  const seriesByStage: Record<string, number[]> = {}
  for (const r of recent) (seriesByStage[r.stage] ??= []).push(r.duration_ms)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Metrics</h1>
          <p className="text-muted-foreground">
            Pipeline stage timings recorded in <code>metrics.db</code> (auto-refreshes).
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load}>
          <RotateCcw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      {(!m || m.total_records === 0) && (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            No metrics yet — run a few items in <b>Part 2 · Pipeline</b> and they'll appear here.
          </CardContent>
        </Card>
      )}

      {m && m.total_records > 0 && (
        <>
          {/* headline stats */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Records" value={String(m.total_records)} />
            <Stat label="Avg per full run" value={fmt(runAvg)} />
            <Stat label="Slowest stage" value={slowest ? STAGE_LABEL[slowest.stage] ?? slowest.stage : '—'} />
            <Stat label="Slowest avg" value={fmt(slowest?.avg_ms)} />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Chart 1: avg time per stage */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Timer className="h-4 w-4" /> Average time per stage
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {stages.map((s) => (
                  <div key={s.stage}>
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span>{STAGE_LABEL[s.stage] ?? s.stage}</span>
                      <span className="text-muted-foreground">
                        <b className="text-foreground">{fmt(s.avg_ms)}</b> avg · {fmt(s.max_ms)} max · {s.count}×
                      </span>
                    </div>
                    <div className="h-3.5 overflow-hidden rounded bg-muted">
                      <div
                        className="h-full rounded"
                        style={{ width: `${(s.avg_ms / maxAvg) * 100}%`, backgroundColor: color(s.stage) }}
                      />
                    </div>
                  </div>
                ))}
                <p className="pt-1 text-[11px] text-muted-foreground">
                  The two LLM stages (Enrich · Sonnet, Classify · Opus) dominate; vector/string/dedup are near-instant.
                </p>
              </CardContent>
            </Card>

            {/* Chart 2: per-stage run time over recent runs (each stage its own y-scale) */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Per-stage run time (time series)</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {STAGE_ORDER.filter((s) => (seriesByStage[s] ?? []).length > 0).map((s) => (
                  <StageTrend key={s} stage={s} points={seriesByStage[s]} />
                ))}
                {STAGE_ORDER.every((s) => !(seriesByStage[s] ?? []).length) && (
                  <p className="text-xs text-muted-foreground">Run items in Part 2 to populate.</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Recent runs table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recent stage runs</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="max-h-[50vh] overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-card text-left text-xs text-muted-foreground">
                    <tr>
                      <th className="px-2 py-1 font-medium">When</th>
                      <th className="px-2 py-1 font-medium">Content</th>
                      <th className="px-2 py-1 font-medium">Stage</th>
                      <th className="px-2 py-1 text-right font-medium">Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {m.recent.map((r, i) => (
                      <tr key={i} className="border-t">
                        <td className="px-2 py-1.5 text-muted-foreground">{ago(r.at)}</td>
                        <td className="px-2 py-1.5 font-mono text-xs">{r.content_id}</td>
                        <td className="px-2 py-1.5">
                          <span className="inline-flex items-center gap-1.5">
                            <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: color(r.stage) }} />
                            {STAGE_LABEL[r.stage] ?? r.stage}
                          </span>
                        </td>
                        <td className="px-2 py-1.5 text-right font-medium tabular-nums">{fmt(r.duration_ms)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
