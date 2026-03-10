import { useKeycloak } from "@react-keycloak/web";
import { useState } from "react";
import { AllowedSenders } from "../components/AllowedSenders";
import { EmailLogs } from "../components/EmailLogs";
import { fetchWithAuth } from "../api";

export const Dashboard = () => {
    const { keycloak, initialized } = useKeycloak();
    const [checking, setChecking] = useState(false);
    const [checkMsg, setCheckMsg] = useState<string | null>(null);
    const [logsKey, setLogsKey] = useState(0); // bump to refresh EmailLogs

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

    const handleCheckEmails = async () => {
        setChecking(true);
        setCheckMsg(null);
        try {
            await fetchWithAuth("/check-emails", { method: "POST" });
            setCheckMsg("✅ Check started! Refreshing logs in a few seconds...");
            // Wait a few seconds then refresh the email logs
            setTimeout(() => {
                setLogsKey(k => k + 1);
                setCheckMsg("✅ Done! Logs updated.");
            }, 4000);
        } catch (e: any) {
            setCheckMsg(`❌ Error: ${e.message}`);
        } finally {
            setChecking(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50">
            <nav className="bg-white border-b border-gray-200 sticky top-0 z-10">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between h-16">
                        <div className="flex items-center gap-3">
                            <div className="bg-blue-600 text-white w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xl uppercase leading-none shadow-sm shadow-blue-200">A</div>
                            <h1 className="text-xl font-bold text-gray-900 tracking-tight">Agent Dashboard</h1>
                        </div>
                        <div className="flex items-center gap-3">
                            <button
                                onClick={handleCheckEmails}
                                disabled={checking}
                                className="flex items-center gap-2 text-sm font-semibold text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 py-1.5 px-4 rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed border border-blue-200"
                            >
                                {checking ? (
                                    <>
                                        <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                        </svg>
                                        Checking...
                                    </>
                                ) : (
                                    <>
                                        <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582M20 20v-5h-.581M5.632 8A9 9 0 0119 15.368M18.368 16A9 9 0 016 8.632" />
                                        </svg>
                                        Check Emails Now
                                    </>
                                )}
                            </button>
                            <span className="text-sm font-medium text-gray-600 bg-gray-100 px-3 py-1.5 rounded-full border border-gray-200">
                                {keycloak.tokenParsed?.preferred_username}
                            </span>
                            <button
                                onClick={() => keycloak.logout()}
                                className="text-sm font-semibold text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100 py-1.5 px-4 rounded-full transition-colors"
                            >
                                Logout
                            </button>
                        </div>
                    </div>
                </div>
            </nav>

            {checkMsg && (
                <div className={`max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4`}>
                    <div className={`text-sm px-4 py-2 rounded-lg border ${checkMsg.startsWith('✅') ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-700 border-red-200'}`}>
                        {checkMsg}
                    </div>
                </div>
            )}

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
                <AllowedSenders />
                <EmailLogs key={logsKey} />
            </main>
        </div>
    );
};


