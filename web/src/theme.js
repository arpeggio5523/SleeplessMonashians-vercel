// web/src/theme.js - light / dark theme.
//
// The theme is a "dark" class on <html>; src/dark.css does the rest. The
// choice is remembered; a first visit always starts in light mode.
// index.html applies the saved theme before React loads, so the page never
// flashes light first.

import { useCallback, useEffect, useState } from "react";

const KEY = "sdoc.theme";

function initialTheme() {
  try {
    const saved = window.localStorage.getItem(KEY);
    if (saved === "dark" || saved === "light") return saved;
  } catch {
    /* storage unavailable */
  }
  return "light";
}

export function useTheme() {
  const [theme, setTheme] = useState(initialTheme);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      window.localStorage.setItem(KEY, theme);
    } catch {
      /* not fatal */
    }
  }, [theme]);

  const toggle = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);
  return { theme, toggle };
}