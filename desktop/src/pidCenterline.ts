import type { RoutePoint } from "./pidRouteAudit";
import { auditRasterLegAlignment } from "./pidRouteAudit";

export type CenterlineLeg = {
  index: number; offsetPixels: number; coverage: number; ambiguous: boolean;
  eligible: boolean; start: RoutePoint; end: RoutePoint; reason: string;
};
/** Parallel-stroke suggestions, never a connectivity inference.
 * Each leg is independent: joining adjacent candidates would require
 * corner/intersection analysis and explicit engineering approval.
 */
export function proposeCenterlineLegs(points: RoutePoint[], raster: ImageData): CenterlineLeg[] {
  const alignment = auditRasterLegAlignment(points, raster);
  const {width, height} = raster;
  return alignment.legs.map(leg => {
    const a=points[leg.index-1], b=points[leg.index];
    const dx=(b.x-a.x)*width, dy=(b.y-a.y)*height;
    const length=Math.hypot(dx,dy);
    const nx=length ? -dy/length : 0, ny=length ? dx/length : 0;
    const shiftX=nx*leg.offsetPixels/width, shiftY=ny*leg.offsetPixels/height;
    const eligible=leg.coverage>=0.8 && !leg.ambiguous && Math.abs(leg.offsetPixels)<=8;
    const reason=leg.ambiguous ? "Multiple parallel raster strokes: engineer must resolve" :
      leg.coverage<0.8 ? "Insufficient coherent raster evidence" :
      Math.abs(leg.offsetPixels)>8 ? "Offset exceeds conservative 8 px limit" :
      "Candidate only: check actual pipe and both endpoints";
    return {...leg, eligible, reason,
      start:{x:a.x+shiftX,y:a.y+shiftY},
      end:{x:b.x+shiftX,y:b.y+shiftY}};
  });
}
