export type IconName =
  | "activity"
  | "arrow-up-right"
  | "bell"
  | "bolt"
  | "book"
  | "chart"
  | "check"
  | "check-circle"
  | "clock"
  | "close"
  | "database"
  | "gauge"
  | "key"
  | "layers"
  | "mail"
  | "menu"
  | "message"
  | "monitor"
  | "moon"
  | "plus"
  | "send"
  | "shield"
  | "sun"
  | "user"
  | "users";

type IconProps = {
  name: IconName;
  size?: number;
  label?: string;
  className?: string;
};

export default function Icon({ name, size = 20, label, className }: IconProps) {
  const common = {
    className: className ? `icon ${className}` : "icon",
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    role: label ? "img" : undefined,
    "aria-label": label,
    "aria-hidden": label ? undefined : true,
  };

  return (
    <svg {...common}>
      {name === "activity" && <><path d="M3 12h4l2.2-7 4.1 14 2.2-7H21" /></>}
      {name === "arrow-up-right" && <><path d="M7 17 17 7" /><path d="M7 7h10v10" /></>}
      {name === "bell" && <><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></>}
      {name === "bolt" && <path d="M13 2 3 14h7l-1 8 10-12h-7l1-8Z" />}
      {name === "book" && <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" /></>}
      {name === "chart" && <><path d="M3 3v16a2 2 0 0 0 2 2h16" /><path d="m7 14 4-4 3 3 5-6" /></>}
      {name === "check" && <path d="m5 12 4 4L19 6" />}
      {name === "check-circle" && <><circle cx="12" cy="12" r="9" /><path d="m8.5 12 2.5 2.5 5-5" /></>}
      {name === "clock" && <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 3" /></>}
      {name === "close" && <><path d="m6 6 12 12" /><path d="m18 6-12 12" /></>}
      {name === "database" && <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></>}
      {name === "gauge" && <><circle cx="12" cy="13" r="2" /><path d="M12 11V5" /><path d="M5 13H3" /><path d="M21 13h-2" /><path d="M6 7l1.5 1.5" /><path d="M18 7l-1.5 1.5" /></>}
      {name === "key" && <><circle cx="7.5" cy="15.5" r="4.5" /><path d="m11 12 9-9" /><path d="m16 7 3 3" /><path d="m18 5 2 2" /></>}
      {name === "layers" && <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 12 9 5 9-5" /><path d="m3 16 9 5 9-5" /></>}
      {name === "mail" && <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>}
      {name === "menu" && <><path d="M4 7h16" /><path d="M4 12h16" /><path d="M4 17h16" /></>}
      {name === "message" && <><path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" /></>}
      {name === "monitor" && <><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8" /><path d="M12 16v4" /></>}
      {name === "moon" && <path d="M20.5 15.5A8.5 8.5 0 0 1 8.5 3.5 8.5 8.5 0 1 0 20.5 15.5Z" />}
      {name === "plus" && <><path d="M12 5v14" /><path d="M5 12h14" /></>}
      {name === "send" && <><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></>}
      {name === "shield" && <><path d="M12 3 19 6v5c0 4.5-2.8 8-7 10-4.2-2-7-5.5-7-10V6l7-3Z" /><path d="m9 12 2 2 4-4" /></>}
      {name === "sun" && <><circle cx="12" cy="12" r="4" /><path d="M12 2v2" /><path d="M12 20v2" /><path d="m4.93 4.93 1.41 1.41" /><path d="m17.66 17.66 1.41 1.41" /><path d="M2 12h2" /><path d="M20 12h2" /><path d="m6.34 17.66-1.41 1.41" /><path d="m19.07 4.93-1.41 1.41" /></>}
      {name === "user" && <><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></>}
      {name === "users" && <><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></>}
    </svg>
  );
}
