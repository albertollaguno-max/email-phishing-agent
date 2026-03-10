import { useKeycloak } from "@react-keycloak/web";
import { useState } from "react";
import { AllowedSenders } from "../components/AllowedSenders";
import { EmailLogs } from "../components/EmailLogs";
import { fetchWithAuth } from "../api";

const REQUIRED_ROLE = 'emailphisingIA';

export const Dashboard = () => {
    const { keycloak, initialized } = useKeycloak();
    const [checking, setChecking] = useState(false);
    const [checkMsg, setCheckMsg] = useState<string | null>(null);
    const [logsKey, setLogsKey] = useState(0);

    if (!initialized) {
        return <div className="flex items-center justify-center min-h-screen text-gray-500">Connecting to Keycloak...</div>;
    }

    if (!keycloak.authenticated) {
        return (
            <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50">
                <div className="bg-white p-12 rounded-2xl shadow-xl text-center max-w-sm w-full mx-4 border border-gray-100">
                    <h1 className="text-2xl font-bold mb-2 text-gray-800">Email Phishing Agent</h1>
                    <p className="text-gray-500 mb-8 text-sm">Protected environment mapping and AI email analysis node</p>
                    <button
                        onClick={() => keycloak.login()}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors shadow shadow-blue-500/30"
                    >
                        Log in with Keycloak
                    </button>
                </div>
            </div>
        );
    }

    // ── Role check (from token) ──────────────────────────────────────────
    const tp = keycloak.tokenParsed as any;
    const realmRoles: string[] = tp?.realm_access?.roles ?? [];
    const hasRole = realmRoles.includes(REQUIRED_ROLE);
    const username = tp?.preferred_username || tp?.email || '';

    if (!hasRole) {
        return (
            <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50">
                <div className="bg-white p-12 rounded-2xl shadow-xl text-center max-w-md w-full mx-4 border border-red-100">
                    <div className="mx-auto w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-5">
                        <svg className="h-8 w-8 text-red-500" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                        </svg>
                    </div>
                    <h1 className="text-xl font-bold mb-2 text-gray-800">Acceso Denegado</h1>
                    <p className="text-gray-500 text-sm mb-2">
                        Hola <span className="font-semibold text-gray-700">{username}</span>,
                        tu cuenta no tiene el rol <code className="bg-red-50 text-red-600 px-1.5 py-0.5 rounded text-xs font-mono">{REQUIRED_ROLE}</code> necesario.
                    </p>
                    <p className="text-gray-400 text-xs mb-6">
                        Contacta con el administrador para que te asigne el rol en Keycloak.
                    </p>
                    <button onClick={() => keycloak.logout()}
                        className="w-full bg-red-500 hover:bg-red-600 text-white font-semibold py-3 px-6 rounded-lg transition-colors shadow">
                        Cerrar sesión
                    </button>
                </div>
            </div>
        );
    }

    const handleCheckEmails = async () => {
        setChecking(true);
        setCheckMsg(null);
        try {
            await fetchWithAuth("/check-emails", { method: "POST" });
            setCheckMsg("✅ Check started! Refreshing logs in a few seconds...");
            setTimeout(() => { setLogsKey(k => k + 1); setCheckMsg(null); }, 5000);
        } catch (err: any) {
            setCheckMsg(`❌ ${err.message}`);
        } finally {
            setChecking(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
            <header className="bg-white/70 backdrop-blur-sm border-b border-gray-200 shadow-sm sticky top-0 z-10">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
                    <div>
                        <h1 className="text-xl font-bold tracking-tight text-gray-800 flex items-center gap-2">
                            <span className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">⛨ Email Phishing Agent</span>
                        </h1>
                        <p className="text-xs text-gray-400 mt-0.5">Logged in as <span className="font-medium text-gray-600">{username}</span></p>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={handleCheckEmails}
                            disabled={checking}
                            className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white text-sm font-semibold py-2 px-5 rounded-lg transition-colors shadow shadow-blue-500/20"
                        >
                            {checking ? "⏳ Checking…" : "🔍 Check Emails Now"}
                        </button>
                        <button onClick={() => keycloak.logout()}
                            className="text-sm text-gray-500 hover:text-red-600 transition-colors border border-gray-200 rounded-lg px-3 py-2">
                            Logout
                        </button>
                    </div>
                </div>
                {checkMsg && <div className="max-w-7xl mx-auto px-4 pb-3 text-sm text-gray-600">{checkMsg}</div>}
            </header>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
                <AllowedSenders />
                <EmailLogs key={logsKey} />
            </main>
        </div>
    );
};
