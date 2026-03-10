import { useEffect, useState, useCallback } from "react";
import { fetchWithAuth } from "../api";

const PAGE_SIZE = 10;

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
}

interface PagedResponse {
    total: number;
    page: number;
    page_size: number;
    pages: number;
    items: EmailLog[];
}

export const EmailLogs = () => {
    const [data, setData] = useState<PagedResponse | null>(null);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(true);
    const [deletingId, setDeletingId] = useState<number | null>(null);
    const [expandedId, setExpandedId] = useState<number | null>(null);

    const fetchLogs = useCallback(async (p: number) => {
        setLoading(true);
        try {
            const result = await fetchWithAuth(`/logs/emails?page=${p}&page_size=${PAGE_SIZE}`);
            setData(result);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchLogs(page);
    }, [page, fetchLogs]);

    const handleDelete = async (id: number) => {
        if (!confirm("¿Borrar este registro? El email volverá a marcarse como no leído en IMAP.")) return;
        setDeletingId(id);
        try {
            await fetchWithAuth(`/logs/emails/${id}`, { method: "DELETE" });
            // Refresh current page (or go back if it was the last item)
            await fetchLogs(page);
        } catch (e: any) {
            alert(`Error al borrar: ${e.message}`);
        } finally {
            setDeletingId(null);
        }
    };

    const logs = data?.items ?? [];
    const totalPages = data?.pages ?? 1;

    return (
        <div className="bg-white shadow rounded-xl overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
                <h2 className="text-xl flex items-center gap-2 font-semibold text-gray-800">
                    <span className="bg-blue-100 text-blue-700 p-2 rounded-lg text-base">📨</span>
                    Analyzed Emails Log
                    {data && (
                        <span className="ml-2 text-sm font-normal text-gray-400">
                            ({data.total} total)
                        </span>
                    )}
                </h2>
                <button
                    onClick={() => fetchLogs(page)}
                    className="text-xs text-gray-500 hover:text-blue-600 flex items-center gap-1 transition-colors"
                >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582M20 20v-5h-.581M5.632 8A9 9 0 0119 15.368M18.368 16A9 9 0 016 8.632" />
                    </svg>
                    Refresh
                </button>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
                {loading ? (
                    <div className="p-10 text-center text-gray-400 animate-pulse">Loading...</div>
                ) : (
                    <table className="w-full text-left">
                        <thead className="bg-gray-50 border-b border-gray-100">
                            <tr>
                                <th className="px-4 py-3 font-semibold text-gray-500 text-xs tracking-wide uppercase">Date</th>
                                <th className="px-4 py-3 font-semibold text-gray-500 text-xs tracking-wide uppercase">Subject</th>
                                <th className="px-4 py-3 font-semibold text-gray-500 text-xs tracking-wide uppercase">From / Fwd By</th>
                                <th className="px-4 py-3 font-semibold text-gray-500 text-xs tracking-wide uppercase">Verdict</th>
                                <th className="px-4 py-3 font-semibold text-gray-500 text-xs tracking-wide uppercase text-right">Tokens</th>
                                <th className="px-4 py-3 font-semibold text-gray-500 text-xs tracking-wide uppercase text-center">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50 text-sm">
                            {logs.map((log) => (
                                <>
                                    <tr
                                        key={log.id}
                                        className="hover:bg-blue-50/40 transition-colors cursor-pointer"
                                        onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                                    >
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
                                                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-semibold bg-red-100 text-red-700">
                                                    🚨 Phishing
                                                </span>
                                            ) : log.is_fraudulent === false ? (
                                                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-semibold bg-green-100 text-green-700">
                                                    ✅ Clean
                                                </span>
                                            ) : (
                                                <span className="px-2 py-1 rounded-md text-xs font-semibold bg-yellow-100 text-yellow-700">
                                                    ⏳ Pending
                                                </span>
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
                                        <td className="px-4 py-3 text-center" onClick={(e) => e.stopPropagation()}>
                                            <button
                                                onClick={() => handleDelete(log.id)}
                                                disabled={deletingId === log.id}
                                                className="inline-flex items-center justify-center w-7 h-7 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors disabled:opacity-40"
                                                title="Delete & mark as unread"
                                            >
                                                {deletingId === log.id ? (
                                                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                                    </svg>
                                                ) : (
                                                    <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                    </svg>
                                                )}
                                            </button>
                                        </td>
                                    </tr>
                                    {/* Expandable explanation row */}
                                    {expandedId === log.id && log.ai_explanation && (
                                        <tr key={`exp-${log.id}`} className="bg-blue-50/60">
                                            <td colSpan={6} className="px-6 py-3">
                                                <div className="flex items-start gap-2 text-xs text-gray-700">
                                                    <span className="text-blue-500 mt-0.5 shrink-0">🤖</span>
                                                    <p className="leading-relaxed">{log.ai_explanation}</p>
                                                </div>
                                            </td>
                                        </tr>
                                    )}
                                </>
                            ))}
                            {logs.length === 0 && (
                                <tr>
                                    <td colSpan={6} className="p-10 text-center text-gray-400">
                                        No emails have been analyzed yet.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between px-6 py-3 border-t border-gray-100 bg-gray-50">
                    <p className="text-xs text-gray-500">
                        Page {page} of {totalPages} — {data?.total} results
                    </p>
                    <div className="flex items-center gap-1">
                        <button
                            onClick={() => setPage(1)}
                            disabled={page === 1}
                            className="px-2 py-1 text-xs rounded hover:bg-gray-200 disabled:opacity-30 transition-colors"
                        >«</button>
                        <button
                            onClick={() => setPage(p => Math.max(1, p - 1))}
                            disabled={page === 1}
                            className="px-2 py-1 text-xs rounded hover:bg-gray-200 disabled:opacity-30 transition-colors"
                        >‹</button>
                        {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                            const start = Math.max(1, Math.min(page - 2, totalPages - 4));
                            const p = start + i;
                            return (
                                <button
                                    key={p}
                                    onClick={() => setPage(p)}
                                    className={`px-2.5 py-1 text-xs rounded transition-colors ${p === page
                                            ? 'bg-blue-600 text-white font-semibold'
                                            : 'hover:bg-gray-200 text-gray-600'
                                        }`}
                                >{p}</button>
                            );
                        })}
                        <button
                            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                            disabled={page === totalPages}
                            className="px-2 py-1 text-xs rounded hover:bg-gray-200 disabled:opacity-30 transition-colors"
                        >›</button>
                        <button
                            onClick={() => setPage(totalPages)}
                            disabled={page === totalPages}
                            className="px-2 py-1 text-xs rounded hover:bg-gray-200 disabled:opacity-30 transition-colors"
                        >»</button>
                    </div>
                </div>
            )}
        </div>
    );
};
