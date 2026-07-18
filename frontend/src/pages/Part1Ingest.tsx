import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Check,
  ChevronRight,
  Database,
  Loader2,
  Lock,
  RotateCcw,
  Search,
  ShieldAlert,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  getCustomer,
  getCustomers,
  getStoresStatus,
  ingestAll,
  ingestStreamUrl,
  resetIngest,
  type CustomerDetail,
  type CustomerSummary,
  type StoresStatus,
} from '@/lib/api'

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
          <Button variant="secondary" size="sm" onClick={onIngestAll} disabled={!!ingestingId || bulk}>
            {bulk ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
            Ingest all
          </Button>
          <Button variant="outline" size="sm" onClick={onReset} disabled={!!ingestingId || bulk}>
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
                <button
                  key={c.id}
                  onClick={() => !locked && select(c.id)}
                  disabled={locked || !!ingestingId}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors',
                    selectedId === c.id ? 'border-primary bg-accent' : 'border-transparent hover:bg-accent',
                    locked && 'opacity-45',
                  )}
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
                    {detail.type} · {detail.industry}
                  </p>
                  <p className="mt-2 max-w-2xl text-sm">{detail.protect_summary}</p>
                </div>
                <Button
                  onClick={() => ingest(detail.id)}
                  disabled={detail.ingested || ingestingId !== null || customers[activeIndex]?.id !== detail.id}
                >
                  {ingestingId === detail.id ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" /> Ingesting…
                    </>
                  ) : detail.ingested ? (
                    <>
                      <Check className="h-4 w-4" /> Ingested
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
                <div className="max-h-64 space-y-1 overflow-auto rounded-md bg-muted/40 p-3 font-mono text-xs">
                  {log.map((e, i) => (
                    <div
                      key={i}
                      className={cn(
                        e.event === 'complete' && 'font-semibold text-green-700',
                        e.event === 'error' && 'font-semibold text-destructive',
                        e.event === 'asset_done' && 'text-green-700',
                      )}
                    >
                      {describe(e)}
                    </div>
                  ))}
                  {ingestingId && <div className="animate-pulse text-muted-foreground">…</div>}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
