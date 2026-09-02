import { useRef, useState } from "react";
import { Upload, Database, Loader2, Satellite, Smartphone, CheckCircle2, Circle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import { IDS } from "@/constants/testIds";
import { loadPreset, uploadCsv } from "@/lib/api";
import { toast } from "sonner";

export default function DatasetPanel({ session, onLoaded }) {
  const [busy, setBusy] = useState(false);
  const [vboxFile, setVboxFile] = useState(null);
  const [phoneFile, setPhoneFile] = useState(null);
  const vboxRef = useRef(null);
  const phoneRef = useRef(null);

  const doPreset = async () => {
    setBusy(true);
    try {
      const s = await loadPreset();
      onLoaded(s);
      toast.success(
        s.has_vbox
          ? "IO-VNBD preset loaded · VBOX GT aligned with smartphone log"
          : "IO-VNBD smartphone preset loaded (VBOX not aligned)"
      );
    } catch (e) {
      toast.error(e?.message || "Failed to load preset");
    } finally {
      setBusy(false);
    }
  };

  const doUpload = async () => {
    if (!phoneFile) {
      toast.error("Please pick a smartphone (S-*) CSV first");
      return;
    }
    setBusy(true);
    try {
      const s = await uploadCsv(phoneFile, vboxFile);
      onLoaded(s);
      toast.success(
        vboxFile
          ? `Loaded ${phoneFile.name} + VBOX ${vboxFile.name}`
          : `Loaded ${phoneFile.name} (no VBOX GT)`
      );
      setPhoneFile(null);
      setVboxFile(null);
    } catch (e) {
      toast.error(e?.response?.data?.detail || e?.message || "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const chartData = session?.sensor_series?.t?.map((t, i) => ({
    t: Number(t.toFixed?.(1) ?? t),
    ax: session.sensor_series.ax[i],
    ay: session.sensor_series.ay[i],
    az: session.sensor_series.az[i],
    speed: session.sensor_series.speed[i],
    gt_v: session.sensor_series.gt_v?.[i],
  })) ?? [];

  return (
    <div className="card-tactical p-6" data-testid={IDS.datasetCard}>
      <div className="flex items-start justify-between mb-4 gap-3 flex-wrap">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.2em] text-cyan-400">Step 1</div>
          <h3 className="text-xl font-heading font-semibold text-slate-100">Dataset · VBOX + Smartphone</h3>
          <p className="text-xs text-slate-400 mt-1">
            VBOX = high-precision ground truth · Smartphone = dead-reckoning input
          </p>
        </div>
        <Button
          data-testid={IDS.loadPresetBtn}
          disabled={busy}
          onClick={doPreset}
          className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold"
        >
          {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Database className="w-4 h-4 mr-2" />}
          Load IO-VNBD Preset (V + S)
        </Button>
      </div>

      {/* Uploader — VBOX first, then Smartphone */}
      <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-3 mb-4">
        <FileDrop
          idx="1"
          testid="vbox-file-input"
          title="VBOX (V-*.csv)"
          subtitle="Ground truth"
          icon={Satellite}
          tone="orange"
          file={vboxFile}
          onPick={() => vboxRef.current?.click()}
        />
        <input ref={vboxRef} type="file" accept=".csv" className="hidden"
               onChange={(e) => setVboxFile(e.target.files?.[0] || null)} />

        <FileDrop
          idx="2"
          testid={IDS.uploadInput}
          title="Smartphone (S-*.csv)"
          subtitle="IMU + phone GPS"
          icon={Smartphone}
          tone="cyan"
          file={phoneFile}
          onPick={() => phoneRef.current?.click()}
        />
        <input ref={phoneRef} type="file" accept=".csv" className="hidden"
               onChange={(e) => setPhoneFile(e.target.files?.[0] || null)} />

        <Button
          data-testid="dataset-upload-btn"
          onClick={doUpload}
          disabled={busy || !phoneFile}
          className="bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 h-auto py-3"
        >
          <Upload className="w-4 h-4 mr-2" /> Upload
        </Button>
      </div>

      {!session && (
        <p className="text-slate-400 text-sm">
          <span className="text-orange-400">Tip:</span> load the bundled IO-VNBD preset for a
          Coventry drive where VBOX and smartphone logs are pre-aligned. Or upload your own pair —
          VBOX first (ground truth), smartphone second (dead-reckoning input).
        </p>
      )}

      {session && (
        <>
          <div className="mb-3">
            <span
              data-testid="dataset-gt-source"
              className={`inline-flex items-center gap-2 px-3 py-1 rounded-md border text-xs font-mono ${
                session.has_vbox
                  ? "border-orange-500/40 bg-orange-500/10 text-orange-300"
                  : "border-slate-700 bg-slate-900 text-slate-400"
              }`}
            >
              {session.has_vbox ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Circle className="w-3.5 h-3.5" />}
              GT source: {session.has_vbox ? "VBOX (aligned)" : "smartphone GPS (VBOX not provided)"}
            </span>
          </div>

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
                {session.has_vbox && (
                  <Line type="monotone" dataKey="gt_v" stroke="#f97316" dot={false}
                        strokeWidth={1.8} name="VBOX v (m/s)" />
                )}
                {!session.has_vbox && (
                  <Line type="monotone" dataKey="speed" stroke="#10b981" dot={false}
                        strokeWidth={1.5} name="v (m/s)" />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}

function FileDrop({ idx, testid, title, subtitle, icon: Icon, tone, file, onPick }) {
  const toneMap = {
    orange: { border: "border-orange-500/40 hover:border-orange-500", text: "text-orange-400" },
    cyan:   { border: "border-cyan-500/40 hover:border-cyan-500",     text: "text-cyan-400"   },
  };
  const styles = toneMap[tone] || toneMap.cyan;
  return (
    <button
      type="button"
      onClick={onPick}
      data-testid={testid}
      className={`text-left rounded-md border ${styles.border} bg-slate-950/50 px-3 py-3 transition-colors flex items-center gap-3`}
    >
      <div className={`${styles.text} font-mono text-xs w-6`}>{idx}.</div>
      <Icon className={`w-5 h-5 ${styles.text}`} />
      <div className="min-w-0">
        <div className="text-sm font-semibold text-slate-100 truncate">
          {file ? file.name : title}
        </div>
        <div className="text-[11px] font-mono text-slate-500 truncate">
          {file ? `${(file.size / 1024).toFixed(0)} KB · click to change` : subtitle}
        </div>
      </div>
    </button>
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
