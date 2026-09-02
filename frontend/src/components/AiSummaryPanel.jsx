import { useState } from "react";
import { Sparkles, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { IDS } from "@/constants/testIds";
import { aiSummary } from "@/lib/api";
import { toast } from "sonner";

export default function AiSummaryPanel({ session, canRun }) {
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");

  const doRun = async () => {
    if (!canRun) return toast.error("Run training and simulation first");
    setBusy(true);
    try {
      const r = await aiSummary(session.session_id);
      setText(r.summary || "");
    } catch (e) { toast.error(e?.message || "AI summary failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="card-tactical p-6" data-testid={IDS.aiSummaryCard}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.2em] text-cyan-400">Mission Report</div>
          <h3 className="text-xl font-heading font-semibold text-slate-100">AI Analysis</h3>
        </div>
        <Button data-testid={IDS.aiSummaryBtn} onClick={doRun} disabled={busy || !canRun}
                className="bg-purple-500 hover:bg-purple-400 text-slate-950 font-semibold">
          {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
          Generate Report
        </Button>
      </div>

      <div data-testid="ai-summary-output"
           className="rounded-md border border-slate-800 bg-slate-950/70 p-4 font-mono text-sm text-slate-300 min-h-[160px] whitespace-pre-wrap leading-relaxed">
        {text ? text : (
          <span className="text-slate-500">
            {"> await run.simulation && run.training\n> generate mission_report --model claude-sonnet-4.5\n"}
          </span>
        )}
      </div>
    </div>
  );
}
