# Environment Guide: Production

## Purpose

Highly available environment with strict quality gates.

## Deployment Strategy

- Blue-green deployment
- Gradual traffic shift

## High Availability

- 3–5 replicas with autoscaling
- HA Postgres and Redis cluster

## Backup and Recovery

- Regular DB backups
- Tested restore procedure

## Emergency Procedures

- Follow runbooks in `/docs/runbooks/`
- Prefer feature-flag rollback for risky features
- Use `/docs/rollback-guide.md` for deployment rollback
