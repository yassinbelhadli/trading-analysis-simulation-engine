"use client";

/**
 * Compact global preference bar: Language / Currency / Timezone.
 * Rendered in the Client Dashboard topbar. All values persist to the backend.
 */

import { useLocale, LANGUAGES, CURRENCIES } from "@/components/LocaleContext";
import { TIMEZONE_REGIONS, getTimezoneLabel } from "@/lib/timezone";

const selectCls =
  "h-7 rounded-md bg-input border border-line px-1.5 text-[11px] text-ink focus:outline-none focus:border-brand-500 max-w-[130px]";

export default function LocaleBar() {
  const { language, currency, timezone, setLanguage, setCurrency, setTimezone } = useLocale();

  return (
    <div className="flex items-center gap-1.5" aria-label="Global preferences">
      <select
        aria-label="Language"
        className={selectCls}
        value={language}
        onChange={(e) => setLanguage(e.target.value as (typeof LANGUAGES)[number])}
      >
        {LANGUAGES.map((l) => (
          <option key={l} value={l}>
            {l}
          </option>
        ))}
      </select>

      <select
        aria-label="Currency"
        className={selectCls}
        value={currency}
        onChange={(e) => setCurrency(e.target.value as (typeof CURRENCIES)[number])}
      >
        {CURRENCIES.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>

      <select
        aria-label="Timezone"
        className={selectCls}
        value={timezone}
        onChange={(e) => setTimezone(e.target.value)}
        title={getTimezoneLabel(timezone)}
      >
        {TIMEZONE_REGIONS.map((region) => (
          <optgroup key={region.region} label={region.region}>
            {region.timezones.map((tz) => (
              <option key={tz.iana} value={tz.iana}>
                {tz.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </div>
  );
}