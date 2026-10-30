import { useState } from "react";
import StructuredData from "../components/common/StructuredData";
import api from "../services/api";
import { extractErrorMessage } from "../utils/error";

export default function AI() {
  const [shipmentId, setShipmentId] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const analyze = async (event) => {
    event.preventDefault();
    setError("");
    setData(null);
    setLoading(true);
    try {
      const response = await api.post("/ai/analyze", { shipment_id: shipmentId.trim() });
      setData(response.data);
    } catch (requestError) {
      setError(extractErrorMessage(requestError, "Unable to analyze the shipment."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section>
      <h1 className="text-3xl font-bold text-[#102a43]">AI Shipment Analysis</h1>
      <p className="mt-2 text-sm text-slate-600">Run deterministic risk and provenance checks using this shipment’s persisted batch and identity records.</p>
      <form onSubmit={analyze} className="mt-6 flex max-w-xl gap-3">
        <input required value={shipmentId} onChange={(event) => setShipmentId(event.target.value)} placeholder="Shipment ID" className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-[#5a1725]" />
        <button disabled={loading} className="rounded-lg bg-[#5a1725] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{loading ? "Analyzing…" : "Analyze"}</button>
      </form>
      <p className="mt-3 text-xs text-slate-500">No sensor readings or route events are submitted by this form. Telemetry-based checks require recorded readings; the adapter resolves batch and QR/RFID identities from PostgreSQL.</p>
      {error && <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {data && (
        <div className="mt-5 space-y-4">
          <article className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-[#102a43]">Risk assessment</h2>
            <StructuredData value={data.risk} className="mt-4" />
          </article>
          <article className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-[#102a43]">Identity assessment</h2>
            <StructuredData value={data.counterfeit} className="mt-4" />
          </article>
          <article className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-[#102a43]">Anomalies and correlations</h2>
            <StructuredData value={{ anomalies: data.anomalies, correlations: data.correlations }} className="mt-4" />
          </article>
          <article className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-[#102a43]">Explainability and model status</h2>
            <StructuredData value={{ explanations: data.explanations, explainability: data.explainability, blockchain: data.blockchain, ml_assessment: data.ml_assessment }} className="mt-4" />
          </article>
          <article className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-[#102a43]">Alerts returned by this analysis</h2>
            <StructuredData value={data.alerts} className="mt-4" />
          </article>
        </div>
      )}
    </section>
  );
}
