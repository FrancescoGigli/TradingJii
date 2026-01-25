# Styling Rules

## Dark Theme
- All UI components MUST use dark theme colors
- Background colors must be dark (e.g., `#0d1117`, `#1e2130`, `#161b26`)
- Text colors must be light (e.g., `#e0e0ff`, `#9ca3af`, `#ffffff`)
- Never use white or light backgrounds in any component

## Streamlit Expanders
- Expander content must have explicit dark background
- Use CSS injection to override default Streamlit styling
- Example: `background: #1e2130` or `background: #0d1117`

## HTML Elements in st.markdown
- All custom HTML must include explicit dark background colors
- Never rely on browser defaults which may be white
- Code blocks should use `background: #2d3748`
- Cards should use `background: #1e2130`

## Color Palette Reference
- Primary background: `#0d1117`
- Secondary background: `#1e2130`
- Tertiary background: `#161b26`
- Card border: `#2d3748`
- Primary text: `#e0e0ff`
- Secondary text: `#9ca3af`
- Accent (cyan): `#00ffff`
- Success (green): `#4ade80` / `#34d399`
- Error (red): `#ef4444`
- Warning (yellow): `#fbbf24`
- Info (blue): `#60a5fa` / `#4a90d9`

## Tables
- Table headers: background `#161b26`, text `#00ffff`
- Table rows: background `#0d1117`, text `#e0e0ff`
- Hover: slightly lighter background

## Charts
- Plotly charts must use dark template
- Chart background: `rgba(0,0,0,0)` or `#0d1117`
- Grid lines: subtle colors like `#2d3748`
