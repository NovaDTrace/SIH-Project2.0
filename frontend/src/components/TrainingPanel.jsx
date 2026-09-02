import { useState } from "react";
import { BrainCircuit, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import { IDS } from "@/constants/testIds";
import { trainModel } from "@/lib/api";
import { toast } from "sonner";

export default function TrainingPanel({ session, trainRes, onTrained }) {
  const [busy, setBusy] = useState(false);
  const [win, setWin] = useState(20);
  const [trees, setTrees] = useState(60);

  const doTrain = async () => {
    if (!session) return toast.error("Load a dataset first");
    setBusy(true);
    try {
      const t = await trainModel(session.session_id, +win, +trees);
      onTrained(t);
      toast.success(`Trained · MAE ${t.mae.toFixed(3)} m/s · R² ${t.r2.toFixed(3)}`);
    } catch (e) { toast.error(e?.message || "Training failed"); }
    finally { setBusy(false); }
  };

  const fiData = (trainRes?.feature_importance || []).slice(0, 8).map((d) => ({
    feature: d.feature, importance: +d.importance.toFixed(4),
  }));
  const vData = trainRes?.velocity_preview?.t?.map((t, i) => ({
    t: +t.toFixed(1), gps: trainRes.velocity_preview.gps_speed[i], ml: trainRes.velocity_preview.ml_pred[i],
  })) ?? [];

  return (
    <div className="card-tactical p-6">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.2em] text-cyan-400">Step 2</div>
          <h3 className="text-xl font-heading font-semibold text-slate-100">ML Velocity Estimator</h3>
        </div>
        <div className="flex items-end gap-3">
          <Field label="Window (samples)">
            <Input data-testid={IDS.windowInput} type="number" min={5} max={100} value={win}
                   onChange={(e) => setWin(e.target.value)}
                   className="w-24 bg-slate-900 border-slate-700 font-mono text-slate-100" />
          </Field>
          <Field label="Trees">
            <Input data-testid={IDS.treesInput} type="number" min={10} max={200} value={trees}
                   onChange={(e) => setTrees(e.target.value)}
                   className="w-24 bg-slate-900 border-slate-700 font-mono text-slate-100" />
          </Field>
          <Button data-testid={IDS.trainBtn} disabled={busy || !session} onClick={doTrain}
                  className="bg-orange-500 hover:bg-orange-400 text-slate-950 font-semibold">
            {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <BrainCircuit className="w-4 h-4 mr-2" />}
            Train RandomForest
          </Button>
        </div>
      </div>

      {!trainRes && (
        <p className="text-slate-400 text-sm">
          Sliding-window IMU statistics → RandomForest regressor predicting instantaneous vehicle
          velocity (m/s). Trained on the first 80% of the trace, validated on the rest.
        </p>
      )}

      {trainRes && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6" data-testid={IDS.trainMetrics}>
          <div className="grid grid-cols-3 gap-3 lg:col-span-3">
            <MetricCard label="MAE" value={`${trainRes.mae.toFixed(3)} m/s`} tone="cyan" />
            <MetricCard label="RMSE" value={`${trainRes.rmse.toFixed(3)} m/s`} tone="orange" />
            <MetricCard label="R²" value={trainRes.r2.toFixed(3)} tone="emerald" />
          </div>

          <div className="lg:col-span-2 h-64">
            <div className="text-xs font-mono uppercase text-slate-400 mb-2">GPS vs ML velocity</div>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={vData} margin={{ top: 4, right: 24, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="t" stroke="#64748b" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line dataKey="gps" stroke="#10b981" dot={false} strokeWidth={1.4} name="GPS truth" />
                <Line dataKey="ml"  stroke="#06b6d4" dot={false} strokeWidth={1.4} name="ML predicted" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="lg:col-span-1 h-64">
            <div className="text-xs font-mono uppercase text-slate-400 mb-2">Top features</div>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={fiData} layout="vertical" margin={{ top: 0, right: 12, left: 60, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis type="number" stroke="#64748b" tick={{ fontSize: 9, fontFamily: "JetBrains Mono" }} />
                <YAxis type="category" dataKey="feature" stroke="#94a3b8"
                       tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} width={90} />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }} />
                <Bar dataKey="importance" fill="#f97316" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-widest text-slate-400">{label}</Label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function MetricCard({ label, value, tone }) {
  const toneMap = { cyan: "text-cyan-400", orange: "text-orange-400", emerald: "text-emerald-400" };
  return (
    <div className="p-4 rounded-md border border-slate-800 bg-slate-950/50">
      <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`stat-value ${toneMap[tone]} text-2xl`}>{value}</div>
    </div>
  );
}
