-- Omnichannel case routing: SQLite DDL.
-- Timestamps: TEXT ISO-8601 UTC, e.g. '2026-01-03T14:05:00Z'.
-- Durations and targets: INTEGER minutes. Booleans: INTEGER 0/1.
-- Tables are created parents first. Enable FKs with PRAGMA foreign_keys = ON.
-- Constraints cover shape only (enums, flags, ranges); labelled anomalies
-- (capacity, calendar, safety, loops, lost history) are business-rule
-- violations and still load. Their labels live only in ground_truth/.

-- ===================== Reference / master =====================

-- Contact channel and default per-agent concurrency limit.
CREATE TABLE channel (
    channel_id             TEXT    PRIMARY KEY CHECK (channel_id IN ('EMAIL', 'CHAT', 'PHONE')),
    name                   TEXT    NOT NULL,
    default_max_concurrent INTEGER NOT NULL CHECK (default_max_concurrent >= 1)
);

-- ISO 639-1 languages customers and agents use.
CREATE TABLE language (
    language_code TEXT PRIMARY KEY CHECK (language_code IN ('en', 'es', 'fr', 'de')),
    name          TEXT NOT NULL
);

-- Agent skills; each queue requires exactly one.
CREATE TABLE skill (
    skill_id TEXT PRIMARY KEY,
    name     TEXT NOT NULL
);

-- Work queues (Queue N:1 Skill).
CREATE TABLE queue (
    queue_id TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    skill_id TEXT NOT NULL REFERENCES skill (skill_id)
);

-- Intent taxonomy: home queue, default priority, safety flag.
CREATE TABLE intent (
    intent_id        TEXT    PRIMARY KEY,
    queue_id         TEXT    NOT NULL REFERENCES queue (queue_id),
    default_priority TEXT    NOT NULL CHECK (default_priority IN ('P1', 'P2', 'P3', 'P4')),
    is_safety        INTEGER NOT NULL CHECK (is_safety IN (0, 1))
);

-- Ordered priority rules; tickets cite the last rule that changed priority.
CREATE TABLE priority_rule (
    rule_id        TEXT PRIMARY KEY,
    description    TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to   TEXT
);

-- SLA targets per priority x channel (added; not in the spec's entity list).
CREATE TABLE sla_policy (
    priority           TEXT    NOT NULL CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    channel_id         TEXT    NOT NULL REFERENCES channel (channel_id),
    first_response_min INTEGER NOT NULL CHECK (first_response_min > 0),
    resolution_min     INTEGER NOT NULL CHECK (resolution_min > 0),
    calendar           TEXT    NOT NULL CHECK (calendar IN ('24x7', 'CHANNEL')),
    PRIMARY KEY (priority, channel_id)
);

-- Agent shift windows (added). end_min < start_min means it wraps midnight.
CREATE TABLE shift (
    shift_id  TEXT    PRIMARY KEY,
    start_min INTEGER NOT NULL CHECK (start_min BETWEEN 0 AND 1439),
    end_min   INTEGER NOT NULL CHECK (end_min BETWEEN 0 AND 1439),
    weekdays  TEXT    NOT NULL
);

-- Customers and prospects (prospects have no tier).
CREATE TABLE customer (
    customer_id        TEXT PRIMARY KEY,
    display_name       TEXT NOT NULL,
    customer_type      TEXT NOT NULL CHECK (customer_type IN ('CUSTOMER', 'PROSPECT')),
    tier               TEXT CHECK (tier IN ('STANDARD', 'PREMIUM', 'ENTERPRISE')),
    preferred_language TEXT NOT NULL REFERENCES language (language_code),
    created_at         TEXT NOT NULL,
    CHECK ((customer_type = 'PROSPECT' AND tier IS NULL)
        OR (customer_type = 'CUSTOMER' AND tier IS NOT NULL))
);

-- Support agents with per-channel concurrency limits.
CREATE TABLE agent (
    agent_id             TEXT    PRIMARY KEY,
    display_name         TEXT    NOT NULL,
    shift_id             TEXT    NOT NULL REFERENCES shift (shift_id),
    max_concurrent_email INTEGER NOT NULL CHECK (max_concurrent_email >= 0),
    max_concurrent_chat  INTEGER NOT NULL CHECK (max_concurrent_chat >= 0),
    max_concurrent_phone INTEGER NOT NULL CHECK (max_concurrent_phone >= 0),
    hired_at             TEXT    NOT NULL,
    status               TEXT    NOT NULL CHECK (status IN ('ACTIVE'))
);

-- Bridge: Agent N:M Skill.
CREATE TABLE agent_skill (
    agent_id       TEXT NOT NULL REFERENCES agent (agent_id),
    skill_id       TEXT NOT NULL REFERENCES skill (skill_id),
    effective_from TEXT NOT NULL,
    PRIMARY KEY (agent_id, skill_id)
);

-- Bridge: Agent N:M Language.
CREATE TABLE agent_language (
    agent_id       TEXT NOT NULL REFERENCES agent (agent_id),
    language_code  TEXT NOT NULL REFERENCES language (language_code),
    effective_from TEXT NOT NULL,
    PRIMARY KEY (agent_id, language_code)
);

-- ===================== Transactions / events =====================

-- Ticket. Lifecycle columns are a snapshot derived from the event tables.
CREATE TABLE ticket (
    ticket_id         TEXT    PRIMARY KEY,
    customer_id       TEXT    NOT NULL REFERENCES customer (customer_id),
    channel_id        TEXT    NOT NULL REFERENCES channel (channel_id),
    intent_id         TEXT    NOT NULL REFERENCES intent (intent_id),
    language_code     TEXT    NOT NULL REFERENCES language (language_code),
    urgency           TEXT    NOT NULL CHECK (urgency IN ('LOW', 'MEDIUM', 'HIGH')),
    priority          TEXT    NOT NULL CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    priority_rule_id  TEXT    NOT NULL REFERENCES priority_rule (rule_id),
    created_at        TEXT    NOT NULL,
    after_hours       INTEGER NOT NULL CHECK (after_hours IN (0, 1)),
    status            TEXT    NOT NULL CHECK (status IN ('QUEUED', 'ASSIGNED', 'RESOLVED', 'REOPENED')),
    current_queue_id  TEXT    NOT NULL REFERENCES queue (queue_id),
    transfer_count    INTEGER NOT NULL CHECK (transfer_count >= 0),
    escalation_count  INTEGER NOT NULL CHECK (escalation_count >= 0),
    reopen_count      INTEGER NOT NULL CHECK (reopen_count >= 0),
    first_response_at TEXT,
    resolved_at       TEXT,
    csat              INTEGER CHECK (csat BETWEEN 1 AND 5)
);

-- SLA instance, one per ticket (1:1).
CREATE TABLE sla (
    sla_id                    TEXT    PRIMARY KEY,
    ticket_id                 TEXT    NOT NULL UNIQUE REFERENCES ticket (ticket_id),
    priority                  TEXT    NOT NULL CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    channel_id                TEXT    NOT NULL REFERENCES channel (channel_id),
    calendar                  TEXT    NOT NULL CHECK (calendar IN ('24x7', 'CHANNEL')),
    first_response_target_min INTEGER NOT NULL CHECK (first_response_target_min > 0),
    resolution_target_min     INTEGER NOT NULL CHECK (resolution_target_min > 0),
    started_at                TEXT    NOT NULL,
    first_response_due_at     TEXT    NOT NULL,
    resolution_due_at         TEXT    NOT NULL
);

-- Append-only routing history (assign, transfer, escalate, resolve, reopen).
CREATE TABLE assignment_event (
    asn_id           TEXT    PRIMARY KEY,
    ticket_id        TEXT    NOT NULL REFERENCES ticket (ticket_id),
    seq              INTEGER NOT NULL CHECK (seq >= 1),
    event_type       TEXT    NOT NULL CHECK (event_type IN ('ASSIGN', 'TRANSFER', 'ESCALATE', 'RESOLVE', 'REOPEN')),
    ts               TEXT    NOT NULL,
    queue_id         TEXT    NOT NULL REFERENCES queue (queue_id),
    agent_id         TEXT    REFERENCES agent (agent_id),
    translation_flag INTEGER NOT NULL CHECK (translation_flag IN (0, 1)),
    reason           TEXT    NOT NULL,
    UNIQUE (ticket_id, seq)
);

-- Append-only SLA clock history.
CREATE TABLE sla_event (
    sla_event_id TEXT    PRIMARY KEY,
    sla_id       TEXT    NOT NULL REFERENCES sla (sla_id),
    ticket_id    TEXT    NOT NULL REFERENCES ticket (ticket_id),
    cycle_no     INTEGER NOT NULL CHECK (cycle_no >= 1),
    event_type   TEXT    NOT NULL CHECK (event_type IN ('CLOCK_STARTED', 'FIRST_RESPONSE_MET', 'FIRST_RESPONSE_BREACHED',
                                                         'RESOLUTION_MET', 'RESOLUTION_BREACHED', 'CLOCK_RESTARTED')),
    ts           TEXT    NOT NULL,
    due_at       TEXT
);

-- Threaded messages per ticket.
CREATE TABLE message (
    message_id  TEXT    PRIMARY KEY,
    ticket_id   TEXT    NOT NULL REFERENCES ticket (ticket_id),
    seq         INTEGER NOT NULL CHECK (seq BETWEEN 1 AND 999),
    ts          TEXT    NOT NULL,
    author_type TEXT    NOT NULL CHECK (author_type IN ('CUSTOMER', 'AGENT', 'SYSTEM')),
    channel_id  TEXT    NOT NULL REFERENCES channel (channel_id),
    agent_id    TEXT    REFERENCES agent (agent_id),
    body        TEXT    NOT NULL,
    UNIQUE (ticket_id, seq)
);

-- One resolution per ticket per lifecycle cycle.
CREATE TABLE resolution (
    resolution_id   TEXT    PRIMARY KEY,
    ticket_id       TEXT    NOT NULL REFERENCES ticket (ticket_id),
    cycle_no        INTEGER NOT NULL CHECK (cycle_no >= 1),
    agent_id        TEXT    NOT NULL REFERENCES agent (agent_id),
    resolved_at     TEXT    NOT NULL,
    handle_minutes  INTEGER NOT NULL CHECK (handle_minutes >= 0),
    resolution_code TEXT    NOT NULL CHECK (resolution_code IN ('SOLVED', 'WORKAROUND', 'INFO_PROVIDED')),
    csat            INTEGER CHECK (csat BETWEEN 1 AND 5),
    UNIQUE (ticket_id, cycle_no)
);
