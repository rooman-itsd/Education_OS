# search — integration points

## Platform services used
| Service | For |
|---|---|
| identity | the caller (`Principal`): user id, organisation, and the full grant set, read once per request |
| audit | `reindex.requested`, in the same transaction as the job row |
| event-bus | delivery to `eos.event_consumers`; search publishes `search.reindex.completed`, `search.reindex.failed`, `search.organisation.purged` through the outbox |

## Entry points
| Group | Who registers | What |
|---|---|---|
| `eos.event_consumers` | search | `eos_search.application.consumers:CONSUMERS`: the trigger events of the declared types, `tenancy.entitlement.changed`, `tenancy.organisation.purged` |
| `eos.search_documents` | each searchable module | a provider (see README, "What each first module must add"). New with this module |

## Events consumed
Declared in `module.yaml` and `contracts/events.yaml`: the platform events above, and the trigger events of the first three
modules to opt in. A module's declaration may name only events that start with its own module name.

## Not used
Search never reads another module's tables and never imports its code.
