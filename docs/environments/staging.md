# Environment Guide: Staging

## Purpose

Production-like validation with full monitoring.

## Deployment Procedure

- Apply staging ConfigMap + Secret
- Deploy 2–3 replicas
- Run full test suite and validate quality gates

## Monitoring Access

- Dashboards and alerts should match production

## Approval Workflow

- Tech Lead approval required for promotion to production
