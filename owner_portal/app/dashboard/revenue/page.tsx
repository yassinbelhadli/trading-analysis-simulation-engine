"use client";

import { useEffect, useState, useCallback } from "react";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import { getRevenueAnalytics } from "@/lib/api";
import { PageHeader, StatCard, Card, Skeleton, EmptyState } from "@ds/components/ui";

function money(v: unknown): string {
  const n = Number(v ?? 0);
  return n > 0 ? `$${n.toFixed(2)}` : "—";
}

function count(v: unknown): string {
  return String(Number(v ?? 0));
}

export default function RevenuePage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await getRevenueAnalytics();
      setData(res);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const growthRate: string = data ? (() => {
    const nu = Number(data.new_users_30d ?? 0);
    const ch = Number(data.churned_30d ?? 0);
    const tu = Number(data.total_users || 1);
    if (nu > 0 && ch > 0) return `${((nu - ch) / tu * 100).toFixed(1)}%`;
    if (nu > 0) return "Growing";
    return "—";
  })() : "";

  return (
    <OwnerPermissionGuard permission="billing.read">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="Revenue"
          subtitle="Canonical revenue surface for the Owner Portal."
        />

        {error && (
          <EmptyState icon="alert-triangle" title="Could not load revenue analytics" description={error} />
        )}

        {!data && !error && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map((i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
        )}

        {data && (
          <>
            <Card title="Revenue" icon="dollar">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <StatCard
                  label="MRR"
                  value={money(data.mrr)}
                  tone={Number(data.mrr ?? 0) > 0 ? "green" : "default"}
                  icon="dollar"
                  mono
                />
                <StatCard
                  label="ARR"
                  value={money(data.arr)}
                  tone={Number(data.arr ?? 0) > 0 ? "green" : "default"}
                  icon="trending-up"
                  mono
                />
                <StatCard
                  label="Total Revenue"
                  value={money(data.total_revenue)}
                  tone={Number(data.total_revenue ?? 0) > 0 ? "green" : "default"}
                  icon="credit-card"
                  mono
                />
                <StatCard
                  label="New Users (30d)"
                  value={count(data.new_users_30d)}
                  tone={Number(data.new_users_30d ?? 0) > 0 ? "green" : "default"}
                  icon="users"
                  mono
                />
              </div>
            </Card>

            <Card title="Usage" icon="activity">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <StatCard label="Total Users" value={count(data.total_users)} icon="users" mono />
                <StatCard
                  label="Active Subscriptions"
                  value={count(data.active_subscriptions)}
                  tone={Number(data.active_subscriptions ?? 0) > 0 ? "green" : "default"}
                  icon="credit-card"
                  mono
                />
                <StatCard
                  label="Active Licenses"
                  value={count(data.active_licenses)}
                  tone={Number(data.active_licenses ?? 0) > 0 ? "green" : "default"}
                  icon="key"
                  mono
                />
                <StatCard
                  label="Connected Accounts"
                  value={count(data.connected_accounts)}
                  tone={Number(data.connected_accounts ?? 0) > 0 ? "blue" : "default"}
                  icon="server"
                  mono
                />
              </div>
            </Card>

            <Card title="Growth & Churn" icon="trending-up">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                <StatCard
                  label="Churned (30d)"
                  value={count(data.churned_30d)}
                  tone={Number(data.churned_30d ?? 0) > 0 ? "red" : "green"}
                  icon="trending-down"
                  mono
                />
                <StatCard
                  label="Total Subscriptions"
                  value={count(data.total_subscriptions)}
                  icon="credit-card"
                  mono
                />
                <StatCard
                  label="Growth Rate"
                  value={growthRate}
                  tone={Number(data.new_users_30d ?? 0) > Number(data.churned_30d ?? 0) ? "green" : "default"}
                  icon="trending-up"
                  mono
                />
              </div>
            </Card>

            {data.plan_distribution && Object.keys(data.plan_distribution).length > 0 && (
              <Card title="Plan Distribution" icon="chart-pie">
                <div className="space-y-2.5">
                  {Object.entries(data.plan_distribution as Record<string, number>).map(([plan, countVal]) => {
                    const pct = data.active_subscriptions > 0
                      ? ((countVal as number) / data.active_subscriptions * 100).toFixed(1)
                      : 0;
                    return (
                      <div key={plan} className="flex items-center gap-3 text-xs">
                        <span className="w-24 capitalize text-ink-soft">{plan}</span>
                        <div className="flex-1 bg-input rounded-full h-2">
                          <div
                            className="h-2 rounded-full bg-brand-500"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="w-16 text-right text-ink-muted font-mono">
                          {String(countVal)} ({pct}%)
                        </span>
                      </div>
                    );
                  })}
                </div>
              </Card>
            )}
          </>
        )}
      </div>
    </OwnerPermissionGuard>
  );
}
