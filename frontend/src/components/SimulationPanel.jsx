import { useEffect, useState } from "react";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Play, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { IDS } from "@/constants/testIds";
import { simulate } from "@/lib/api";
import { toast } from "sonner";

export default function SimulationPanel({ session, canRun, onResult }) {
  const [busy, setBusy] = useState(false);
  const maxT = session?.duration_s || 100;
  const [range, setRange] = useState([Math.round(0.3 * maxT), Math.round(0.7 * maxT)]);

  useEffect(() => {
    const m = session?.duration_s || 100;
    setRange([Math.round(0.3 * m), Math.round(0.7 * m)]);
  }, [session?.session_id]);

  const doRun = async () => {
    if (!canRun) return toast.error("Train the ML model first");
    setBusy(true);
    try {
      const r = await simulate(session.session_id, range[0], range[1]);
      onResult(r);
      toast.success(`Fused drift: ${r.metrics.fused_drift_pct.toFixed(2)}%`);
    } catch (e) { toast.error(e?.message || "Simulation failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="card-tactical p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.2em] text-cyan-400">Step 3</div>
          <h3 className="text-xl font-heading font-semibold text-slate-100">GPS Blackout Simulation</h3>
        </div>
        <Button data-testid={IDS.simRunBtn} disabled={busy || !canRun} onClick={doRun}
                className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold">
          {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
          Run Dead Reckoning
        </Button>
      </div>

      <p className="text-slate-400 text-sm mb-5">
        Pick a time window during which we cut GPS. INS + EKF + ML velocity + non-holonomic
        constraint take over, and the fused trajectory is scored against ground truth.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <Label className="text-[10px] font-mono uppercase tracking-widest text-slate-400">
            Blackout start (s)
          </Label>
          <Input
            data-testid={IDS.simStartInput}
            type="number" min={0} max={maxT} step={1}
            value={Math.round(range[0])}
            onChange={(e) => setRange([+e.target.value, range[1]])}
            className="mt-1 bg-slate-900 border-slate-700 font-mono text-slate-100"
          />
        </div>
        <div>
          <Label className="text-[10px] font-mono uppercase tracking-widest text-slate-400">
            Blackout end (s)
          </Label>
          <Input
            data-testid={IDS.simEndInput}
            type="number" min={0} max={maxT} step={1}
            value={Math.round(range[1])}
            onChange={(e) => setRange([range[0], +e.target.value])}
            className="mt-1 bg-slate-900 border-slate-700 font-mono text-slate-100"
          />
        </div>
      </div>

      <div className="px-2 py-4 rounded-md border border-slate-800 bg-slate-950/50">
        <Slider
          min={0} max={Math.round(maxT)} step={1}
          value={range}
          onValueChange={setRange}
        />
        <div className="mt-3 flex justify-between text-[11px] font-mono text-slate-400">
          <span>0s</span>
          <span className="text-red-400">
            BLACKOUT · {(range[1] - range[0]).toFixed(0)}s
          </span>
          <span>{Math.round(maxT)}s</span>
        </div>
      </div>
    </div>
  );
}
