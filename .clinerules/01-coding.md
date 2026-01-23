# Coding Standards

## Language
- All code, comments, docstrings, identifiers, and documentation
  MUST be written in English only.
- Italian or mixed language is forbidden.

## File Size
- No source file may exceed 400 lines.
- If a file approaches this limit, code MUST be split
  into smaller, well-named modules.

## Modularity
- Monolithic files are forbidden.
- Each file must have a single responsibility.
- Reusable logic must be extracted into shared modules.

## Optimization
- Code must prioritize:
  - readability
  - maintainability
  - performance
- Avoid duplicated logic.
- Prefer clear, explicit code over clever shortcuts.

## Safe Changes
- Do not refactor unrelated code.
- Modify only what is required for the requested change.
