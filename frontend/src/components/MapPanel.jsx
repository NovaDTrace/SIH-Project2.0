import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, useMap } from "react-leaflet";
import { IDS } from "@/constants/testIds";
import { useEffect, useMemo } from "react";
import L from "leaflet";

const styles = {
  gt:    { color: "#f97316", weight: 4, opacity: 0.95 },
  ins:   { color: "#a855f7", weight: 2, opacity: 0.7, dashArray: "6 6" },
  fused: { color: "#06b6d4", weight: 3, opacity: 0.95 },
};

function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (!points || points.length < 2) return;
    const b = L.latLngBounds(points);
    map.fitBounds(b, { padding: [30, 30], animate: false });
  }, [points, map]);
  return null;
}

export default function MapPanel({ session, sim }) {
  const center = useMemo(() => {
    if (session) return [session.lat0, session.lon0];
    return [52.4017, -1.5053];
  }, [session]);

  const traj = sim?.trajectories;
  const gt = traj?.ground_truth || [];
  const ins = traj?.ins_raw || [];
  const fused = traj?.fused || [];
  const gtLabel = session?.has_vbox ? "VBOX GT" : "Phone-GPS GT";

  return (
    <div className="card-tactical p-3 h-full flex flex-col">
      <div className="px-3 pt-2 pb-3 flex items-center justify-between">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.2em] text-cyan-400">Trajectory Map</div>
          <h3 className="text-lg font-heading font-semibold text-slate-100">
            {gtLabel} vs INS-only vs Fused
          </h3>
        </div>
        <div className="flex flex-wrap gap-3 text-[11px] font-mono">
          <Legend color="#f97316" label={gtLabel} />
          <Legend color="#a855f7" dashed label="INS raw" />
          <Legend color="#06b6d4" label="Fused (EKF+ML)" />
        </div>
      </div>

      <div className="flex-1 min-h-[480px] rounded-md overflow-hidden border border-slate-800"
           data-testid={IDS.mapContainer}>
        <MapContainer center={center} zoom={13} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {gt.length > 1 && <Polyline positions={gt} pathOptions={styles.gt} />}
          {ins.length > 1 && <Polyline positions={ins} pathOptions={styles.ins} />}
          {fused.length > 1 && <Polyline positions={fused} pathOptions={styles.fused} />}
          <FitBounds points={gt.length > 1 ? gt : []} />

          {gt[0] && (
            <CircleMarker center={gt[0]} radius={6} pathOptions={{ color: "#10b981", fillColor: "#10b981", fillOpacity: 1 }}>
              <Tooltip permanent direction="top" offset={[0, -8]}
                       className="!bg-slate-950 !text-cyan-400 !border !border-slate-700 !font-mono !text-xs">
                START
              </Tooltip>
            </CircleMarker>
          )}
          {gt.length > 1 && (
            <CircleMarker center={gt[gt.length - 1]} radius={6}
                          pathOptions={{ color: "#f97316", fillColor: "#f97316", fillOpacity: 1 }}>
              <Tooltip permanent direction="top" offset={[0, -8]}
                       className="!bg-slate-950 !text-orange-400 !border !border-slate-700 !font-mono !text-xs">
                END
              </Tooltip>
            </CircleMarker>
          )}
          {fused.length > 1 && (
            <CircleMarker center={fused[fused.length - 1]} radius={5}
                          pathOptions={{ color: "#06b6d4", fillColor: "#06b6d4", fillOpacity: 1 }}>
              <Tooltip direction="bottom" offset={[0, 8]}
                       className="!bg-slate-950 !text-cyan-400 !border !border-slate-700 !font-mono !text-xs">
                Fused final
              </Tooltip>
            </CircleMarker>
          )}
        </MapContainer>
      </div>
    </div>
  );
}

function Legend({ color, label, dashed }) {
  return (
    <span className="flex items-center gap-1.5 text-slate-300">
      <span style={{
        width: 22, height: 3, background: color, display: "inline-block",
        borderRadius: 2, boxShadow: `0 0 6px ${color}55`,
        backgroundImage: dashed ? `repeating-linear-gradient(90deg, ${color} 0 4px, transparent 4px 8px)` : undefined,
      }} />
      {label}
    </span>
  );
}
