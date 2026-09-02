import { useMemo, useState } from "react";
import Header from "@/components/Header";
import HeroPanel from "@/components/HeroPanel";
import DatasetPanel from "@/components/DatasetPanel";
import TrainingPanel from "@/components/TrainingPanel";
import SimulationPanel from "@/components/SimulationPanel";
import MapPanel from "@/components/MapPanel";
import MetricsPanel from "@/components/MetricsPanel";
import AiSummaryPanel from "@/components/AiSummaryPanel";

export default function Dashboard() {
  const [session, setSession] = useState(null);
  const [trainRes, setTrainRes] = useState(null);
  const [sim, setSim] = useState(null);

  const gpsStatus = useMemo(() => sim ? "BLACKOUT-CAPABLE" : "NOMINAL", [sim]);

  return (
    <>
      <Header sessionId={session?.session_id} gpsStatus={gpsStatus} />
      <main className="max-w-[1600px] mx-auto px-4 md:px-6 lg:px-8 py-8 space-y-8">
        <HeroPanel />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <DatasetPanel session={session} onLoaded={(s) => { setSession(s); setTrainRes(null); setSim(null); }} />
          <TrainingPanel session={session} trainRes={trainRes} onTrained={setTrainRes} />
        </div>

        <SimulationPanel
          session={session}
          canRun={!!trainRes}
          onResult={setSim}
        />

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3 min-h-[560px]">
            <MapPanel session={session} sim={sim} />
          </div>
          <div className="lg:col-span-2 space-y-6">
            <MetricsPanel sim={sim} />
            <AiSummaryPanel session={session} canRun={!!sim && !!trainRes} />
          </div>
        </div>

        <footer className="pt-8 pb-12 text-center text-xs font-mono uppercase tracking-[0.24em] text-slate-500">
          IO-VNBD · Sensor Fusion · EKF · Non-Holonomic Constraints · Map Matching
        </footer>
      </main>
    </>
  );
}
