import { useRef, useState } from "react";
import { Upload, Database, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import { IDS } from "@/constants/testIds";
import { loadPreset, uploadCsv } from "@/lib/api";
import { toast } from "sonner";

export default function DatasetPanel({ session, onLoaded }) {
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const doPreset = async () => {
    setBusy(true);
    try { const s = await loadPreset(); onLoaded(s); toast.success("IO-VNBD S-S1 preset loaded"); }
    catch (e) { toast.error(e?.message || "Failed to load preset"); }
    finally { setBusy(false); }
  };

  const doUpload = async (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    setBusy(true);
    try { const s = await uploadCsv(f); onLoaded(s); toast.success(`Loaded ${f.name}`); }
    catch (err) { toast.error(err?.message || "Upload failed"); }
    finally { setBusy(false); e.target.value = ""; }
  };

  const chartData = session?.sensor_series?.t?.map((t, i) => ({
    t: Number(t.toFixed?.(1) ?? t),
    ax: session.sensor_series.ax[i],
    ay: session.sensor_series.ay[i],
    az: session.sensor_series.az[i],
    speed: session.sensor_series.speed[i],
  })) ?? [];

  return (
    <div className="card-tactical p-6" data-testid={IDS.datasetCard}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.2em] text-cyan-400">Step 1</div>
          <h3 className="text-xl font-heading font-semibold text-slate-100">Dataset</h3>
        </div>
        <div className="flex gap-2">
          <Button
            data-testid={IDS.loadPresetBtn}
            disabled={busy}
            onClick={doPreset}
            className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold"
          >
            {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Database className="w-4 h-4 mr-2" />}
            Load IO-VNBD Preset
          </Button>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
            className="border-slate-700 text-slate-200 hover:bg-slate-800"
          >
            <Upload className="w-4 h-4 mr-2" /> Upload CSV
          </Button>
          <input
            ref={fileRef}
            data-testid={IDS.uploadInput}
            type="file"
            accept=".csv"
            onChange={doUpload}
            className="hidden"
          />
        </div>
      </div>

      {!session && (
        <p className="text-slate-400 text-sm">
          Load the bundled <span className="font-mono text-cyan-400">S-S1.csv</span> IO-VNBD sample
          (Coventry drive, first ~10 min at native 10 Hz) or upload your own smartphone log.
        </p>
      )}

      {session && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Stat label="Samples" value={session.n_samples.toLocaleString()} />
            <Stat label="Duration" value={`${session.duration_s.toFixed(0)} s`} />
            <Stat label="Origin Lat" value={session.lat0.toFixed(5)} />
            <Stat label="Origin Lon" value={session.lon0.toFixed(5)} />
          </div>

          <div className="mt-4 h-56 -mx-2">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 8, right: 24, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="t" stroke="#64748b" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }}
                       label={{ value: "t (s)", fill: "#64748b", fontSize: 10, dy: 10 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="ax" stroke="#06b6d4" dot={false} strokeWidth={1} name="ax" />
                <Line type="monotone" dataKey="ay" stroke="#a855f7" dot={false} strokeWidth={1} name="ay" />
                <Line type="monotone" dataKey="az" stroke="#f59e0b" dot={false} strokeWidth={1} name="az" />
                <Line type="monotone" dataKey="speed" stroke="#10b981" dot={false} strokeWidth={1.5} name="v (m/s)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="p-3 rounded-md border border-slate-800 bg-slate-950/50">
      <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</div>
      <div className="stat-value text-slate-100 text-lg">{value}</div>
    </div>
  );
}
