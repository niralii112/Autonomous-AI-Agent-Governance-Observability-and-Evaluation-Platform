## What changed
<!-- One logical change per pull request. -->

## Contract impact
- [ ] No change to `contracts/`, enums, error codes, span names, audit event names, environment variables or function signatures
- [ ] There IS a contract change: issue number ______ (change control, spec section 21.2). All three students must approve.

## Checks (paste the last line of each)
- [ ] `cd backend && python -m pytest tests -q`
- [ ] `python scripts/check_contracts.py --strict`
- [ ] `cd frontend && npm run check:types` (only if the frontend or `contracts/openapi.yaml` changed)

## Notes for the reviewer
<!-- What should they look at first? What did you NOT test? -->
