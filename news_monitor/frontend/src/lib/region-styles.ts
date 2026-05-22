export function getRegionBorderClass(regionName: string): string {
  const key = regionName.toLowerCase();
  if (key.includes("ticker")) return "border-s-teal-500";
  if (key.includes("headline")) return "border-s-amber-500";
  if (key.includes("side")) return "border-s-purple-500";
  return "border-s-primary";
}

export function getRegionBadgeVariant(
  regionName: string
): "default" | "warning" | "secondary" {
  const key = regionName.toLowerCase();
  if (key.includes("headline")) return "warning";
  if (key.includes("side")) return "secondary";
  return "default";
}
