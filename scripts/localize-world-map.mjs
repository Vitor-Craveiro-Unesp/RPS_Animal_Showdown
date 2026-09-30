import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

// Regenerate the four displayed copies from the public-domain SVG at world.ie/map/.
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(root, "apps/frontend/public/maps/world-map-countries.svg"), "utf8");
const english = new Intl.DisplayNames(["en"], { type: "region" });
const regionCodes = new Map();
for (let first = 65; first <= 90; first += 1) {
  for (let second = 65; second <= 90; second += 1) {
    const code = String.fromCharCode(first, second);
    const name = english.of(code);
    if (name && name !== code) regionCodes.set(name, code);
  }
}

const aliases = {
  "United States of America": "US",
  "Dem. Rep. Congo": "CD",
  "S. Sudan": "SS",
  "Côte d'Ivoire": "CI",
  "Turkey": "TR",
  "Russia": "RU",
  "North Korea": "KP",
  "South Korea": "KR",
  "Myanmar": "MM",
  "Solomon Is.": "SB",
};
const labelPattern = /(<text\b[^>]*>)([^<]*)(<\/text>)/g;
// Retain outlines, but display only sovereign-country names on the playable map.
const nonCountryLabels = new Set([
  "Antarctica",
  "Greenland",
  "Falkland Is.",
  "Fr. S. Antarctic Lands",
  "S. Geo. and the Is.",
  "New Caledonia",
  "PR",
  "EH",
]);
const visibleSource = source.replace(labelPattern, (match, _open, label) => nonCountryLabels.has(label) ? "" : match);
const labels = [...visibleSource.matchAll(labelPattern)].map((match) => match[2]);
const unmatched = labels.filter((label) => label.length > 2 && !aliases[label] && !regionCodes.has(label));
if (unmatched.length) throw new Error(`Unmapped country labels: ${unmatched.join(", ")}`);

writeFileSync(resolve(root, "apps/frontend/public/maps/world-map-countries-en.svg"), visibleSource);
for (const locale of ["pt-BR", "zh-CN", "ar"]) {
  const localNames = new Intl.DisplayNames([locale], { type: "region" });
  const translated = visibleSource.replace(labelPattern, (_match, open, label, close) => {
    const code = aliases[label] ?? (label.length === 2 ? label : regionCodes.get(label));
    const name = label.length === 2 ? label : localNames.of(code);
    const safe = name.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
    return `${locale === "ar" ? open.replace("<text ", '<text direction="rtl" ') : open}${safe}${close}`;
  });
  writeFileSync(resolve(root, `apps/frontend/public/maps/world-map-countries-${locale}.svg`), translated);
}
