import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Check,
  ChevronRight,
  Database,
  Loader2,
  Lock,
  Plus,
  RotateCcw,
  Search,
  ShieldAlert,
  Shuffle,
  Trash2,
  X,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  createCustomer,
  deleteCustomer,
  getCustomer,
  getCustomers,
  getStoresStatus,
  ingestAll,
  ingestStreamUrl,
  resetIngest,
  suggestCustomer,
  type CustomerDetail,
  type CustomerSummary,
  type DraftAsset,
  type DraftCustomer,
  type StoresStatus,
} from '@/lib/api'

const ASSET_TYPES = [
  'email', 'phone', 'address', 'domain', 'website', 'social_handle',
  'brand', 'executive', 'app', 'credit_card', 'bank_account', 'other',
]

interface LogEntry {
  event: string
  [k: string]: unknown
}

function describe(e: LogEntry): string {
  switch (e.event) {
    case 'start':
      return `Starting ingest — ${e.total_assets} asset(s)`
    case 'embedding':
      return String(e.message ?? 'Embedding…')
    case 'embedded':
      return `Embedded ${e.count} asset(s) via OpenAI`
    case 'vectors_stored':
      return `Stored ${e.count} vector(s) in Chroma`
    case 'indexed':
      return `Indexed ${e.count} doc(s) in Elasticsearch`
    case 'asset_done':
      return `✓ ${e.asset_type}: ${e.asset_value}`
    case 'complete':
      return `Done — ${e.assets_indexed} asset(s) · ES total ${e.es_total} · Chroma total ${e.chroma_total}`
    case 'error':
      return `Error: ${e.message}`
    default:
      return e.event
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function LogLine({ e }: { e: LogEntry }) {
  const d = e as any
  if (e.event === 'asset_done' && d.embedding) {
    return (
      <details className="text-green-700">
        <summary className="cursor-pointer">{describe(e)}</summary>
        <div className="ml-3 mt-1 space-y-1 text-foreground/80">
          <div>
            <span className="text-muted-foreground">OpenAI embedding:</span> {d.embedding.model} · dim{' '}
            {d.embedding.dim} · [{(d.embedding.preview || []).join(', ')} …]
          </div>
          <div className="text-muted-foreground">
            → Chroma (vector DB) · collection "{d.chroma.collection}" · id {d.chroma.id}
          </div>
          <pre className="overflow-auto rounded bg-background p-1">{JSON.stringify(d.chroma.metadata, null, 2)}</pre>
          <div className="text-muted-foreground">
            → Elasticsearch · index "{d.elasticsearch.index}" · id {d.elasticsearch.id}
          </div>
          <pre className="overflow-auto rounded bg-background p-1">
            {JSON.stringify(d.elasticsearch.document, null, 2)}
          </pre>
        </div>
      </details>
    )
  }
  return (
    <div
      className={cn(
        e.event === 'complete' && 'font-semibold text-green-700',
        e.event === 'error' && 'font-semibold text-destructive',
        e.event === 'asset_done' && 'text-green-700',
      )}
    >
      {describe(e)}
    </div>
  )
}

function Pill({ label, value, ok }: { label: string; value: string | number; ok?: boolean }) {
  return (
    <div className="flex items-center gap-1.5 rounded-md border bg-card px-2.5 py-1 text-xs">
      <span className={cn('h-2 w-2 rounded-full', ok ? 'bg-green-500' : 'bg-muted-foreground/40')} />
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  )
}

export default function Part1Ingest() {
  const [customers, setCustomers] = useState<CustomerSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<CustomerDetail | null>(null)
  const [stores, setStores] = useState<StoresStatus | null>(null)
  const [ingestingId, setIngestingId] = useState<string | null>(null)
  const [log, setLog] = useState<LogEntry[]>([])
  const [doneAssets, setDoneAssets] = useState<Set<string>>(new Set())
  const [bulk, setBulk] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [draft, setDraft] = useState<DraftCustomer | null>(null)
  const [saving, setSaving] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const esRef = useRef<EventSource | null>(null)

  const activeIndex = useMemo(() => customers.findIndex((c) => !c.ingested), [customers])

  async function refresh(selectAfter?: string) {
    const [cs, ss] = await Promise.all([getCustomers(), getStoresStatus()])
    setCustomers(cs)
    setStores(ss)
    const nextId = selectAfter ?? selectedId ?? cs.find((c) => !c.ingested)?.id ?? cs[0]?.id ?? null
    if (nextId) {
      setSelectedId(nextId)
      setDetail(await getCustomer(nextId))
    }
  }

  useEffect(() => {
    refresh().catch(console.error)
    return () => esRef.current?.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function select(id: string) {
    if (ingestingId) return
    setSelectedId(id)
    setDetail(await getCustomer(id))
  }

  function ingest(id: string) {
    if (ingestingId) return
    setIngestingId(id)
    setLog([])
    setDoneAssets(new Set())
    const es = new EventSource(ingestStreamUrl(id))
    esRef.current = es
    es.onmessage = (msg) => {
      const e: LogEntry = JSON.parse(msg.data)
      setLog((prev) => [...prev, e])
      if (e.event === 'asset_done') {
        setDoneAssets((prev) => new Set(prev).add(String(e.asset_id)))
      }
      if (e.event === 'complete') {
        es.close()
        setIngestingId(null)
        // advance to the next un-ingested customer
        getCustomers().then((cs) => {
          setCustomers(cs)
          getStoresStatus().then(setStores)
          const next = cs.find((c) => !c.ingested)
          if (next) select(next.id)
        })
      }
      if (e.event === 'error') {
        es.close()
        setIngestingId(null)
      }
    }
    es.onerror = () => {
      es.close()
      setIngestingId(null)
      setLog((prev) => [...prev, { event: 'error', message: 'stream disconnected' }])
    }
  }

  async function onReset() {
    if (ingestingId || bulk) return
    await resetIngest()
    setLog([])
    setDoneAssets(new Set())
    await refresh(customers[0]?.id)
  }

  async function onIngestAll() {
    if (ingestingId || bulk) return
    setBulk(true)
    try {
      await ingestAll()
      await refresh()
    } finally {
      setBulk(false)
    }
  }

  async function onDelete(c: CustomerSummary) {
    if (ingestingId || bulk) return
    if (!window.confirm(`Delete "${c.name}" and remove its assets from Chroma + Elasticsearch?`)) return
    try {
      await deleteCustomer(c.id)
      if (selectedId === c.id) {
        setSelectedId(null)
        setDetail(null)
      }
      await refresh()
    } catch (err) {
      console.error(err)
    }
  }

  // ── New customer form ──
  async function openNew() {
    setShowNew(true)
    setCreateError(null)
    try {
      setDraft(await suggestCustomer())
    } catch {
      setDraft({ name: '', type: 'company', industry: '', protect_summary: '', assets: [] })
    }
  }
  async function randomize() {
    try {
      setDraft(await suggestCustomer())
    } catch {
      /* ignore */
    }
  }
  function patchDraft(patch: Partial<DraftCustomer>) {
    setDraft((d) => (d ? { ...d, ...patch } : d))
  }
  function patchAsset(i: number, patch: Partial<DraftAsset>) {
    setDraft((d) =>
      d ? { ...d, assets: d.assets.map((a, idx) => (idx === i ? { ...a, ...patch } : a)) } : d,
    )
  }
  function addAsset() {
    setDraft((d) =>
      d ? { ...d, assets: [...d.assets, { id: 'new', type: 'domain', value: '', concerns: [] }] } : d,
    )
  }
  function removeAsset(i: number) {
    setDraft((d) => (d ? { ...d, assets: d.assets.filter((_, idx) => idx !== i) } : d))
  }
  async function addNew() {
    if (!draft) return
    setSaving(true)
    setCreateError(null)
    try {
      await createCustomer(draft)
      setShowNew(false)
      setDraft(null)
      await refresh()
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  const ingestedCount = customers.filter((c) => c.ingested).length

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Part 1 · Asset Data Lake &amp; Ingestion</h1>
          <p className="text-muted-foreground">
            Ingest one customer at a time — each asset is embedded into Chroma and indexed in
            Elasticsearch.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Pill label="Ingested" value={`${ingestedCount}/${customers.length}`} ok={ingestedCount > 0} />
          <Pill label="ES assets" value={stores?.elasticsearch.assets_indexed ?? 0} ok={stores?.elasticsearch.up} />
          <Pill label="Chroma vectors" value={stores?.chroma.vectors ?? 0} ok={stores?.chroma.up} />
          <Button
            size="sm"
            onClick={openNew}
            disabled={!!ingestingId || bulk}
            title="Create a new customer — the form is pre-filled with a random fake company; edit anything or Randomize, then Add to embed + index it into the stores."
          >
            <Plus className="h-4 w-4" /> New customer
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={onIngestAll}
            disabled={!!ingestingId || bulk}
            title="Embed & index ALL customers at once: each asset → OpenAI embedding → Chroma (vectors) + Elasticsearch (search index). The bulk version of clicking Ingest on every customer. Needed so Part 2 matching has data."
          >
            {bulk ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
            Ingest all
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onReset}
            disabled={!!ingestingId || bulk}
            title="Wipe the stores: clears the Elasticsearch index + Chroma collection back to 0 and resets which customers are marked ingested — so you can replay ingestion from scratch. Does NOT delete any source data files."
          >
            <RotateCcw className="h-4 w-4" /> Reset
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
        {/* Customer list (sequential) */}
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="text-base">Customers</CardTitle>
          </CardHeader>
          <CardContent className="max-h-[70vh] space-y-1 overflow-auto pr-2">
            {customers.map((c, i) => {
              const done = c.ingested
              const active = !done && i === activeIndex
              const locked = !done && !active
              return (
                <div
                  key={c.id}
                  className={cn(
                    'flex items-center gap-1 rounded-md border transition-colors',
                    selectedId === c.id ? 'border-primary bg-accent' : 'border-transparent hover:bg-accent',
                    locked && 'opacity-45',
                  )}
                >
                  <button
                    onClick={() => !locked && select(c.id)}
                    disabled={locked || !!ingestingId}
                    className="flex flex-1 items-center gap-2 truncate px-3 py-2 text-left text-sm"
                  >
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center">
                      {done ? (
                        <Check className="h-4 w-4 text-green-600" />
                      ) : ingestingId === c.id ? (
                        <Loader2 className="h-4 w-4 animate-spin text-primary" />
                      ) : active ? (
                        <ChevronRight className="h-4 w-4 text-primary" />
                      ) : (
                        <Lock className="h-3.5 w-3.5 text-muted-foreground" />
                      )}
                    </span>
                    <span className="flex-1 truncate">
                      <span className="font-medium">{c.name}</span>
                      <span className="ml-1 text-xs text-muted-foreground">· {c.type}</span>
                    </span>
                    <span className="text-xs text-muted-foreground">{c.asset_count}</span>
                  </button>
                  <button
                    onClick={() => onDelete(c)}
                    disabled={!!ingestingId || bulk}
                    title="Delete this customer and remove its assets from Chroma + Elasticsearch"
                    className="mr-1 shrink-0 rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-40"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              )
            })}
          </CardContent>
        </Card>

        {/* Selected customer detail + ingest */}
        <div className="space-y-6">
          {detail && (
            <Card>
              <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
                <div>
                  <CardTitle>{detail.name}</CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {detail.type}
                    {detail.industry ? ` · ${detail.industry}` : ''}
                  </p>
                  {detail.description && (
                    <p className="mt-2 max-w-2xl text-sm">{detail.description}</p>
                  )}
                  {detail.protect_summary && (
                    <p className="mt-1 max-w-2xl text-xs text-muted-foreground">
                      <span className="font-medium">Protects:</span> {detail.protect_summary}
                    </p>
                  )}
                </div>
                <Button
                  onClick={() => ingest(detail.id)}
                  disabled={
                    ingestingId !== null ||
                    bulk ||
                    (!detail.ingested && customers[activeIndex]?.id !== detail.id)
                  }
                  title={
                    detail.ingested
                      ? 'Re-run ingestion for this customer to watch the live log (embedding + Chroma + Elasticsearch records). Idempotent.'
                      : 'Ingest this customer — embed + index each asset, with a live log.'
                  }
                >
                  {ingestingId === detail.id ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" /> Ingesting…
                    </>
                  ) : detail.ingested ? (
                    <>
                      <RotateCcw className="h-4 w-4" /> Re-ingest
                    </>
                  ) : (
                    <>
                      <Database className="h-4 w-4" /> Ingest customer
                    </>
                  )}
                </Button>
              </CardHeader>
              <CardContent>
                <div className="overflow-hidden rounded-md border">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                      <tr>
                        <th className="px-3 py-2 font-medium">Type</th>
                        <th className="px-3 py-2 font-medium">Value</th>
                        <th className="px-3 py-2 font-medium">Concerns</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.assets.map((a) => (
                        <tr key={a.id} className={cn('border-t', doneAssets.has(a.id) && 'bg-green-50')}>
                          <td className="px-3 py-2 align-top">
                            <span className="rounded bg-secondary px-1.5 py-0.5 text-xs">{a.type}</span>
                          </td>
                          <td className="px-3 py-2 align-top font-mono text-xs">
                            <span className="inline-flex items-center gap-1">
                              {doneAssets.has(a.id) && <Check className="h-3 w-3 text-green-600" />}
                              {a.value}
                            </span>
                          </td>
                          <td className="px-3 py-2 align-top">
                            <div className="flex flex-wrap gap-1">
                              {a.concerns.map((c, i) => (
                                <span
                                  key={i}
                                  className="inline-flex items-center gap-1 rounded bg-destructive/10 px-1.5 py-0.5 text-xs text-destructive"
                                >
                                  <ShieldAlert className="h-3 w-3" />
                                  {c.type}
                                </span>
                              ))}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Live ingest log */}
          {(ingestingId || log.length > 0) && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Search className="h-4 w-4" /> Ingestion progress
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="max-h-96 space-y-1 overflow-auto rounded-md bg-muted/40 p-3 font-mono text-xs">
                  {log.map((e, i) => (
                    <LogLine key={i} e={e} />
                  ))}
                  {ingestingId && <div className="animate-pulse text-muted-foreground">…</div>}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* New customer modal */}
      {showNew && draft && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-auto bg-black/40 p-4">
          <Card className="mt-8 w-full max-w-2xl">
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle className="text-base">New customer</CardTitle>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" onClick={randomize} title="Pre-fill with a different random company">
                  <Shuffle className="h-4 w-4" /> Randomize
                </Button>
                <button
                  onClick={() => {
                    setShowNew(false)
                    setDraft(null)
                  }}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <label className="text-xs text-muted-foreground">
                  Name
                  <input
                    value={draft.name}
                    onChange={(e) => patchDraft({ name: e.target.value })}
                    className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm text-foreground"
                  />
                </label>
                <label className="text-xs text-muted-foreground">
                  Type
                  <select
                    value={draft.type}
                    onChange={(e) => patchDraft({ type: e.target.value })}
                    className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm text-foreground"
                  >
                    <option value="company">company</option>
                    <option value="person">person</option>
                  </select>
                </label>
                <label className="col-span-2 text-xs text-muted-foreground">
                  Industry
                  <input
                    value={draft.industry ?? ''}
                    onChange={(e) => patchDraft({ industry: e.target.value })}
                    className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm text-foreground"
                  />
                </label>
                <label className="col-span-2 text-xs text-muted-foreground">
                  What to protect
                  <textarea
                    value={draft.protect_summary}
                    onChange={(e) => patchDraft({ protect_summary: e.target.value })}
                    rows={2}
                    className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm text-foreground"
                  />
                </label>
              </div>

              <div>
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-xs font-medium">Assets</span>
                  <Button size="sm" variant="ghost" onClick={addAsset}>
                    <Plus className="h-3.5 w-3.5" /> asset
                  </Button>
                </div>
                <div className="space-y-1">
                  {draft.assets.map((a, i) => (
                    <div key={i} className="flex items-center gap-1">
                      <select
                        value={a.type}
                        onChange={(e) => patchAsset(i, { type: e.target.value })}
                        className="rounded border bg-background px-1 py-1 text-xs"
                      >
                        {ASSET_TYPES.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                      <input
                        value={a.value}
                        onChange={(e) => patchAsset(i, { value: e.target.value })}
                        placeholder="value"
                        className="flex-1 rounded border bg-background px-2 py-1 font-mono text-xs"
                      />
                      <input
                        value={a.concerns.map((c) => c.type).join(', ')}
                        onChange={(e) =>
                          patchAsset(i, {
                            concerns: e.target.value
                              .split(',')
                              .map((s) => s.trim())
                              .filter(Boolean)
                              .map((t) => ({ type: t })),
                          })
                        }
                        placeholder="concerns"
                        className="w-40 rounded border bg-background px-2 py-1 text-xs"
                      />
                      <button
                        onClick={() => removeAsset(i)}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  concerns = comma-separated (phishing, scam, impersonation, doxxing, data_leak,
                  financial_fraud, online_threat, physical_attack, mention)
                </p>
              </div>

              {createError && <p className="text-xs text-destructive">Error: {createError}</p>}

              <div className="flex justify-end gap-2 pt-1">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setShowNew(false)
                    setDraft(null)
                  }}
                >
                  Cancel
                </Button>
                <Button size="sm" onClick={addNew} disabled={saving || !draft.name || !draft.assets.length}>
                  {saving ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" /> Adding…
                    </>
                  ) : (
                    <>
                      <Database className="h-4 w-4" /> Add &amp; ingest
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
