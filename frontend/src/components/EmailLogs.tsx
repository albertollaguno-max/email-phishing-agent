import { useEffect, useState, useCallback, useRef } from "react";
import { fetchWithAuth } from "../api";

const PAGE_SIZE = 15;

interface EmailLog {
    id: number;
    message_id: string;
    from_address: string;
    forwarded_by: string;
    subject: string;
    date_received: string;
    is_fraudulent: boolean | null;
    ai_explanation: string | null;
    ai_provider_used: string | null;
    prompt_tokens: number;
    completion_tokens: number;
    user_feedback: string | null;
    user_notes: string | null;
}

interface PagedResponse {
    total: number;
    page: number;
    page_size: number;
    pages: number;
    items: EmailLog[];
}

interface Filters {
    search: string;
    verdict: string;   // '' | 'phishing' | 'clean' | 'pending'
    feedback: string;  // '' | 'correct' | 'incorrect' | 'unrated'
}

const VERDICT_OPTIONS = [
    { value: '', label: 'All verdicts' },
    { value: 'phishing', label: '🚨 Phishing' },
    { value: 'clean', label: '✅ Clean' },
    { value: 'pending', label: '⏳ Pending' },
];

const FEEDBACK_OPTIONS = [
    { value: '', label: 'All ratings' },
    { value: 'correct', label: '👍 AI acertó' },
    { value: 'incorrect', label: '👎 AI falló' },
    { value: 'unrated', label: '— Sin valorar' },
];

export const EmailLogs = ({ refreshKey }: { refreshKey?: number }) => {
    const [data, setData] = useState<PagedResponse | null>(null);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(true);
    const [filters, setFilters] = useState<Filters>({ search: '', verdict: '', feedback: '' });
    const [pendingSearch, setPendingSearch] = useState('');

    // Selection
    const [selected, setSelected] = useState<Set<number>>(new Set());
    const [bulkMode, setBulkMode] = useState<'unseen' | 'permanent'>('unseen');
    const [bulkWorking, setBulkWorking] = useState(false);

    // Per-row state
    const [expandedId, setExpandedId] = useState<number | null>(null);
    const [feedbackState, setFeedbackState] = useState<Record<number, string>>({});
    const [deletingId, setDeletingId] = useState<number | null>(null);

    const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    const buildQuery = useCallback((p: number, f: Filters) => {
        const params = new URLSearchParams({ page: String(p), page_size: String(PAGE_SIZE) });
        if (f.search) params.set('search', f.search);
        if (f.verdict) params.set('verdict', f.verdict);
        if (f.feedback) params.set('feedback', f.feedback);
        return `/logs/emails?${params}`;
    }, []);

    const fetchLogs = useCallback(async (p: number, f: Filters) => {
        setLoading(true);
        setSelected(new Set());
        try {
            const result = await fetchWithAuth(buildQuery(p, f));
            setData(result);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, [buildQuery]);

    useEffect(() => {
        fetchLogs(page, filters);
    }, [page, filters, refreshKey, fetchLogs]);

    // Debounced search
    const handleSearchInput = (val: string) => {
        setPendingSearch(val);
        if (searchTimer.current) clearTimeout(searchTimer.current);
        searchTimer.current = setTimeout(() => {
            setPage(1);
            setFilters(f => ({ ...f, search: val }));
        }, 400);
    };

    const setFilter = (key: keyof Filters, val: string) => {
        setPage(1);
        setFilters(f => ({ ...f, [key]: val }));
    };

    // ── Selection ────────────────────────────────────────────────────────────
    const logs = data?.items ?? [];
    const allOnPageSelected = logs.length > 0 && logs.every(l => selected.has(l.id));

    const toggleAll = () => {
        if (allOnPageSelected) {
            setSelected(new Set());
        } else {
            setSelected(new Set(logs.map(l => l.id)));
        }
    };

    const toggleOne = (id: number) => {
        setSelected(prev => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
        });
    };

    // ── Bulk delete ──────────────────────────────────────────────────────────
    const handleBulkDelete = async () => {
        const ids = Array.from(selected);
        const label = bulkMode === 'permanent'
            ? `¿Eliminar PERMANENTEMENTE ${ids.length} email(s) de la BBDD y del buzón IMAP?`
            : `¿Borrar ${ids.length} email(s) de la BBDD y marcarlos como no leídos en IMAP?`;
        if (!confirm(label)) return;
        setBulkWorking(true);
        try {
            await fetchWithAuth('/logs/emails/bulk-delete', {
                method: 'POST',
                body: JSON.stringify({ ids, mode: bulkMode })
            });
            await fetchLogs(page, filters);
        } catch (e: any) {
            alert(`Error: ${e.message}`);
        } finally {
            setBulkWorking(false);
        }
    };

    // ── Single delete ────────────────────────────────────────────────────────
    const handleDelete = async (id: number, mode: 'unseen' | 'permanent' = 'unseen') => {
        const label = mode === 'permanent'
            ? '¿Eliminar permanentemente del buzón IMAP y de la BBDD?'
            : '¿Borrar de la BBDD y marcar como no leído en IMAP?';
        if (!confirm(label)) return;
        setDeletingId(id);
        try {
            await fetchWithAuth(`/logs/emails/${id}?mode=${mode}`, { method: 'DELETE' });
            await fetchLogs(page, filters);
        } catch (e: any) {
            alert(`Error: ${e.message}`);
        } finally {
            setDeletingId(null);
        }
    };

    // ── Feedback ─────────────────────────────────────────────────────────────
    const handleFeedback = async (id: number, verdict: 'correct' | 'incorrect') => {
        const current = feedbackState[id] ?? logs.find(l => l.id === id)?.user_feedback;
        if (current === verdict) return;
        setFeedbackState(prev => ({ ...prev, [id]: verdict }));
        try {
            await fetchWithAuth(`/logs/emails/${id}/feedback`, {
                method: 'PATCH',
                body: JSON.stringify({ user_feedback: verdict })
            });
        } catch (e: any) {
            setFeedbackState(prev => { const n = { ...prev }; delete n[id]; return n; });
            alert(`Error: ${e.message}`);
        }
    };

    const totalPages = data?.pages ?? 1;
    const hasSelection = selected.size > 0;

    return (
        <div className="bg-white shadow rounded-xl overflow-hidden">

            {/* ─── Header ──────────────────────────────────────────────────── */}
            <div className="px-6 py-4 border-b border-gray-100">
                <div className="flex items-center justify-between mb-3">
                    <h2 className="text-xl flex items-center gap-2 font-semibold text-gray-800">
                        <span className="bg-blue-100 text-blue-700 p-2 rounded-lg text-base">📨</span>
                        Analyzed Emails Log
                        {data && <span className="text-sm font-normal text-gray-400">({data.total} total)</span>}
                    </h2>
                    <button onClick={() => fetchLogs(page, filters)}
                        className="text-xs text-gray-400 hover:text-blue-600 flex items-center gap-1 transition-colors">
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582M20 20v-5h-.581M5.632 8A9 9 0 0119 15.368M18.368 16A9 9 0 016 8.632" />
                        </svg>
                        Refresh
                    </button>
                </div>

                {/* ─── Filter bar ─────────────────────────────────────────── */}
                <div className="flex flex-wrap items-center gap-2">
                    {/* Search */}
                    <div className="relative flex-1 min-w-[180px]">
                        <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
                        </svg>
                        <input
                            type="text"
                            value={pendingSearch}
                            onChange={e => handleSearchInput(e.target.value)}
                            placeholder="Buscar en asunto o remitente…"
                            className="w-full pl-8 pr-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300"
                        />
                    </div>

                    {/* Verdict filter */}
                    <select value={filters.verdict} onChange={e => setFilter('verdict', e.target.value)}
                        className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-300 bg-white">
                        {VERDICT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>

                    {/* Feedback filter */}
                    <select value={filters.feedback} onChange={e => setFilter('feedback', e.target.value)}
                        className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-300 bg-white">
                        {FEEDBACK_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>

                    {/* Clear filters */}
                    {(filters.search || filters.verdict || filters.feedback) && (
                        <button onClick={() => { setFilters({ search: '', verdict: '', feedback: '' }); setPendingSearch(''); setPage(1); }}
                            className="text-xs text-red-400 hover:text-red-600 px-2 py-1.5 rounded-lg hover:bg-red-50 transition-colors">
                            ✕ Limpiar filtros
                        </button>
                    )}
                </div>
            </div>

            {/* ─── Bulk action toolbar (appears on selection) ──────────────── */}
            {hasSelection && (
                <div className="flex items-center gap-3 px-6 py-2.5 bg-blue-50 border-b border-blue-100 text-sm">
                    <span className="font-medium text-blue-700">{selected.size} seleccionado{selected.size > 1 ? 's' : ''}</span>
                    <div className="flex items-center gap-1 ml-2">
                        <label className="text-xs text-gray-600 mr-1">Acción:</label>
                        <button onClick={() => setBulkMode('unseen')}
                            className={`px-2.5 py-1 text-xs rounded-l-md border transition-colors ${bulkMode === 'unseen' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'}`}>
                            🔄 Marcar no leído
                        </button>
                        <button onClick={() => setBulkMode('permanent')}
                            className={`px-2.5 py-1 text-xs rounded-r-md border-t border-r border-b transition-colors ${bulkMode === 'permanent' ? 'bg-red-600 text-white border-red-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'}`}>
                            🗑️ Eliminar permanente
                        </button>
                    </div>
                    <button onClick={handleBulkDelete} disabled={bulkWorking}
                        className={`ml-2 px-3 py-1 text-xs font-semibold rounded-lg transition-colors disabled:opacity-50 ${bulkMode === 'permanent' ? 'bg-red-500 hover:bg-red-600 text-white' : 'bg-blue-500 hover:bg-blue-600 text-white'
                            }`}>
                        {bulkWorking ? '⟳ Procesando…' : 'Confirmar'}
                    </button>
                    <button onClick={() => setSelected(new Set())} className="ml-auto text-xs text-gray-400 hover:text-gray-600">
                        Cancelar
                    </button>
                </div>
            )}

            {/* ─── Table ───────────────────────────────────────────────────── */}
            <div className="overflow-x-auto">
                {loading ? (
                    <div className="p-10 text-center text-gray-400 animate-pulse">Loading...</div>
                ) : (
                    <table className="w-full text-left">
                        <thead className="bg-gray-50 border-b border-gray-100">
                            <tr>
                                {/* Checkbox column */}
                                <th className="px-3 py-3 w-8">
                                    <input type="checkbox" checked={allOnPageSelected} onChange={toggleAll}
                                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-300 cursor-pointer" />
                                </th>
                                <th className="px-4 py-3 font-semibold text-gray-500 text-xs tracking-wide uppercase">Date</th>
                                <th className="px-4 py-3 font-semibold text-gray-500 text-xs tracking-wide uppercase">Subject</th>
                                <th className="px-4 py-3 font-semibold text-gray-500 text-xs tracking-wide uppercase">From / Fwd By</th>
                                <th className="px-4 py-3 font-semibold text-gray-500 text-xs tracking-wide uppercase">Verdict</th>
                                <th className="px-4 py-3 font-semibold text-gray-500 text-xs tracking-wide uppercase text-right">Tokens</th>
                                <th className="px-4 py-3 font-semibold text-gray-500 text-xs tracking-wide uppercase text-center">Feedback / Acción</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50 text-sm">
                            {logs.map((log) => {
                                const isSelected = selected.has(log.id);
                                const fb = feedbackState[log.id] ?? log.user_feedback;
                                return (
                                    <>
                                        <tr key={log.id}
                                            className={`transition-colors cursor-pointer ${isSelected ? 'bg-blue-50' : 'hover:bg-gray-50/60'}`}
                                            onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}>

                                            {/* Checkbox */}
                                            <td className="px-3 py-3" onClick={e => { e.stopPropagation(); toggleOne(log.id); }}>
                                                <input type="checkbox" checked={isSelected} onChange={() => toggleOne(log.id)}
                                                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-300 cursor-pointer" />
                                            </td>

                                            <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                                                {log.date_received ? new Date(log.date_received).toLocaleString('es-ES') : '—'}
                                            </td>
                                            <td className="px-4 py-3 font-medium text-gray-900 max-w-[200px] truncate" title={log.subject}>
                                                {log.subject || "No Subject"}
                                            </td>
                                            <td className="px-4 py-3 text-gray-600 max-w-[160px]">
                                                <div className="truncate text-xs">{log.from_address || "?"}</div>
                                                <div className="text-xs text-gray-400 mt-0.5 truncate">fwd: {log.forwarded_by}</div>
                                            </td>
                                            <td className="px-4 py-3">
                                                {log.is_fraudulent === true ? (
                                                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-semibold bg-red-100 text-red-700">🚨 Phishing</span>
                                                ) : log.is_fraudulent === false ? (
                                                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-semibold bg-green-100 text-green-700">✅ Clean</span>
                                                ) : (
                                                    <span className="px-2 py-1 rounded-md text-xs font-semibold bg-yellow-100 text-yellow-700">⏳ Pending</span>
                                                )}
                                            </td>
                                            <td className="px-4 py-3 text-right text-gray-500 text-xs">
                                                {(log.prompt_tokens || 0) + (log.completion_tokens || 0) > 0 ? (
                                                    <span>
                                                        {(log.prompt_tokens || 0) + (log.completion_tokens || 0)}
                                                        <p className="text-[10px] text-gray-400 mt-0.5">{log.ai_provider_used}</p>
                                                    </span>
                                                ) : '—'}
                                            </td>

                                            {/* Actions */}
                                            <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                                                <div className="flex items-center justify-center gap-0.5">
                                                    {/* Thumbs */}
                                                    <button onClick={() => handleFeedback(log.id, 'correct')} title="IA acertó ✓"
                                                        className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all text-base ${fb === 'correct' ? 'bg-green-100 scale-110' : 'text-gray-300 hover:text-green-500 hover:bg-green-50'}`}>
                                                        👍
                                                    </button>
                                                    <button onClick={() => handleFeedback(log.id, 'incorrect')} title="IA se equivocó ✗"
                                                        className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all text-base ${fb === 'incorrect' ? 'bg-orange-100 scale-110' : 'text-gray-300 hover:text-orange-400 hover:bg-orange-50'}`}>
                                                        👎
                                                    </button>

                                                    {/* Delete single — unseen (default) */}
                                                    <button onClick={() => handleDelete(log.id, 'unseen')} disabled={deletingId === log.id}
                                                        title="Borrar y marcar no leído (reenviar al agente)"
                                                        className="w-7 h-7 ml-0.5 rounded-lg flex items-center justify-center text-gray-300 hover:text-amber-500 hover:bg-amber-50 transition-colors disabled:opacity-40">
                                                        {deletingId === log.id ? (
                                                            <svg className="animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
                                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                                            </svg>
                                                        ) : (
                                                            /* Recycle / re-process icon */
                                                            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582M20 20v-5h-.581M5.632 8A9 9 0 0119 15.368M18.368 16A9 9 0 016 8.632" />
                                                            </svg>
                                                        )}
                                                    </button>

                                                    {/* Delete single — permanent */}
                                                    <button onClick={() => handleDelete(log.id, 'permanent')} disabled={deletingId === log.id}
                                                        title="Eliminar permanentemente del buzón IMAP"
                                                        className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-40">
                                                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                        </svg>
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>

                                        {/* Expanded AI explanation */}
                                        {expandedId === log.id && (
                                            <tr key={`exp-${log.id}`} className="bg-blue-50/60">
                                                <td colSpan={7} className="px-8 py-3">
                                                    <div className="flex items-start gap-2 text-xs text-gray-700">
                                                        <span className="text-blue-500 mt-0.5 shrink-0">🤖</span>
                                                        <p className="leading-relaxed">{log.ai_explanation || "Sin explicación disponible."}</p>
                                                    </div>
                                                    {fb && (
                                                        <p className="mt-1.5 text-xs text-gray-400 italic">
                                                            Feedback: <span className={`font-medium ${fb === 'correct' ? 'text-green-600' : 'text-orange-600'}`}>
                                                                {fb === 'correct' ? '✓ IA acertó' : '✗ IA se equivocó'}
                                                            </span>
                                                            <span className="ml-1 text-[10px]">(usado para mejorar futuros análisis)</span>
                                                        </p>
                                                    )}
                                                </td>
                                            </tr>
                                        )}
                                    </>
                                );
                            })}
                            {logs.length === 0 && (
                                <tr>
                                    <td colSpan={7} className="p-10 text-center text-gray-400">
                                        {filters.search || filters.verdict || filters.feedback
                                            ? '🔍 No se encontraron resultados con los filtros actuales.'
                                            : 'No emails have been analyzed yet.'}
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                )}
            </div>

            {/* ─── Pagination ──────────────────────────────────────────────── */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between px-6 py-3 border-t border-gray-100 bg-gray-50">
                    <p className="text-xs text-gray-500">
                        Página {page} de {totalPages} — {data?.total} resultados
                    </p>
                    <div className="flex items-center gap-1">
                        <button onClick={() => setPage(1)} disabled={page === 1}
                            className="px-2 py-1 text-xs rounded hover:bg-gray-200 disabled:opacity-30 transition-colors">«</button>
                        <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                            className="px-2 py-1 text-xs rounded hover:bg-gray-200 disabled:opacity-30 transition-colors">‹</button>
                        {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                            const start = Math.max(1, Math.min(page - 2, totalPages - 4));
                            const p = start + i;
                            return (
                                <button key={p} onClick={() => setPage(p)}
                                    className={`px-2.5 py-1 text-xs rounded transition-colors ${p === page ? 'bg-blue-600 text-white font-semibold' : 'hover:bg-gray-200 text-gray-600'
                                        }`}>{p}</button>
                            );
                        })}
                        <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                            className="px-2 py-1 text-xs rounded hover:bg-gray-200 disabled:opacity-30 transition-colors">›</button>
                        <button onClick={() => setPage(totalPages)} disabled={page === totalPages}
                            className="px-2 py-1 text-xs rounded hover:bg-gray-200 disabled:opacity-30 transition-colors">»</button>
                    </div>
                </div>
            )}
        </div>
    );
};
