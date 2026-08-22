import { Building2, ChevronDown, Factory } from "lucide-react";
import type { BridgeUnit } from "./api";
import "./UnitScopeBar.css";

type Props = {
  siteName: string;
  units: BridgeUnit[];
  activeUnit: string;
  onChange: (unitKey: string) => void;
};

export function UnitScopeBar({ siteName, units, activeUnit, onChange }: Props) {
  return (
    <div className="unit-scope-bar" aria-label="Operations scope">
      <div className="unit-scope-site">
        <Building2 size={15} />
        <span>{siteName || "Refinery"}</span>
      </div>
      <div className="unit-scope-divider" />
      <label className="unit-scope-select-wrap">
        <Factory size={15} />
        <select value={activeUnit} onChange={(event) => onChange(event.target.value)} disabled={units.length <= 1}>
          {units.map((unit) => <option key={unit.key} value={unit.key}>{unit.name}</option>)}
        </select>
        <ChevronDown size={14} className="unit-scope-chevron" />
      </label>
      <span className="unit-scope-caption">{units.length} configured unit{units.length === 1 ? "" : "s"}</span>
    </div>
  );
}
