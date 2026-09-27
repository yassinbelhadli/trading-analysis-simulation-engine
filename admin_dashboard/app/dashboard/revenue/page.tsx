"use client";

import { useEffect, useState, useCallback } from "react";
import StatCard from "@/components/StatCard";
import PermissionGuard from "@/components/auth/permission_guard";
import { getRevenueAnalytics } from "@/lib/api";
import { Badge, PageHeader } from "@ds/components/ui";

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
    <PermissionGuard roles={["owner"]}>
      <div>
        <PageHeader
          title="Revenue"
          subtitle="Revenue, usage and growth analytics for the platform."
          actions={
            <Badge tone="amber">Owner only</Badge>
          }
        />
        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        {data && (
          <>
            {/* Revenue */}
            <h2 className="text-sm font-semibold mb-3">Revenue</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <StatCard label="MRR" value={Number(data.mrr ?? 0) > 0 ? `$${Number(data.mrr).toFixed(2)}` : "—"}
                color={Number(data.mrr ?? 0) > 0 ? "success" : "default"} />
              <StatCard label="ARR" value={Number(data.arr ?? 0) > 0 ? `$${Number(data.arr).toFixed(2)}` : "—"}
                color={Number(data.arr ?? 0) > 0 ? "success" : "default"} />
              <StatCard label="Total Revenue" value={Number(data.total_revenue ?? 0) > 0 ? `$${Number(data.total_revenue).toFixed(2)}` : "—"}
                color={Number(data.total_revenue ?? 0) > 0 ? "success" : "default"} />
              <StatCard label="New Users (30d)" value={Number(data.new_users_30d ?? 0)} color={Number(data.new_users_30d ?? 0) > 0 ? "success" : "default"} />
            </div>

            {/* Users & Usage */}
            <h2 className="text-sm font-semibold mb-3">Usage</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <StatCard label="Total Users" value={Number(data.total_users ?? 0)} color="default" />
              <StatCard label="Active Subs" value={Number(data.active_subscriptions ?? 0)}
                color={Number(data.active_subscriptions ?? 0) > 0 ? "success" : "default"} />
              <StatCard label="Active Licenses" value={Number(data.active_licenses ?? 0)} color={Number(data.active_licenses ?? 0) > 0 ? "success" : "default"} />
              <StatCard label="Connected Accounts" value={Number(data.connected_accounts ?? 0)}
                color={Number(data.connected_accounts ?? 0) > 0 ? "success" : "default"} />
            </div>

            {/* Churn & Growth */}
            <h2 className="text-sm font-semibold mb-3">Growth & Churn</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
              <StatCard label="Churned (30d)" value={Number(data.churned_30d ?? 0)}
                color={Number(data.churned_30d ?? 0) > 0 ? "error" : "success"} />
              <StatCard label="Total Subs" value={Number(data.total_subscriptions ?? 0)} color="default" />
              <StatCard label="Growth Rate" value={growthRate}
                color={Number(data.new_users_30d ?? 0) > Number(data.churned_30d ?? 0) ? "success" : "default"} />
            </div>

            {/* Plan Distribution */}
            {data.plan_distribution && Object.keys(data.plan_distribution).length > 0 && (
              <div className="bg-raised border border-line rounded-lg p-4">
                <h2 className="text-sm font-semibold mb-3 text-ink">Plan Distribution</h2>
                <div className="space-y-2">
                  {Object.entries(data.plan_distribution as Record<string, number>).map(([plan, count]) => {
                    const pct = data.active_subscriptions > 0 ? ((count as number) / data.active_subscriptions * 100).toFixed(1) : 0;
                    return (
                      <div key={plan} className="flex items-center gap-3 text-xs text-ink">
                        <span className="w-24 capitalize">{plan}</span>
                        <div className="flex-1 bg-input rounded-full h-2">
                          <div className="h-2 rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="w-16 text-right text-ink-muted">{String(count)} ({pct}%)</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}

        {!data && !error && <div className="text-ink-muted text-sm py-8 text-center">Loading analytics...</div>}
      </div>
    </PermissionGuard>
  );
}
