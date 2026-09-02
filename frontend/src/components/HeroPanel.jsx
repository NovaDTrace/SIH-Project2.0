import { Radio, Map, Cpu, ShieldCheck } from "lucide-react";

const stat = "flex items-start gap-3 p-4 rounded-md bg-slate-900/60 border border-slate-800";

export default function HeroPanel() {
  return (
    <section className="relative overflow-hidden rounded-lg border border-slate-800 grid-overlay">
      <div
        className="absolute inset-0 opacity-30 pointer-events-none"
        style={{
          backgroundImage:
            "url(https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA2MTJ8MHwxfHNlYXJjaHwxfHxzYXRlbGxpdGUlMjBlYXJ0aCUyMHNwYWNlJTIwdGVjaHxlbnwwfHx8fDE3ODc4NDI4NTN8MA&ixlib=rb-4.1.0&q=85)",
          backgroundSize: "cover",
          backgroundPosition: "center",
          maskImage: "linear-gradient(to bottom, rgba(0,0,0,0.7), transparent 80%)",
          WebkitMaskImage: "linear-gradient(to bottom, rgba(0,0,0,0.7), transparent 80%)",
        }}
      />
      <div className="relative p-6 md:p-10">
        <div className="text-xs font-mono uppercase tracking-[0.28em] text-cyan-400 mb-3">
          Mission Brief · Dead Reckoning for GPS-Denied Navigation
        </div>
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-heading font-extrabold text-slate-100 leading-[1.05]">
          When the satellites go dark, <br />
          <span className="text-cyan-400">the phone still knows the way.</span>
        </h1>
        <p className="mt-5 max-w-3xl text-slate-300 leading-relaxed">
          An end-to-end IO-VNBD pipeline: smartphone accelerometer, gyroscope,
          magnetometer and GPS feed a Random Forest velocity estimator, an
          Inertial Navigation System integrator, and an Extended Kalman Filter
          with non-holonomic constraints — targeting less than <span className="text-cyan-400 font-semibold">10% drift</span> across
          a full GPS blackout.
        </p>

        <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className={stat}>
            <Radio className="w-5 h-5 text-cyan-400 mt-1" />
            <div>
              <div className="text-xs font-mono uppercase tracking-widest text-slate-400">Sensors</div>
              <div className="text-slate-100 font-semibold">Accel · Gyro · Mag · GPS</div>
            </div>
          </div>
          <div className={stat}>
            <Cpu className="w-5 h-5 text-orange-400 mt-1" />
            <div>
              <div className="text-xs font-mono uppercase tracking-widest text-slate-400">ML Model</div>
              <div className="text-slate-100 font-semibold">RandomForest velocity</div>
            </div>
          </div>
          <div className={stat}>
            <ShieldCheck className="w-5 h-5 text-emerald-400 mt-1" />
            <div>
              <div className="text-xs font-mono uppercase tracking-widest text-slate-400">Fusion</div>
              <div className="text-slate-100 font-semibold">EKF + NHC</div>
            </div>
          </div>
          <div className={stat}>
            <Map className="w-5 h-5 text-purple-400 mt-1" />
            <div>
              <div className="text-xs font-mono uppercase tracking-widest text-slate-400">Map</div>
              <div className="text-slate-100 font-semibold">OpenStreetMap · Dark</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
