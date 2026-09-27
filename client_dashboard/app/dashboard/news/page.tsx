"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getUpcomingCalendar,
  getRecentNews,
  getClientSettings,
  type CalendarEvent,
} from "@/lib/api";
import {
  PageHeader,
  Card,
  Badge,
  EmptyState,
  Skeleton,
  SelectField,
  SectionLabel,
  Table,
  Td,
  Button,
} from "@ds/components/ui";
import { Icon, type IconName } from "@ds/components/Icon";
import { formatUserDateTime, DEFAULT_TIMEZONE, getTimezoneLabel } from "@/lib/timezone";
import { useLocale } from "@/components/LocaleContext";

const IMPACT_TONE: Record<string, "red" | "amber" | "gray"> = {
  HIGH: "red",
  MEDIUM: "amber",
  LOW: "gray",
};

const IMPACT_ICON: Record<string, IconName> = {
  HIGH: "alert-triangle",
  MEDIUM: "info",
  LOW: "calendar",
};

function safeValue(v: string | null | undefined): string {
  if (v == null || v === "" || v === "NaN" || v === "nan" || v === "null" || v === "undefined") return "—";
  return v;
}

export default function NewsPage() {
  const { t } = useLocale();
  const [upcoming, setUpcoming] = useState<CalendarEvent[] | null>(null);
  const [recent, setRecent] = useState<CalendarEvent[] | null>(null);
  const [error, setError] = useState("");
  const [days, setDays] = useState("7");
  const [impact, setImpact] = useState("HIGH,MEDIUM");
  const [reloadKey, setReloadKey] = useState(0);
  const [userTimezone, setUserTimezone] = useState(DEFAULT_TIMEZONE);

  useEffect(() => {
    getClientSettings()
      .then((s) => { if (s.timezone) setUserTimezone(s.timezone); })
      .catch(() => {});
  }, []);

  const formatTime = (iso: string | null): string => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return formatUserDateTime(d, userTimezone);
  };

  const load = useCallback(async () => {
    setError("");
    try {
      const [calResult, recResult] = await Promise.allSettled([
        getUpcomingCalendar(Number(days), impact),
        getRecentNews(48),
      ]);
      if (calResult.status === "fulfilled") {
        setUpcoming(calResult.value.items);
      } else {
        setUpcoming([]);
      }
      if (recResult.status === "fulfilled") {
        setRecent(recResult.value.items);
      } else {
        setRecent([]);
      }
      // Show error only if both failed; partial success is acceptable
      if (calResult.status === "rejected" && recResult.status === "rejected") {
        setError(calResult.reason instanceof Error ? calResult.reason.message : t("news.loadError"));
      } else if (calResult.status === "rejected") {
        setError(calResult.reason instanceof Error ? calResult.reason.message : t("news.loadUpcomingError"));
      } else if (recResult.status === "rejected") {
        setError(recResult.reason instanceof Error ? recResult.reason.message : t("news.loadRecentError"));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t("news.loadError"));
      setUpcoming([]);
      setRecent([]);
    }
  }, [days, impact, reloadKey, t]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageHeader
        title={t("news.title")}
        subtitle={t("news.subtitle", { tz: getTimezoneLabel(userTimezone) })}
        actions={
          <Button variant="secondary" icon="refresh" onClick={() => setReloadKey((k) => k + 1)}>
            {t("news.refresh")}
          </Button>
        }
      />

      {error && (
        <div className="mb-4 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-[13px] text-danger">
          {error}
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <SelectField label={t("news.window")} value={days} onChange={(e) => setDays(e.target.value)}>
          <option value="3">{t("news.next3")}</option>
          <option value="7">{t("news.next7")}</option>
          <option value="14">{t("news.next14")}</option>
          <option value="30">{t("news.next30")}</option>
        </SelectField>
        <SelectField label={t("news.impact")} value={impact} onChange={(e) => setImpact(e.target.value)}>
          <option value="HIGH,MEDIUM">{t("news.highMedium")}</option>
          <option value="HIGH">{t("news.highOnly")}</option>
          <option value="HIGH,MEDIUM,LOW">{t("news.all")}</option>
        </SelectField>
      </div>

      <Card
        title={t("news.upcoming")}
        subtitle={t("news.upcomingSub")}
        icon="calendar"
      >
        {upcoming === null ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : upcoming.length === 0 ? (
          <EmptyState
            icon="calendar"
            title={t("news.noUpcoming")}
            description={t("news.noUpcomingDesc")}
          />
        ) : (
          <Table
            columns={[
              t("news.colTime"),
              t("news.colCurrency"),
              t("news.colEvent"),
              t("news.impact"),
              t("news.colForecast"),
              t("news.colPrevious"),
              t("news.colActual"),
            ]}
          >
            {upcoming.map((ev) => (
              <tr key={ev.news_id}>
                <Td mono>{formatTime(ev.time)}</Td>
                <Td>
                  <Badge>{ev.currency}</Badge>
                </Td>
                <Td>{ev.event}</Td>
                <Td>
                  <Badge tone={IMPACT_TONE[ev.impact] ?? "gray"}>
                    <span className="inline-flex items-center gap-1">
                      <Icon name={IMPACT_ICON[ev.impact] ?? "calendar"} className="h-3 w-3" />
                      {ev.impact}
                    </span>
                  </Badge>
                </Td>
                <Td>{safeValue(ev.forecast)}</Td>
                <Td>{safeValue(ev.previous)}</Td>
                <Td>{safeValue(ev.actual)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <div className="mt-6">
        <SectionLabel>{t("news.recentlyReleased")}</SectionLabel>
        <Card title={t("news.last48")} subtitle={t("news.last48Sub")} icon="newspaper">
          {recent === null ? (
            <Skeleton className="h-10 w-full" />
          ) : recent.length === 0 ? (
            <EmptyState
              icon="newspaper"
              title={t("news.nothingRecent")}
              description={t("news.nothingRecentDesc")}
            />
          ) : (
            <Table
              columns={[
                t("news.colTime"),
                t("news.colCurrency"),
                t("news.colEvent"),
                t("news.impact"),
                t("news.colActual"),
                t("news.colForecast"),
                t("news.colPrevious"),
              ]}
            >
              {recent.map((ev) => (
                <tr key={ev.news_id}>
                  <Td mono>{formatTime(ev.time)}</Td>
                  <Td>
                    <Badge>{ev.currency}</Badge>
                  </Td>
                  <Td>{ev.event}</Td>
                  <Td>
                    <Badge tone={IMPACT_TONE[ev.impact] ?? "gray"}>
                      <span className="inline-flex items-center gap-1">
                        <Icon name={IMPACT_ICON[ev.impact] ?? "calendar"} className="h-3 w-3" />
                        {ev.impact}
                      </span>
                    </Badge>
                  </Td>
                  <Td>
                    <span className="font-medium text-ink">{safeValue(ev.actual)}</span>
                  </Td>
                  <Td>{safeValue(ev.forecast)}</Td>
                  <Td>{safeValue(ev.previous)}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      </div>
    </>
  );
}
