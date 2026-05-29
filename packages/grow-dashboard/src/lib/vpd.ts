/**
 * Vapor Pressure Deficit utilities for grow automation.
 * VPD = SVP(T_leaf) - (RH/100) * SVP(T_air)
 */

// Magnus-Tetens Formel fuer Saturation Vapor Pressure
export function calculateSVP(tempC: number): number {
  return 0.6108 * Math.exp((17.27 * tempC) / (tempC + 237.3));
}

// VPD in kPa berechnen
// leafOffset: typisch -2°C (Blatt kuehler als Luft)
export function calculateVPD(tempC: number, rhPercent: number, leafOffset: number = -2): number {
  const svpLeaf = calculateSVP(tempC + leafOffset);
  const svpAir = calculateSVP(tempC);
  const vpd = svpLeaf - (rhPercent / 100) * svpAir;
  return Math.max(0, Math.round(vpd * 1000) / 1000);
}

// Rueckrechnung: welche RH braucht man fuer ein VPD-Ziel bei gegebener Temperatur?
export function requiredRH(tempC: number, targetVPD: number, leafOffset: number = -2): number {
  const svpLeaf = calculateSVP(tempC + leafOffset);
  const svpAir = calculateSVP(tempC);
  if (svpAir === 0) return 100;
  const rh = ((svpLeaf - targetVPD) / svpAir) * 100;
  return Math.max(0, Math.min(100, Math.round(rh * 10) / 10));
}

// VPD Zone Klassifizierung
export type VPDZone = "low" | "veg" | "flower" | "high";

export const VPD_ZONES: Record<VPDZone, [number, number]> = {
  low: [0, 0.4],
  veg: [0.4, 1.2],
  flower: [1.2, 1.6],
  high: [1.6, Infinity],
};

export function vpdZone(vpd: number): VPDZone {
  if (vpd < 0.4) return "low";
  if (vpd < 1.2) return "veg";
  if (vpd < 1.6) return "flower";
  return "high";
}

// VPD Status fuer UI (ok/warn/crit)
export function vpdStatus(vpd: number | null): "ok" | "warn" | "crit" {
  if (vpd === null) return "crit";
  if (vpd >= 0.4 && vpd <= 1.6) return "ok";
  if (vpd > 1.6 || vpd < 0.2) return "crit";
  return "warn";
}
