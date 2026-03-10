import { useEffect, useState } from "react";
import { fetchWithAuth } from "../api";
import { Trash2, Plus } from "lucide-react";

type SenderType = "domain" | "email";

interface AllowedSender {
    id: number;
    type: SenderType;
    value: string;
    is_active: boolean;
    description?: string;
}

export const AllowedSenders = () => {
    const [senders, setSenders] = useState<AllowedSender[]>([]);
    const [loading, setLoading] = useState(true);

    const [form, setForm] = useState({ type: "domain" as SenderType, value: "", description: "" });

    const loadSenders = async () => {
        try {
            const data = await fetchWithAuth("/senders/");
            setSenders(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadSenders();
    }, []);

    const handleAdd = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!form.value) return;
        try {
            await fetchWithAuth("/senders/", {
                method: "POST",
                body: JSON.stringify(form)
            });
            setForm({ type: "domain", value: "", description: "" });
            loadSenders();
        } catch (err) {
            alert("Error adding sender");
        }
    };

    const handleDelete = async (id: number) => {
        try {
            await fetchWithAuth(`/senders/${id}`, { method: "DELETE" });
            loadSenders();
        } catch (err) {
            alert("Error deleting sender");
        }
    };

    return (
        <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl flex items-center gap-2 font-semibold mb-6 text-gray-800">
                <span className="bg-blue-100 text-blue-700 p-2 rounded-lg">🛡️</span>
                Allowed Senders
            </h2>

            <form onSubmit={handleAdd} className="flex gap-4 items-end mb-8 bg-gray-50 p-4 rounded-lg border border-gray-100">
                <label className="flex flex-col flex-1 text-sm font-medium text-gray-600">
                    Type
                    <select
                        className="mt-1 p-2 border rounded-md"
                        value={form.type}
                        onChange={(e) => setForm({ ...form, type: e.target.value as SenderType })}
                    >
                        <option value="domain">Domain (e.g. example.com)</option>
                        <option value="email">Email (e.g. foo@example.com)</option>
                    </select>
                </label>

                <label className="flex flex-col flex-[2] text-sm font-medium text-gray-600">
                    Value
                    <input
                        type="text"
                        placeholder={form.type === "domain" ? "example.com" : "user@example.com"}
                        className="mt-1 p-2 border rounded-md"
                        value={form.value}
                        onChange={(e) => setForm({ ...form, value: e.target.value })}
                        required
                    />
                </label>

                <label className="flex flex-col flex-[2] text-sm font-medium text-gray-600">
                    Description
                    <input
                        type="text"
                        className="mt-1 p-2 border rounded-md"
                        value={form.description}
                        onChange={(e) => setForm({ ...form, description: e.target.value })}
                    />
                </label>

                <button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-6 rounded-md shadow-sm flex items-center gap-2 transition-colors">
                    <Plus size={18} /> Add
                </button>
            </form>

            {loading ? (
                <div className="text-gray-500 animate-pulse text-center p-8">Loading rules...</div>
            ) : (
                <table className="w-full text-left bg-white rounded-lg overflow-hidden ring-1 ring-gray-200">
                    <thead className="bg-gray-100/50">
                        <tr>
                            <th className="p-4 font-semibold text-gray-600 font-mono text-sm tracking-wide">Type</th>
                            <th className="p-4 font-semibold text-gray-600 font-mono text-sm tracking-wide">Value</th>
                            <th className="p-4 font-semibold text-gray-600 font-mono text-sm tracking-wide">Description</th>
                            <th className="p-4 font-semibold text-gray-600 font-mono text-sm tracking-wide w-24 text-center">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {senders.map((s) => (
                            <tr key={s.id} className="hover:bg-gray-50/50 transition-colors">
                                <td className="p-4 text-gray-600 text-sm">
                                    <span className={`px-2 py-1 rounded text-xs font-semibold ${s.type === 'domain' ? 'bg-purple-100 text-purple-700' : 'bg-emerald-100 text-emerald-700'}`}>
                                        {s.type.toUpperCase()}
                                    </span>
                                </td>
                                <td className="p-4 text-gray-900 font-medium">{s.value}</td>
                                <td className="p-4 text-gray-500 text-sm">{s.description || "-"}</td>
                                <td className="p-4 text-center">
                                    <button onClick={() => handleDelete(s.id)} className="text-red-500 hover:text-red-700 p-2 rounded-full hover:bg-red-50 transition-colors" title="Delete Rule">
                                        <Trash2 size={18} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                        {senders.length === 0 && (
                            <tr><td colSpan={4} className="p-8 text-center text-gray-500">No allowed senders mapped yet.</td></tr>
                        )}
                    </tbody>
                </table>
            )}
        </div>
    );
};
