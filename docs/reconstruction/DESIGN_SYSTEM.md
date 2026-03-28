# Phase 2 — Design System (frontend)

**Aesthetic (three adjectives):** **Phosphor-terminal**, **precise**, **calm-aggressive** — dark void UI with monospace truth, one electric accent family, no playful illustration noise.

**Law:** No colour outside the semantic tokens below. If you need another hue, extend the token table here first.

---

## 1. Spacing scale (4px base)

| Token | Value | Use |
|-------|-------|-----|
| `space-1` | 4px | Tight inline gap |
| `space-2` | 8px | Chip padding, icon gaps |
| `space-3` | 12px | Card padding (compact) |
| `space-4` | 16px | Default section padding |
| `space-5` | 20px | Feed gutters |
| `space-6` | 24px | Modal interior |

*(Current `style.css` uses ad-hoc px; migration = replace with `calc(var(--space-n))` variables.)*

---

## 2. Colour tokens (semantic)

| Token | Role | Example hex (current) |
|-------|------|----------------------|
| `--bg-base` | App background | `#070809` |
| `--bg-elevated` | Raised panels | `#0c0f12` |
| `--bg-surface` | Cards, feed chrome | `#11161c` |
| `--bg-inset` | Inputs, wells | `#050607` |
| `--accent-primary` | Primary action, success emphasis | `#3de1a8` |
| `--accent-secondary` | Links, secondary focus | `#6b9fff` |
| `--danger` | Destructive / error | `#ff6b6b` |
| `--warning` | Caution, running state | `#e8c547` |
| `--text-primary` | Body | `#e8eaed` |
| `--text-secondary` | Labels | `#9aa3b2` |
| `--text-tertiary` | Muted / timestamps | `#5c6570` |
| `--border-default` | Default stroke | `#2a313c` |

**Legacy aliases** (`--cyan`, `--green`, `--red`, `--amber`, `--muted`, …) exist for JS `style.color` — deprecate gradually.

---

## 3. Typography (max 2 families, controlled scale)

| Role | Family | Weight | Size |
|------|--------|--------|------|
| UI chrome | IBM Plex Sans | 500–700 | 11–15px |
| Data / code / time | IBM Plex Mono | 400–600 | 10–15px |

**Scale:** `xs` 10px, `sm` 11–12px, `md` 14–15px, `lg` clamp(1.1rem, 3vw, 1.35rem) for hero status only.

---

## 4. Radii & elevation

- **Radii:** `sm` 6px, `md` 10px, `lg` 14px — no pill except mode chips (allowed exception: 20px for chips only).
- **Shadows:** Prefer **glow** (`box-shadow` with accent alpha) over neutral drop shadow. At most **one** neutral elevated shadow for drawers.

---

## 5. Motion

| Name | Duration | Easing | Use |
|------|----------|--------|-----|
| fast | 120ms | `ease-out` | Hover borders |
| medium | 220ms | `cubic-bezier(0.22,1,0.36,1)` | Drawer, panels |
| slow | 380ms | same | Login reveal only |

**`prefers-reduced-motion: reduce`:** disable scanlines, pulse, indeterminate shimmer; keep opacity fades ≤ 120ms.

---

## 6. Interactive states (required)

| Component | default | hover | active | focus-visible | disabled | loading |
|-----------|---------|-------|--------|---------------|----------|---------|
| Primary button | gradient fill | +brightness | slight press | 2px outline accent | greyed, no shadow | optional spinner text |
| Ghost / icon | border subtle | border accent | — | 2px outline | opacity 0.45 | — |
| Input | inset bg | — | — | ring accent | readonly style | — |
| Drawer scrim | transparent | — | — | — | — | blocks pointer |

**Contrast:** Primary text on accent buttons must meet **AA** (dark text on bright green is acceptable; verify with checker when tweaking hex).

---

## 7. Component inventory (primitives)

1. **App shell** — top bar, scanline overlay, safe-area padding.
2. **Composer** — prompt glyph + input + transmit.
3. **Message row** — timestamp + body variants (user, assistant, system, result, thinking).
4. **Intel drawer** — scrim + sliding aside.
5. **Card** — label strip + body (status, workflow, metrics).
6. **Modal** — archives, profile (bottom sheet on small VP).
7. **Mode chip** — three-state segment control.

**Hardest first (already designed):** Message row + composer (density + readability + wrap).

---

## 8. Implementation checklist

- [ ] Extract `:root` block to `css/tokens.css`.
- [ ] Document tokens in this file only; components reference variables.
- [ ] Remove one-off hex from `app.js` (use CSS classes for error states).

---

## Phase 2 exit criteria

- [x] Tokens, type, motion, and states specified.
- [ ] CSS file split to match tokens (Phase 3 UI slice).
