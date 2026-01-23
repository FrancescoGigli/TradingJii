# Streamlit & Frontend Rules

## Separation of Concerns
- Do not mix:
  - data processing
  - rendering logic
  - styling
  in the same function or file.

## Rendering
- Custom HTML and CSS rendering must be encapsulated
  in dedicated modules.
- Streamlit integration must be a thin wrapper only.

## Reusability
- UI components must be reusable.
- Avoid inline styles or duplicated UI logic.

## Constraints
- Prefer deterministic rendering over interactivity.
- Avoid Streamlit components that cannot be styled reliably
  when a custom theme is used.
