# Data dictionary

DDL: `caserouting/schema.sql`. Allowed values and ID formats come from `caserouting/config.py` and `caserouting/ids.py`.

- **Seed:** `20261022` (`config.SEED`). Same seed and scale give identical output.
- **Time model:** the simulation runs in integer UTC minutes since `2026-01-01T00:00Z`, with no daylight saving (2026-01-01 is a Thursday, day index `t // 1440`). Every timestamp is exported as ISO-8601 UTC TEXT, e.g. `2026-01-03T14:05:00Z`. Durations and targets are INTEGER minutes. Booleans are INTEGER `0`/`1`.
- **Ground truth:** anomaly labels (`CAPACITY_EXCEEDED`, `SLA_CALENDAR_IGNORED`, `REOPEN_HISTORY_LOST`, `TRANSFER_LOOP`, `PRIORITY_SAFETY_VIOLATION`) live only in `ground_truth/`. They never appear as columns in these tables.
- **Snapshot rule:** ticket lifecycle columns are a snapshot computed from the append-only event tables (`assignment_event`, `sla_event`, `message`, `resolution`). They are never edited on their own.
- **ISO TS** below means TEXT `YYYY-MM-DDTHH:MM:SSZ` (UTC).

## channel

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `channel_id` | TEXT | Yes | `EMAIL`, `CHAT`, `PHONE` | - | PK | CHECK enum |
| `name` | TEXT | Yes | `Email`, `Live chat`, `Phone` | - | No | Matches `config.CHANNELS[*].name` |
| `default_max_concurrent` | INTEGER | Yes | EMAIL 5, CHAT 3, PHONE 1 | tickets per agent | No | >= 1. Matches `config.CHANNELS[*].limit` |

## language

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `language_code` | TEXT | Yes | `en`, `es`, `fr`, `de` (ISO 639-1) | - | PK | CHECK enum |
| `name` | TEXT | Yes | `English`, `Spanish`, `French`, `German` | - | No | Matches `config.LANGUAGES[*].name` |

## skill

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `skill_id` | TEXT | Yes | `SKL-BILLING`, `SKL-ACCOUNT`, `SKL-TECH`, `SKL-SALES`, `SKL-T2` | - | PK | Must be a key of `config.SKILLS` |
| `name` | TEXT | Yes | Free text, e.g. `Billing and refunds` | - | No | Not empty |

## queue

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `queue_id` | TEXT | Yes | `QUE-BILLING`, `QUE-ACCOUNT`, `QUE-TECH`, `QUE-SALES`, `QUE-T2` | - | PK | Must be a key of `config.QUEUES`. `QUE-T2` is the escalation queue |
| `name` | TEXT | Yes | Free text, e.g. `Billing` | - | No | Not empty |
| `skill_id` | TEXT | Yes | `SKL-*` | - | No | FK -> `skill`. Exactly one skill per queue |

## intent

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `intent_id` | TEXT | Yes | `INT-BILLING_DISPUTE`, `INT-REFUND`, `INT-PASSWORD_RESET`, `INT-ACCOUNT_CHANGE`, `INT-GENERAL_QUESTION`, `INT-TECH_ISSUE`, `INT-OUTAGE`, `INT-SECURITY`, `INT-SAFETY_HAZARD`, `INT-SALES_INQUIRY`, `INT-DEMO_REQUEST` | - | PK | Must be a key of `config.INTENTS` |
| `queue_id` | TEXT | Yes | `QUE-*` | - | No | FK -> `queue`. The intent's home queue |
| `default_priority` | TEXT | Yes | `P1`, `P2`, `P3`, `P4` (P1 is most urgent) | - | No | CHECK enum. Must be `P1` when `is_safety = 1` |
| `is_safety` | INTEGER | Yes | `0`, `1` | boolean | No | CHECK 0/1. `1` for `INT-OUTAGE`, `INT-SECURITY`, `INT-SAFETY_HAZARD` |

## priority_rule

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `rule_id` | TEXT | Yes | `PRL-001` .. `PRL-005` | - | PK | Rules apply in id order. `PRL-005` is the safety rule (safety intents are always P1) |
| `description` | TEXT | Yes | Free text | - | No | Not empty |
| `effective_from` | TEXT | Yes | ISO TS | - | No | Rule is active from this time. All rules: `2026-01-01T00:00:00Z` |
| `effective_to` | TEXT | No | ISO TS or NULL | - | No | NULL means still active. When set, must be > `effective_from` |

## sla_policy

Added table (not in the spec's entity list). It holds the SLA targets from `config.SLA_TARGETS`.

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `priority` | TEXT | Yes | `P1`, `P2`, `P3`, `P4` | - | PK (with `channel_id`) | CHECK enum |
| `channel_id` | TEXT | Yes | `EMAIL`, `CHAT`, `PHONE` | - | PK (with `priority`) | FK -> `channel`. 12 rows in total (4 priorities x 3 channels) |
| `first_response_min` | INTEGER | Yes | e.g. P1/EMAIL 30, P4/EMAIL 480 | business minutes | No | > 0. Matches `config.SLA_TARGETS[(priority, channel)][0]` |
| `resolution_min` | INTEGER | Yes | P1 240, P2 600, P3 1200, P4 3000 | business minutes | No | > 0. Must be >= `first_response_min` |
| `calendar` | TEXT | Yes | `24x7`, `CHANNEL` | - | No | CHECK enum. `24x7` when priority is `P1`, otherwise `CHANNEL` |

## shift

Added table. Holds `config.SHIFTS`.

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `shift_id` | TEXT | Yes | `SHF-DAY`, `SHF-EVE`, `SHF-NIGHT` | - | PK | Must be a key of `config.SHIFTS` |
| `start_min` | INTEGER | Yes | 0..1439 (DAY 420, EVE 840, NIGHT 1320) | minutes after midnight UTC | No | CHECK range |
| `end_min` | INTEGER | Yes | 0..1439 (DAY 900, EVE 1320, NIGHT 420) | minutes after midnight UTC | No | CHECK range. `end_min < start_min` means the shift wraps past midnight (NIGHT) |
| `weekdays` | TEXT | Yes | Comma-separated weekday indices, Mon=0, e.g. `0,1,2,3,4,5` | - | No | Each value is in 0..6, no duplicates |

## customer

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `customer_id` | TEXT | Yes | `CUS-000001` (`^CUS-\d{6}$`) | - | PK | Matches the `ids.PATTERNS` regex |
| `display_name` | TEXT | Yes | Synthetic name | - | No | Not empty. Synthetic only, no real personal data |
| `customer_type` | TEXT | Yes | `CUSTOMER`, `PROSPECT` | - | No | CHECK enum. About 12% are `PROSPECT` |
| `tier` | TEXT | No | `STANDARD`, `PREMIUM`, `ENTERPRISE` or NULL | - | No | CHECK: NULL if and only if `customer_type = 'PROSPECT'` |
| `preferred_language` | TEXT | Yes | `en`, `es`, `fr`, `de` | - | No | FK -> `language` |
| `created_at` | TEXT | Yes | ISO TS | - | No | Must be <= every `ticket.created_at` for this customer |

## agent

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `agent_id` | TEXT | Yes | `AGT-000001` (`^AGT-\d{6}$`) | - | PK | Matches the `ids.PATTERNS` regex |
| `display_name` | TEXT | Yes | Synthetic name | - | No | Not empty |
| `shift_id` | TEXT | Yes | `SHF-*` | - | No | FK -> `shift` |
| `max_concurrent_email` | INTEGER | Yes | default 5 | tickets | No | >= 0 |
| `max_concurrent_chat` | INTEGER | Yes | default 3 | tickets | No | >= 0 |
| `max_concurrent_phone` | INTEGER | Yes | default 1 | tickets | No | >= 0 |
| `hired_at` | TEXT | Yes | ISO TS | - | No | Must be <= the agent's first `assignment_event.ts` |
| `status` | TEXT | Yes | `ACTIVE` | - | No | CHECK enum |

## agent_skill

Bridge table: Agent N:M Skill.

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `agent_id` | TEXT | Yes | `AGT-*` | - | PK (with `skill_id`) | FK -> `agent` |
| `skill_id` | TEXT | Yes | `SKL-*` | - | PK (with `agent_id`) | FK -> `skill` |
| `effective_from` | TEXT | Yes | ISO TS | - | No | The agent holds this skill from this time. Must be >= `agent.hired_at` |

## agent_language

Bridge table: Agent N:M Language.

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `agent_id` | TEXT | Yes | `AGT-*` | - | PK (with `language_code`) | FK -> `agent` |
| `language_code` | TEXT | Yes | `en`, `es`, `fr`, `de` | - | PK (with `agent_id`) | FK -> `language` |
| `effective_from` | TEXT | Yes | ISO TS | - | No | The agent speaks this language from this time. Must be >= `agent.hired_at` |

## ticket

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `ticket_id` | TEXT | Yes | `TKT-2026-000001` (`^TKT-2026-\d{6}$`) | - | PK | Matches the `ids.PATTERNS` regex |
| `customer_id` | TEXT | Yes | `CUS-*` | - | No | FK -> `customer` |
| `channel_id` | TEXT | Yes | `EMAIL`, `CHAT`, `PHONE` | - | No | FK -> `channel` |
| `intent_id` | TEXT | Yes | `INT-*` | - | No | FK -> `intent` |
| `language_code` | TEXT | Yes | `en`, `es`, `fr`, `de` | - | No | FK -> `language`. Language the ticket was written in |
| `urgency` | TEXT | Yes | `LOW`, `MEDIUM`, `HIGH` | - | No | CHECK enum |
| `priority` | TEXT | Yes | `P1`, `P2`, `P3`, `P4` | - | No | Derived from `intent.default_priority`, `urgency` and `customer.tier` by the `priority_rule` chain PRL-001..PRL-005. Must be `P1` when `intent.is_safety = 1` |
| `priority_rule_id` | TEXT | Yes | `PRL-*` | - | No | FK -> `priority_rule`. The last rule that changed the priority |
| `created_at` | TEXT | Yes | ISO TS | - | No | Must be >= `customer.created_at` |
| `after_hours` | INTEGER | Yes | `0`, `1` | boolean | No | Derived from `created_at` and the channel calendar by rule: 1 if created outside the channel's open hours or on a holiday |
| `status` | TEXT | Yes | `QUEUED`, `ASSIGNED`, `RESOLVED`, `REOPENED` | - | No | Derived from `assignment_event` by replaying event types in `seq` order (see `docs/model.md`). `QUEUED` when there are no events |
| `current_queue_id` | TEXT | Yes | `QUE-*` | - | No | Derived from `assignment_event` by rule: `queue_id` of the last event. With no events, the intent's home queue |
| `transfer_count` | INTEGER | Yes | >= 0 | events | No | Derived from `assignment_event` by counting `event_type = 'TRANSFER'` |
| `escalation_count` | INTEGER | Yes | >= 0 | events | No | Derived from `assignment_event` by counting `event_type = 'ESCALATE'` |
| `reopen_count` | INTEGER | Yes | >= 0 | events | No | Derived from `assignment_event` by counting `event_type = 'REOPEN'` |
| `first_response_at` | TEXT | No | ISO TS or NULL | - | No | Derived from `message` by rule: `ts` of the first message with `author_type = 'AGENT'`. NULL if none |
| `resolved_at` | TEXT | No | ISO TS or NULL | - | No | Derived from `resolution` by rule: `resolved_at` of the highest `cycle_no`, only while `status = 'RESOLVED'`. Otherwise NULL |
| `csat` | INTEGER | No | 1..5 or NULL | score | No | Derived from `resolution` by rule: `csat` of the latest cycle. NULL when the customer did not respond |

## sla

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `sla_id` | TEXT | Yes | `SLA-<ticket-id>` (`^SLA-TKT-2026-\d{6}$`) | - | PK | Matches the `ids.PATTERNS` regex |
| `ticket_id` | TEXT | Yes | `TKT-2026-*` | - | UNIQUE (1:1) | FK -> `ticket` |
| `priority` | TEXT | Yes | `P1`, `P2`, `P3`, `P4` | - | No | Derived from `ticket.priority` by copy |
| `channel_id` | TEXT | Yes | `EMAIL`, `CHAT`, `PHONE` | - | No | FK -> `channel`. Derived from `ticket.channel_id` by copy |
| `calendar` | TEXT | Yes | `24x7`, `CHANNEL` | - | No | Derived from `sla_policy` by lookup on (`priority`, `channel_id`) |
| `first_response_target_min` | INTEGER | Yes | > 0 | business minutes | No | Derived from `sla_policy.first_response_min` by lookup |
| `resolution_target_min` | INTEGER | Yes | > 0 | business minutes | No | Derived from `sla_policy.resolution_min` by lookup |
| `started_at` | TEXT | Yes | ISO TS | - | No | Derived from `ticket.created_at` by copy |
| `first_response_due_at` | TEXT | Yes | ISO TS | - | No | Derived from `started_at` by rule: add `first_response_target_min` open minutes on `calendar` (24x7 = wall clock; CHANNEL = channel hours, holidays closed) |
| `resolution_due_at` | TEXT | Yes | ISO TS | - | No | Derived from `started_at` by rule: add `resolution_target_min` open minutes on `calendar`. Covers cycle 1; later cycles use `sla_event.due_at` |

## assignment_event

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `asn_id` | TEXT | Yes | `ASN-<ticket-id>-001` (`^ASN-TKT-2026-\d{6}-\d{3}$`) | - | PK | Suffix equals `seq` |
| `ticket_id` | TEXT | Yes | `TKT-2026-*` | - | UNIQUE (with `seq`) | FK -> `ticket` |
| `seq` | INTEGER | Yes | 1, 2, 3 ... | - | UNIQUE (with `ticket_id`) | Gap-free per ticket. `ts` does not decrease as `seq` increases |
| `event_type` | TEXT | Yes | `ASSIGN`, `TRANSFER`, `ESCALATE`, `RESOLVE`, `REOPEN` | - | No | CHECK enum. Must be a legal transition from the current status (see `docs/model.md`) |
| `ts` | TEXT | Yes | ISO TS | - | No | Must be >= `ticket.created_at` |
| `queue_id` | TEXT | Yes | `QUE-*` | - | No | FK -> `queue`. Queue after the event. `QUE-T2` for `ESCALATE` |
| `agent_id` | TEXT | No | `AGT-*` or NULL | - | No | FK -> `agent`. Required for `ASSIGN` and `RESOLVE`. NULL for `TRANSFER`, `ESCALATE`, `REOPEN`. For `ASSIGN`, the agent must hold the queue's skill and be under the channel limit |
| `translation_flag` | INTEGER | Yes | `0`, `1` | boolean | No | 1 when the assigned agent does not speak `ticket.language_code` (language mismatch) |
| `reason` | TEXT | Yes | Free text, e.g. misroute, SLA 80% used | - | No | Not empty |

## sla_event

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `sla_event_id` | TEXT | Yes | `SLA-<ticket-id>-001` (`^SLA-TKT-2026-\d{6}-\d{3}$`) | - | PK | Suffix is a per-ticket sequence |
| `sla_id` | TEXT | Yes | `SLA-TKT-2026-*` | - | No | FK -> `sla` |
| `ticket_id` | TEXT | Yes | `TKT-2026-*` | - | No | FK -> `ticket`. Must equal `sla.ticket_id` |
| `cycle_no` | INTEGER | Yes | 1, 2, 3 ... | - | No | Starts at 1. Goes up by 1 at each `CLOCK_RESTARTED` |
| `event_type` | TEXT | Yes | `CLOCK_STARTED`, `FIRST_RESPONSE_MET`, `FIRST_RESPONSE_BREACHED`, `RESOLUTION_MET`, `RESOLUTION_BREACHED`, `CLOCK_RESTARTED` | - | No | CHECK enum |
| `ts` | TEXT | Yes | ISO TS | - | No | Must be >= `sla.started_at` |
| `due_at` | TEXT | No | ISO TS or NULL | - | No | Derived from the `sla` targets and `calendar` by rule: deadline the event measures against (set for start/restart and MET/BREACHED). NULL when not applicable |

## message

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `message_id` | TEXT | Yes | `MSG-<ticket-id>-001` (`^MSG-TKT-2026-\d{6}-\d{3}$`) | - | PK | Suffix equals `seq` |
| `ticket_id` | TEXT | Yes | `TKT-2026-*` | - | UNIQUE (with `seq`) | FK -> `ticket` |
| `seq` | INTEGER | Yes | 1..999 | - | UNIQUE (with `ticket_id`) | Gap-free per ticket. Message 1 is from the customer |
| `ts` | TEXT | Yes | ISO TS | - | No | Must be >= `ticket.created_at`. Does not decrease as `seq` increases |
| `author_type` | TEXT | Yes | `CUSTOMER`, `AGENT`, `SYSTEM` | - | No | CHECK enum |
| `channel_id` | TEXT | Yes | `EMAIL`, `CHAT`, `PHONE` | - | No | FK -> `channel`. Equals `ticket.channel_id` |
| `agent_id` | TEXT | No | `AGT-*` or NULL | - | No | FK -> `agent`. Required when `author_type = 'AGENT'`, otherwise NULL |
| `body` | TEXT | Yes | Synthetic text | - | No | Not empty |

## resolution

| Field | Type | Required | Allowed values / format | Units | Unique | Validation rule |
|---|---|---|---|---|---|---|
| `resolution_id` | TEXT | Yes | `RES-<ticket-id>-001` (`^RES-TKT-2026-\d{6}-\d{3}$`) | - | PK | Suffix equals `cycle_no` |
| `ticket_id` | TEXT | Yes | `TKT-2026-*` | - | UNIQUE (with `cycle_no`) | FK -> `ticket` |
| `cycle_no` | INTEGER | Yes | 1, 2, 3 ... | - | UNIQUE (with `ticket_id`) | 1 + the number of `REOPEN` events before this resolution |
| `agent_id` | TEXT | Yes | `AGT-*` | - | No | FK -> `agent`. Equals `agent_id` of the matching `RESOLVE` event |
| `resolved_at` | TEXT | Yes | ISO TS | - | No | Equals `ts` of the matching `RESOLVE` event |
| `handle_minutes` | INTEGER | Yes | >= 0 | minutes | No | Lognormal draw (median EMAIL 35, CHAT 18, PHONE 12; x1.5 in `QUE-T2`) |
| `resolution_code` | TEXT | Yes | `SOLVED`, `WORKAROUND`, `INFO_PROVIDED` | - | No | CHECK enum |
| `csat` | INTEGER | No | 1..5 or NULL | score | No | CHECK 1..5. NULL when no survey reply (35% reply rate). Formula in `config.py` |
