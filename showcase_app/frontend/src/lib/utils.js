import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

// Backend ExecutionTracker stores UTC timestamps as naive ISO strings
// (tzinfo stripped). new Date() would parse those as local time, producing
// negative durations and wrong-timezone displays for anyone not on UTC.
// Treat a bare ISO string with no trailing 'Z' / offset as UTC.
export function parseBackendTimestamp(value) {
  if (!value) return new Date(NaN);
  if (typeof value !== 'string') return new Date(value);
  const hasTZ = /[zZ]|[+-]\d{2}:?\d{2}$/.test(value);
  return new Date(hasTZ ? value : `${value}Z`);
}
