# piewall brand

**Name:** always lowercase `piewall`, one word. Never "PieWall" or "Pie Wall".

**Idea:** a pie built like a brick wall, with one slice lifted out. Your
firewall is whole by default; piewall shows exactly which slice you opened and
lets you put it back. Simple as pie.

**Tagline:** *Your firewall, simple as pie.*
**Voice:** calm, plain, short sentences. Explain what happens to the user's
network, never jargon for its own sake. No exclamation marks, no fear-selling.

## Logo

| File | Use |
|---|---|
| `logo-mark.svg` | the mark alone, on any background (min 16 px) |
| `app-icon.svg` | app / favicon / social: mark on a graphite squircle |
| `piewall.ico` | Windows icon, 16–256 px |
| `png/` | rendered sizes |

Clear space around the mark: 1/4 of its width. Don't recolor the slice, rotate
the mark, or add effects. Wordmark = the mark + `piewall` set in the display
font, weight 600, tracking -0.02em.

## Color

| Token | Hex | Use |
|---|---|---|
| crust | `#F27B1F` | logo, large accents |
| filling | `#FFC285` | the lifted slice, soft highlights |
| ember | `#C2410C` | buttons/links on light (white text, 5.2:1) |
| emberDark | `#FF9F52` | buttons/links on dark (dark text) |
| ink / graphite | `#1D1D1F` / `#6E6E73` | text on light |
| paper / cloud | `#FBFBFD` / `#F5F5F7` | backgrounds, light |
| night / slate / mist | `#000000` / `#1C1C1E` / `#A1A1A6` | dark mode |
| allow / block | `#248A3D` / `#D70015` | rule states (dark: `#30D158` / `#FF453A`) |

Orange is an accent, not a background: keep it under ~10% of any screen.

## Type

System fonts only (no downloads, native feel on each OS):
San Francisco on macOS/iOS, Segoe UI Variable on Windows. Stacks in
`tokens.json`. Headlines: display stack, weight 600–700, tight tracking.
Body 17 px on web, 10 pt in the Windows app. Code: SF Mono / Cascadia Code.

Machine-readable tokens: `tokens.json`.
