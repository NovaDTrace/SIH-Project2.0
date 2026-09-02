import { TrendingDown, Ruler, AlertTriangle, ShieldCheck, Timer, Gauge } from "lucide-react";
import { IDS } from "@/constants/testIds";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceArea, Legend } from "recharts";

export default function MetricsPanel({ sim }) {
  if (!sim) {
    return (
      <div className="card-tactical p-6">
        <div className="text-xs font-mono uppercase tracking-[0.2em] text-cyan-400">Metrics</div>
        <h3 className="text-xl font-heading font-semibold text-slate-100">Drift & Performance</h3>
        <p className="mt-2 text-slate-400 text-sm">
          Run the simulation to populate drift %, RMSE and 10 Hz playback here.
        </p>
      </div>
    );
  }

  const m = sim.metrics;
  const vs = sim.velocity_series;
  const vData = vs.t.map((t, i) => ({
    t: +t.toFixed(1), gps: vs.gps[i], ml: vs.ml[i], fused: vs.fused[i], black: vs.blackout_flag[i],
  }));
  const blackoutT = { start: m.blackout_start_s, end: m.blackout_end_s };
  const met = m.meets_isro_target;

  return (
    <div className="card-tactical p-6" data-testid="metrics-panel">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.2em] text-cyan-400">Metrics</div>
          <h3 className="text-xl font-heading font-semibold text-slate-100">Drift & Performance</h3>
        </div>
        <div
          data-testid={IDS.metricIsroTarget}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-md border ${
            met ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                 : "border-red-500/40 bg-red-500/10 text-red-300"
          }`}
        >
          <ShieldCheck className="w-4 h-4" />
          <span className="font-mono text-xs">
            {met ? "ISRO TARGET MET (<10% drift)" : "ISRO TARGET NOT MET"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <MetricStat testid={IDS.metricDriftPct} icon={TrendingDown}
                    label="Fused drift %" value={`${m.fused_drift_pct.toFixed(2)}%`} tone="cyan" />
        <MetricStat testid={IDS.metricFinal} icon={Ruler}
                    label="Fused final" value={`${m.fused_final_drift_m.toFixed(1)} m`} tone="cyan" />
        <MetricStat testid={IDS.metricRmse} icon={Gauge}
                    label="Fused RMSE" value={`${m.fused_rmse_m.toFixed(1)} m`} tone="cyan" />
        <MetricStat icon={AlertTriangle} label="INS drift %"
                    value={`${m.ins_drift_pct.toFixed(1)}%`} tone="purple" />
        <MetricStat icon={Ruler} label="INS final"
                    value={`${m.ins_final_drift_m.toFixed(1)} m`} tone="purple" />
        <MetricStat icon={Timer} label="Blackout"
                    value={`${m.blackout_duration_s.toFixed(0)} s`} tone="orange" />
      </div>

      <div className="mt-6 h-60">
        <div className="text-xs font-mono uppercase text-slate-400 mb-2">Velocity streams</div>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={vData} margin={{ top: 4, right: 24, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']}
                   stroke="#64748b" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
            <YAxis stroke="#64748b" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
            <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <ReferenceArea x1={blackoutT.start} x2={blackoutT.end}
                            fill="#ef4444" fillOpacity={0.12} stroke="#ef4444" strokeOpacity={0.4} />
            <Line dataKey="gps"   stroke="#f97316" dot={false} strokeWidth={1.3} name="GPS truth" />
            <Line dataKey="ml"    stroke="#06b6d4" dot={false} strokeWidth={1.3} name="ML" />
            <Line dataKey="fused" stroke="#10b981" dot={false} strokeWidth={1.6} name="Fused" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function MetricStat({ icon: Icon, label, value, tone, testid }) {
  const toneMap = {
    cyan: "text-cyan-400",
    orange: "text-orange-400",
    purple: "text-purple-400",
    emerald: "text-emerald-400",
  };
  return (
    <div data-testid={testid} className="p-3 rounded-md border border-slate-800 bg-slate-950/50">
      <div className="flex items-center gap-1.5">
        <Icon className={`w-3.5 h-3.5 ${toneMap[tone]}`} />
        <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</div>
      </div>
      <div className={`stat-value ${toneMap[tone]} text-xl mt-1`}>{value}</div>
    </div>
  );
}
