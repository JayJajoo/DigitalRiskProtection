import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Check,
  ChevronDown,
  Circle,
  ImageIcon,
  Loader2,
  Pause,
  Play,
  RotateCcw,
  ShieldAlert,
  StepForward,
  X,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  contentImageUrl,
  getContentList,
  getCustomer,
  getMetricsSummary,
  startPipeline,
  stepPipeline,
  type ContentSummary,
  type CustomerDetail,
  type MetricsSummary,
  type PipelineRun,
  type PipelineStage,
} from '@/lib/api'

function fmt(ms?: number | null): string {
  if (ms === null || ms === undefined) return '—'
  return ms >= 1000 ? (ms / 1000).toFixed(1) + 's' : Math.round(ms) + 'ms'
}

const STAGE_LABEL: Record<string, string> = {
  enrich: 'Enrich · Sonnet',
  vector_match: 'Vector match',
  string_match: 'String match',
  dedup: 'Dedup',
  classify: 'Classify · Opus',
}

const THREAT_LABELS = new Set([
  'phishing', 'scam', 'impersonation', 'doxxing', 'physical_threat',
  'extortion', 'money_flipping', 'data_leak', 'online_threat',
])

function sevClass(sev: string): string {
  return (
    {
      high: 'bg-red-100 text-red-700 border-red-200',
      medium: 'bg-orange-100 text-orange-700 border-orange-200',
      low: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    }[sev] ?? 'bg-muted text-muted-foreground border-transparent'
  )
}

function labelClass(label?: string | null): string {
  if (!label) return 'bg-muted text-muted-foreground'
  if (label === 'benign') return 'bg-green-100 text-green-700'
  if (label === 'vague') return 'bg-slate-100 text-slate-600'
  if (THREAT_LABELS.has(label)) return 'bg-red-100 text-red-700'
  return 'bg-secondary text-secondary-foreground'
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function Json({ data }: { data: any }) {
  return (
    <pre className="max-h-80 overflow-auto rounded bg-muted/50 p-2 text-[11px] leading-relaxed">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

function StageIcon({ status }: { status: string }) {
  if (status === 'done') return <Check className="h-3.5 w-3.5 text-green-600" />
  if (status === 'running') return <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
  if (status === 'error') return <X className="h-3.5 w-3.5 text-destructive" />
  return <Circle className="h-3 w-3 text-muted-foreground/50" />
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function MiniList({ items }: { items: any[] }) {
  if (!items?.length) return <p className="text-xs text-muted-foreground">none</p>
  return (
    <div className="space-y-1">
      {items.map((c, i) => (
        <div key={i} className="flex items-center justify-between gap-2 rounded bg-muted/40 px-2 py-1 text-xs">
          <span className="truncate">
            <span className="font-medium">{c.customer_name}</span>
            <span className="ml-1 text-muted-foreground">· {c.asset_type}={c.asset_value}</span>
          </span>
          <span className="shrink-0 font-mono text-muted-foreground">{c.score}</span>
        </div>
      ))}
    </div>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function RollupItem({ r }: { r: any }) {
  const [open, setOpen] = useState(false)
  const [detail, setDetail] = useState<CustomerDetail | null>(null)
  async function toggle() {
    const next = !open
    setOpen(next)
    if (next && !detail) {
      try {
        setDetail(await getCustomer(r.customer_id))
      } catch {
        /* ignore */
      }
    }
  }
  return (
    <div className="overflow-hidden rounded border">
      <button
        onClick={toggle}
        className={cn('flex w-full items-center justify-between gap-2 px-2 py-1.5 text-xs', sevClass(r.max_severity))}
      >
        <span className="font-medium">{r.customer_name}</span>
        <span className="flex items-center gap-2">
          <span className="uppercase">{r.max_severity}</span>
          <span className="opacity-70">· {r.threat_asset_count} threat asset(s)</span>
          <ChevronDown className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-180')} />
        </span>
      </button>
      {open && (
        <div className="space-y-1 border-t bg-card p-2 text-xs">
          {r.summary && <p className="mb-1 text-muted-foreground">{r.summary}</p>}
          {!detail && <p className="text-muted-foreground">loading assets…</p>}
          {detail?.assets.map((a) => (
            <div key={a.id} className="flex flex-wrap items-center gap-1">
              <span className="rounded bg-secondary px-1 py-0.5 text-[10px]">{a.type}</span>
              <span className="font-mono">{a.value}</span>
              {a.concerns.map((c, i) => (
                <span key={i} className="rounded bg-destructive/10 px-1 py-0.5 text-[10px] text-destructive">
                  {c.type}
                </span>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StageOutput({ stage }: { stage: PipelineStage }) {
  const out = stage.output
  if (!out) return <p className="text-xs text-muted-foreground">—</p>
  if (out.error) return <p className="text-xs text-destructive">Error: {out.error}</p>

  if (stage.name === 'enrich') {
    const risks = Object.entries(out.risk_signals || {}).filter(([, v]) => v).map(([k]) => k)
    return (
      <div className="space-y-2 text-xs">
        <p><span className="text-muted-foreground">summary:</span> {out.summary}</p>
        <p><span className="text-muted-foreground">languages:</span> {(out.languages || []).join(', ') || '—'}</p>
        <div className="flex flex-wrap gap-1">
          {risks.length ? risks.map((r) => (
            <span key={r} className="rounded bg-red-100 px-1.5 py-0.5 text-red-700">{r}</span>
          )) : <span className="text-muted-foreground">no risk signals</span>}
        </div>
        {out.image_analysis && (
          <p className="text-muted-foreground">
            image: knife={String(out.image_analysis.weapons?.knife)} · money={String(out.image_analysis.money_signs)} · objects={(out.image_analysis.objects || []).join(', ')}
          </p>
        )}
        <details><summary className="cursor-pointer text-muted-foreground">raw JSON</summary><Json data={out} /></details>
      </div>
    )
  }

  if (stage.name === 'vector_match') return <MiniList items={out.candidates} />

  if (stage.name === 'string_match') {
    return (
      <div className="space-y-2">
        <p className="text-xs font-medium">exact ({out.exact?.length || 0})</p>
        <MiniList items={out.exact} />
        <p className="text-xs font-medium">fuzzy ({out.fuzzy?.length || 0})</p>
        <MiniList items={out.fuzzy} />
      </div>
    )
  }

  if (stage.name === 'dedup') {
    return (
      <div className="space-y-1">
        {(out.matches || []).map((m: any, i: number) => (
          <div key={i} className="flex items-center justify-between gap-2 rounded bg-muted/40 px-2 py-1 text-xs">
            <span className="truncate">
              <span className="font-medium">{m.customer_name}</span>
              <span className="ml-1 text-muted-foreground">· {m.asset_type}={m.asset_value}</span>
            </span>
            <span className="flex shrink-0 items-center gap-1">
              {(m.matched_by || []).map((s: string) => (
                <span key={s} className="rounded bg-secondary px-1 text-[10px]">{s}</span>
              ))}
              <span className="font-mono text-muted-foreground">{m.match_score}</span>
            </span>
          </div>
        ))}
      </div>
    )
  }

  if (stage.name === 'classify') {
    const verdicts = out.asset_verdicts || []
    const threats = verdicts.filter((v: any) => v.is_threat)
    const cleared = verdicts.length - threats.length
    const meta = stage.meta
    return (
      <div className="space-y-3">
        {meta?.companies != null && (
          <p className="rounded bg-muted/40 px-2 py-1 text-xs text-muted-foreground">
            ⏱ {meta.companies} company LLM call(s) · <b>avg {fmt(meta.avg_company_ms)}/company</b> · total
            LLM {fmt(meta.total_llm_ms)}
          </p>
        )}
        <div className="space-y-1">
          {threats.length === 0 && <p className="text-xs text-green-700">No threats — all {verdicts.length} candidates cleared.</p>}
          {threats.map((v: any, i: number) => (
            <div key={i} className={cn('rounded border p-2 text-xs', sevClass(v.severity))}>
              <div className="flex items-center justify-between">
                <span className="font-semibold">{v.customer_name} · {v.asset_type}={v.asset_value}</span>
                <span className="rounded bg-white/60 px-1.5 py-0.5 text-[10px] font-bold uppercase">{v.severity}</span>
              </div>
              <p className="mt-1">{v.reason}</p>
              <p className="mt-0.5 opacity-70">type: {v.threat_type} · confidence {v.confidence}</p>
            </div>
          ))}
          {cleared > 0 && <p className="text-xs text-muted-foreground">+ {cleared} candidate(s) cleared as non-threats.</p>}
        </div>
        {out.company_rollup?.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium">
              Company rollup{' '}
              <span className="font-normal text-muted-foreground">(click a company for its assets &amp; concerns)</span>
            </p>
            <div className="space-y-1">
              {out.company_rollup.map((r: any, i: number) => (
                <RollupItem key={i} r={r} />
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }
  return <Json data={out} />
}

function StageInput({ stage }: { stage: PipelineStage }) {
  const inp = stage.input
  if (!inp) return <p className="text-xs text-muted-foreground">—</p>
  if (stage.name === 'enrich')
    return <p className="text-xs">{inp.text || '(image only)'}{inp.image_path ? ` · image: ${inp.image_path}` : ''}</p>
  if (stage.name === 'vector_match')
    return (
      <div className="text-xs">
        <p className="text-muted-foreground">top_n={inp.top_n} · threshold={inp.threshold}</p>
        <p className="mt-1 line-clamp-4 text-muted-foreground">{inp.query_text}</p>
      </div>
    )
  if (stage.name === 'string_match')
    return (
      <div className="space-y-1 text-xs">
        {['id_terms', 'person_terms', 'org_terms', 'kw_terms'].map((k) => (
          <p key={k}><span className="text-muted-foreground">{k}:</span> {(inp[k] || []).join(', ') || '—'}</p>
        ))}
      </div>
    )
  return <Json data={inp} />
}

export default function Part2Pipeline() {
  const [content, setContent] = useState<ContentSummary[]>([])
  const [filter, setFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [labelFilter, setLabelFilter] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [run, setRun] = useState<PipelineRun | null>(null)
  const [viewIndex, setViewIndex] = useState(-1) // -1 = content, 0..4 = stage
  const [playing, setPlaying] = useState(false)
  const [busy, setBusy] = useState(false)
  const [processingIndex, setProcessingIndex] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null)
  const busyRef = useRef(false)
  const procStartRef = useRef(0)

  function refreshMetrics() {
    getMetricsSummary().then(setMetrics).catch(() => {})
  }

  useEffect(() => {
    getContentList().then(setContent).catch(console.error)
    refreshMetrics()
  }, [])

  // live timer while a stage (LLM call) is processing
  useEffect(() => {
    if (processingIndex === null) return
    procStartRef.current = performance.now()
    setElapsed(0)
    const id = setInterval(() => setElapsed(performance.now() - procStartRef.current), 100)
    return () => clearInterval(id)
  }, [processingIndex])

  const types = useMemo(
    () => Array.from(new Set(content.map((c) => c.type))).sort(),
    [content],
  )
  const labels = useMemo(
    () => Array.from(new Set(content.map((c) => c.label).filter(Boolean))).sort() as string[],
    [content],
  )
  const filtered = useMemo(() => {
    const q = filter.toLowerCase()
    return content.filter(
      (c) =>
        (!q || c.id.includes(q) || (c.label || '').includes(q) || c.text_preview.toLowerCase().includes(q)) &&
        (!typeFilter || c.type === typeFilter) &&
        (!labelFilter || c.label === labelFilter),
    )
  }, [content, filter, typeFilter, labelFilter])

  async function select(id: string) {
    setSelectedId(id)
    setPlaying(false)
    setViewIndex(-1)
    const r = await startPipeline(id)
    setRun(r)
  }

  async function stepOnce() {
    if (!run || run.done || busyRef.current) return
    const runningIndex = run.cursor
    busyRef.current = true
    setBusy(true)
    setProcessingIndex(runningIndex)
    setViewIndex(runningIndex) // jump to the stage being processed
    try {
      const updated = await stepPipeline(run.run_id)
      setRun(updated)
      setViewIndex(updated.cursor - 1) // show the stage that just finished
      refreshMetrics()
      if (updated.done) setPlaying(false)
    } catch {
      setPlaying(false)
    } finally {
      busyRef.current = false
      setBusy(false)
      setProcessingIndex(null)
    }
  }

  // auto-advance while playing
  useEffect(() => {
    if (!playing || !run || run.done || busy) return
    const t = setTimeout(stepOnce, 900)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, run, busy])

  const stageChips = run ? ['content', ...run.stages.map((s) => s.name)] : []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Part 2 · Enrichment &amp; Threat Classification</h1>
        <p className="text-muted-foreground">
          Play the pipeline stage-by-stage — inspect the input and output of each component,
          pause, step, and replay.
        </p>
      </div>

      {metrics && metrics.total_records > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border bg-card px-3 py-2 text-xs">
          <span className="font-medium text-muted-foreground">Saved timings (avg):</span>
          {metrics.per_stage.map((s) => (
            <span key={s.stage} className="rounded bg-muted px-2 py-0.5">
              {STAGE_LABEL[s.stage] ?? s.stage}: <b>{fmt(s.avg_ms)}</b>
            </span>
          ))}
          <span className="ml-auto text-muted-foreground">{metrics.total_records} records in metrics.db</span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[300px_1fr]">
        {/* content queue */}
        <Card className="h-fit">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Content ({filtered.length})</CardTitle>
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="search…"
              className="mt-2 w-full rounded-md border bg-background px-2 py-1 text-sm"
            />
            <div className="mt-2 flex gap-2">
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="w-1/2 rounded-md border bg-background px-2 py-1 text-xs"
              >
                <option value="">all types</option>
                {types.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <select
                value={labelFilter}
                onChange={(e) => setLabelFilter(e.target.value)}
                className="w-1/2 rounded-md border bg-background px-2 py-1 text-xs"
              >
                <option value="">all labels</option>
                {labels.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
            {(typeFilter || labelFilter || filter) && (
              <button
                onClick={() => {
                  setFilter('')
                  setTypeFilter('')
                  setLabelFilter('')
                }}
                className="mt-1 text-[11px] text-muted-foreground hover:text-foreground"
              >
                clear filters
              </button>
            )}
          </CardHeader>
          <CardContent className="max-h-[68vh] space-y-1 overflow-auto pr-2">
            {filtered.map((c) => (
              <button
                key={c.id}
                onClick={() => select(c.id)}
                className={cn(
                  'w-full rounded-md border px-2.5 py-2 text-left text-xs transition-colors',
                  selectedId === c.id ? 'border-primary bg-accent' : 'border-transparent hover:bg-accent',
                )}
              >
                <div className="flex items-center gap-1.5">
                  <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', labelClass(c.label))}>
                    {c.label || 'n/a'}
                  </span>
                  {c.has_image && <ImageIcon className="h-3 w-3 text-muted-foreground" />}
                  <span className="ml-auto text-[10px] text-muted-foreground">{c.id}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-muted-foreground">{c.text_preview || '(image only)'}</p>
              </button>
            ))}
          </CardContent>
        </Card>

        {/* runner */}
        <div className="space-y-4">
          {!run && (
            <Card>
              <CardContent className="py-10 text-center text-muted-foreground">
                Select a content item to run the pipeline.
              </CardContent>
            </Card>
          )}

          {run && (
            <>
              {/* controls */}
              <Card>
                <CardContent className="flex flex-wrap items-center gap-2 py-3">
                  {playing ? (
                    <Button size="sm" variant="secondary" onClick={() => setPlaying(false)}>
                      <Pause className="h-4 w-4" /> Pause
                    </Button>
                  ) : (
                    <Button size="sm" onClick={() => setPlaying(true)} disabled={run.done}>
                      <Play className="h-4 w-4" /> Play
                    </Button>
                  )}
                  <Button size="sm" variant="outline" onClick={stepOnce} disabled={playing || busy || run.done}>
                    <StepForward className="h-4 w-4" /> Step
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => select(run.content_id)} disabled={busy}>
                    <RotateCcw className="h-4 w-4" /> Replay
                  </Button>
                  <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
                    {busy && processingIndex !== null ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                        Processing {STAGE_LABEL[run.stages[processingIndex].name]}… {fmt(elapsed)}
                      </>
                    ) : (
                      `stage ${Math.min(run.cursor, run.stages.length)}/${run.stages.length}${run.done ? ' · complete' : ''}`
                    )}
                  </span>
                </CardContent>
              </Card>

              {/* stage timeline */}
              <div className="flex flex-wrap items-center gap-1">
                {stageChips.map((name, i) => {
                  const idx = i - 1 // content = -1
                  const status =
                    idx < 0 ? 'done' : processingIndex === idx ? 'running' : run.stages[idx].status
                  return (
                    <button
                      key={name}
                      onClick={() => setViewIndex(idx)}
                      className={cn(
                        'flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs transition-colors',
                        viewIndex === idx ? 'border-primary bg-accent' : 'hover:bg-accent',
                      )}
                    >
                      {idx < 0 ? <Circle className="h-3 w-3 text-primary" /> : <StageIcon status={status} />}
                      {idx < 0 ? 'Content' : STAGE_LABEL[name]}
                      {idx >= 0 && run.stages[idx].status === 'done' && run.stages[idx].duration_ms != null && (
                        <span className="text-[10px] text-muted-foreground">{fmt(run.stages[idx].duration_ms)}</span>
                      )}
                      {i < stageChips.length - 1 && <span className="text-muted-foreground/40">›</span>}
                    </button>
                  )
                })}
              </div>

              {/* content view or stage input/output */}
              {viewIndex < 0 ? (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <span className={cn('rounded px-1.5 py-0.5 text-xs', labelClass(run.content.label))}>
                        {run.content.label || 'n/a'}
                      </span>
                      content input · {run.content.type}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {run.content.text && <p className="text-sm">{run.content.text}</p>}
                    {run.content.has_image && (
                      <img
                        src={contentImageUrl(run.content.id)}
                        alt="content"
                        className="max-h-64 rounded border"
                      />
                    )}
                  </CardContent>
                </Card>
              ) : (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm text-muted-foreground">
                        Input → {STAGE_LABEL[run.stages[viewIndex].name]}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <StageInput stage={run.stages[viewIndex]} />
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm text-muted-foreground">Output</CardTitle>
                      <span className="flex items-center gap-2 text-xs text-muted-foreground">
                        {run.stages[viewIndex].status === 'done' &&
                          run.stages[viewIndex].duration_ms != null && (
                            <span>⏱ {fmt(run.stages[viewIndex].duration_ms)}</span>
                          )}
                        <StageIcon status={run.stages[viewIndex].status} />
                      </span>
                    </CardHeader>
                    <CardContent>
                      {processingIndex === viewIndex ? (
                        <p className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Loader2 className="h-4 w-4 animate-spin text-primary" />
                          Processing {STAGE_LABEL[run.stages[viewIndex].name]}… <span className="font-mono">{fmt(elapsed)}</span>
                        </p>
                      ) : run.stages[viewIndex].status === 'pending' ? (
                        <p className="text-xs text-muted-foreground">not run yet</p>
                      ) : run.stages[viewIndex].status === 'running' ? (
                        <p className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Loader2 className="h-4 w-4 animate-spin" /> working…
                        </p>
                      ) : (
                        <StageOutput stage={run.stages[viewIndex]} />
                      )}
                    </CardContent>
                  </Card>
                </div>
              )}

              {/* final verdict banner */}
              {run.done && run.stages[4].output && !run.stages[4].output.error && (
                <Card className="border-primary/40">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <ShieldAlert className="h-4 w-4 text-primary" /> Final verdict
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <StageOutput stage={run.stages[4]} />
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
