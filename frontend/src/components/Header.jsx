import { Satellite, Activity } from "lucide-react";

export default function Header({ sessionId, gpsStatus = "NOMINAL" }) {
  return (
    <header className="sticky top-0 z-40 backdrop-blur-xl bg-slate-950/80 border-b border-slate-800">
      <div className="max-w-[1600px] mx-auto px-6 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Satellite className="w-6 h-6 text-cyan-400" strokeWidth={1.5} />
            <span className="absolute -bottom-0.5 -right-0.5 pulse-dot" />
          </div>
          <div className="leading-tight">
            <div className="text-xs font-mono uppercase tracking-[0.24em] text-cyan-400">
              ISRO / IO-VNBD
            </div>
            <div className="font-heading text-lg font-bold text-slate-100">
              Intelligent Dead Reckoning Console
            </div>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-6 text-xs font-mono uppercase tracking-widest">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-400" />
            <span className="text-slate-400">SESSION</span>
            <span className="text-slate-200" data-testid="session-id-label">
              {sessionId || "—"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${
              gpsStatus === "BLACKOUT" ? "bg-red-500" : "bg-emerald-400"
            }`} />
            <span className="text-slate-400">GPS</span>
            <span className="text-slate-200">{gpsStatus}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
