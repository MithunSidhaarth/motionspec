# Theming

`theme.json` keys: `extends` (midnight | paper | signal), `bg fg muted dim card accent accent_text positive negative` (hex), `brand tagline url logo` (logo is a PNG path inside the project), `fonts` {bold, reg, mono} (file names or paths), `font_dirs`, `grain`, `vignette`.

Tips: keep one accent colour; make `accent_text` readable on `accent` (4.5:1) and `fg` on `bg` (7:1); `motionspec doctor` reports built-in theme contrast and any missing font. For identical output on every machine put an open-licence `.ttf` in `motionspec/fonts/` or the project and name it in `fonts`.

A scene can override its background: `"bg": "accent"` or `"gradient": ["#0B1020", "#1B2A4A"]`.
