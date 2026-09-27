"use client";

import { useEffect, useState } from "react";
import Button from "@/components/primitives/Button";
import Icon from "@/components/primitives/Icon";

type WebsiteTheme = "dark" | "light";

export default function ThemeToggle() {
  const [theme, setTheme] = useState<WebsiteTheme>("dark");

  useEffect(() => {
    const saved = window.localStorage.getItem("website-theme");
    const nextTheme: WebsiteTheme = saved === "light" ? "light" : "dark";
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
  }, []);

  const toggle = () => {
    const nextTheme: WebsiteTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem("website-theme", nextTheme);
  };

  return (
    <Button
      className="theme-toggle button--icon"
      variant="ghost"
      size="medium"
      onClick={toggle}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
    >
      <Icon name={theme === "dark" ? "sun" : "moon"} size={18} />
    </Button>
  );
}
