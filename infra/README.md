# infra/

Infrastructure as code and operations. Mirrors the Infrastructure Layer of the architecture diagram.

| Folder | Contents |
|---|---|
| [docker](docker/) | Dockerfiles and compose files for local and CI. |
| [kubernetes](kubernetes/) | Helm charts / manifests per app and platform service. |
| [terraform](terraform/) | Cloud or on-prem provisioning (as per RFP). |
| [monitoring](monitoring/) | Metrics, logs, traces, dashboards and alert rules. |
| [backup-dr](backup-dr/) | Backup schedules, restore runbooks, disaster-recovery plans. |
| [runbooks](runbooks/) | What to do when something needs attention: on-call, restore, suspend a tenant, rotate a secret, roll back, scale. |
| [load-balancing](load-balancing/) | Ingress, LB and TLS configuration. |
