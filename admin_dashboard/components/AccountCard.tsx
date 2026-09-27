"use client";

import StatusBadge from "./StatusBadge";

interface AccountCardProps {
  account: {
    login: string | null;
    broker: string | null;
    platform: string;
    account_type: string;
    active: boolean;
    engine_status: string;
    balance?: number;
    equity?: number;
    daily_pnl?: number;
    daily_pnl_pct?: number;
    drawdown?: number;
  };
}

export default function AccountCard({ account }: AccountCardProps) {
  return (
    <div className="bg-raised border border-line rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <div>
          <span className="font-mono text-sm font-semibold text-ink">{account.login || "—"}</span>
          <span className="ml-2 text-[10px] text-ink-muted">{account.platform}</span>
        </div>
        <StatusBadge status={account.engine_status || (account.active ? "active" : "inactive")} />
      </div>
      <div className="grid grid-cols-2 gap-1 text-[10px] text-ink-muted">
        <div>Broker: <span className="text-ink">{account.broker || "—"}</span></div>
        <div>Type: <span className="text-ink">{account.account_type}</span></div>
        {account.balance != null && <div>Balance: <span className="text-ink">${account.balance.toFixed(2)}</span></div>}
        {account.equity != null && <div>Equity: <span className="text-ink">${account.equity.toFixed(2)}</span></div>}
        {account.daily_pnl_pct != null && (
          <div>Daily P&L: <span className={account.daily_pnl_pct >= 0 ? "text-ok" : "text-danger"}>{account.daily_pnl_pct.toFixed(1)}%</span></div>
        )}
        {account.daily_pnl != null && account.daily_pnl_pct == null && (
          <div>Daily P&L: <span className={account.daily_pnl >= 0 ? "text-ok" : "text-danger"}>${account.daily_pnl.toFixed(2)}</span></div>
        )}
        {account.drawdown != null && (
          <div>Drawdown: <span className="text-danger">{account.drawdown.toFixed(1)}%</span></div>
        )}
      </div>
    </div>
  );
}
