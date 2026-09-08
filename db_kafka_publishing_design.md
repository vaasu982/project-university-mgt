# DB → Kafka Publishing Design

## 1. Requirement

The application must:

1. Read unpublished transactions from PostgreSQL.
2. Publish the complete transaction to **Kafka Topic A**.
3. Publish only the transaction ID to a **Kafka Status Topic**.
4. A consumer of the Status Topic updates PostgreSQL and marks the transaction as published.
5. There is **one producer application instance**.
6. The consumer of Topic A cannot deduplicate messages, so duplicate records in Topic A are considered unacceptable.
7. The design must handle application/server crashes and restart/recovery.
8. PostgreSQL is the system of record for transaction state.

---

## 2. Proposed Architecture

```text
                         PostgreSQL
                     ┌────────────────┐
                     │ Transactions   │
                     │                │
                     │ TX123 | false  │
                     │ TX124 | false  │
                     └───────┬────────┘
                             │
                       Fetch unpublished
                             │
                             ▼
                    ┌─────────────────┐
                    │ Single Producer │
                    │ Application     │
                    └────────┬────────┘
                             │
                      Kafka Transaction
                       ┌─────┴─────┐
                       │           │
                       ▼           ▼
                 ┌──────────┐  ┌──────────────┐
                 │ Topic A  │  │ Status Topic │
                 │          │  │              │
                 │ Full     │  │ TX123        │
                 │ TX123    │  │ TX124        │
                 └──────────┘  └──────┬───────┘
                                      │
                                      ▼
                              Status Consumer
                                      │
                                      ▼
                                 PostgreSQL
                              published=true
```

Topic A and Status Topic should be produced within the **same Kafka transaction**.

---

## 3. Why Two Kafka Topics?

### Topic A

Contains the complete business transaction:

```json
{
  "txnId": "TX123",
  "amount": 1000,
  "..."
}
```

### Status Topic

Contains only the transaction ID:

```text
TX123
```

The Status Topic acts as a durable Kafka-side confirmation that the Kafka transaction containing the business event committed.

The Status Consumer uses that ID to update PostgreSQL:

```sql
UPDATE transactions
SET published = true
WHERE txn_id = ?
  AND published = false;
```

The DB update must be idempotent because the Status Topic message can be delivered more than once.

---

## 4. Kafka Transaction

The two sends should be part of one Kafka transaction:

```java
producer.beginTransaction();

producer.send(topicA, txnId, transaction);
producer.send(statusTopic, txnId, txnId);

producer.commitTransaction();
```

Therefore:

- Topic A committed + Status Topic committed → both visible.
- Kafka transaction aborted → neither visible.

Consumers that need transactional visibility should use:

```properties
isolation.level=read_committed
```

---

## 5. Important Clarification: Kafka Idempotent Producer

Kafka producer idempotence and the DB recovery problem are **different things**.

### Idempotence protects this scenario

```text
Producer                    Kafka
   │                          │
   │── TX123 ────────────────►│
   │                          │
   │       TX123 stored       │
   │                          │
   │◄── ACK lost ─────────────│
   │                          │
   │── retry TX123 ──────────►│
```

Kafka idempotence prevents the producer retry from creating an additional duplicate record.

It protects the **producer → Kafka retry boundary**.

### It does NOT protect this scenario

```text
1. Send TX123 to Kafka
2. Kafka transaction commits
3. Application crashes
4. PostgreSQL still says published=false
5. Application restarts
6. TX123 is selected again
7. Application intentionally sends TX123 again
```

Kafka idempotence should NOT be considered a solution for this DB → Kafka dual-write problem.

---

## 6. Crash Scenario the Design Must Handle

Normal successful flow:

```text
DB:
TX123 | published=false

       ↓

Kafka transaction:
    Topic A      → TX123 + full message
    Status Topic → TX123

       ↓

Status Consumer:
    TX123 → UPDATE DB

       ↓

DB:
TX123 | published=true
```

### Crash after Kafka commit

Potential failure:

```text
DB:
TX123 | published=false

       ↓

Kafka transaction commits:
    Topic A      → TX123
    Status Topic → TX123

       ↓

Application crashes
```

At this point:

```text
Kafka:
TX123 exists

PostgreSQL:
TX123 = published=false
```

On restart, the application must recover outstanding Status Topic messages **before allowing the publisher to fetch unpublished transactions**.

---

## 7. Startup Recovery

Recommended startup sequence:

```text
Application START
       │
       ▼
Start Status Consumer
       │
       ▼
Process outstanding Status Topic messages
       │
       ▼
Update PostgreSQL published=true
       │
       ▼
Wait until Status Consumer catches up
       │
       ▼
Start/enable DB Publisher
       │
       ▼
SELECT unpublished transactions
       │
       ▼
Publish using Kafka transaction
```

Do NOT start the DB publisher immediately while the Status Consumer is still catching up.

Otherwise this race is possible:

```text
Status Topic:
TX123 exists but has not been consumed yet

PostgreSQL:
TX123 = published=false

Publisher:
SELECT published=false
      ↓
TX123 selected
      ↓
Duplicate risk
```

---

## 8. Do Not Drain the Entire Topic from the Beginning Every Time

The intention is correct, but the implementation should not repeatedly consume the entire Status Topic from offset 0 before every DB query.

Instead:

- Run the Status Consumer continuously.
- On application startup, let it process all outstanding records.
- Establish a clear "caught up/recovered" point.
- Only then enable the DB publisher.
- During normal operation, the Status Consumer continues processing messages asynchronously.

Conceptually:

```text
             Application
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
 Status Consumer          DB Publisher
          │                   │
          ▼                   ▼
     Update DB           Fetch NEW records
                              │
                              ▼
                         Kafka transaction
                         ┌────┴────┐
                         ▼         ▼
                      Topic A   Status Topic
```

---

## 9. Use txn_id as the Idempotency/Business Identity

A separate `eventId` is **not required** if the business requirement is:

> One transaction ID corresponds to one Kafka event.

For example:

```text
txn_id = TX123
```

can be used as:

- Kafka message key
- Status Topic payload
- DB primary/business key
- Idempotency identity

A separate event ID would only become useful if one business transaction can produce multiple independent events, for example:

```text
TX123 → PAYMENT_CREATED
TX123 → PAYMENT_APPROVED
TX123 → PAYMENT_SETTLED
```

For the current requirement, `txn_id` is sufficient.

---

## 10. PostgreSQL State

At minimum:

```sql
CREATE TABLE transactions (
    txn_id      VARCHAR(100) PRIMARY KEY,
    amount      NUMERIC(18,2),
    published   BOOLEAN NOT NULL DEFAULT FALSE
);
```

Status update:

```sql
UPDATE transactions
SET published = TRUE
WHERE txn_id = ?
  AND published = FALSE;
```

This is intentionally idempotent.

If the same Status Topic message is processed twice:

```text
TX123
TX123
```

the first update changes the row and the second update affects zero rows.

---

## 11. Single Producer

There is only one producer instance.

This eliminates the major race where multiple application instances simultaneously execute:

```text
SELECT published=false
```

and both select the same transaction.

If multiple producer instances are introduced in the future, the DB selection must be changed to a claiming/locking strategy, such as PostgreSQL `FOR UPDATE SKIP LOCKED` or an explicit processing state.

---

## 12. Optional Better DB State Model

Instead of only:

```text
published = false / true
```

consider:

```text
NEW
PUBLISHED
```

or, if operational recovery requires it:

```text
NEW
PROCESSING
PUBLISHED
```

For example:

```text
NEW
 │
 │ select/claim
 ▼
PROCESSING
 │
 │ Kafka transaction succeeds
 ▼
PUBLISHED
```

With a single producer, `PROCESSING` may not be strictly necessary, but it can make monitoring and recovery clearer.

---

## 13. Spring Kafka Configuration

Use a transactional producer:

```properties
spring.kafka.producer.transaction-id-prefix=tx-
```

The Kafka producer should use idempotence. When Kafka transactions are enabled, the producer operates with the required idempotent semantics.

For consumers that must not see aborted transactional messages:

```properties
spring.kafka.consumer.properties.isolation.level=read_committed
```

---

## 14. Important Limitation

There is a fundamental distributed-systems limitation:

> PostgreSQL and Kafka are two separate systems and are not one atomic transaction in this design.

Therefore, the following cannot be made absolutely atomic by Kafka producer transactions alone:

```text
PostgreSQL update
       +
Kafka commit
```

The design provides strong crash recovery, but it should not be described as a mathematically guaranteed "exactly once DB-to-Kafka" protocol.

The critical dual-write window is:

```text
Kafka commit succeeds
        ↓
Application crashes
        ↓
DB has not yet been updated
```

The Status Topic + startup recovery is specifically intended to reconcile this state before the publisher selects more DB records.

---

## 15. Implementation Requirements

### Producer

Implement:

1. Single publisher instance.
2. Fetch unpublished transactions from PostgreSQL.
3. Use stable `txn_id`.
4. Start Kafka transaction.
5. Send full transaction to Topic A.
6. Send `txn_id` to Status Topic.
7. Commit Kafka transaction.
8. Do not update `published=true` directly as part of this Kafka operation.
9. Status Topic consumer is responsible for updating the DB.

### Status Consumer

Implement:

1. Consume `txn_id`.
2. Update PostgreSQL:
   ```sql
   UPDATE transactions
   SET published = TRUE
   WHERE txn_id = ?
     AND published = FALSE;
   ```
3. Commit Kafka consumer offset only after the DB update succeeds.
4. If DB update fails, do not acknowledge/commit the Kafka offset; retry the message.
5. Make the DB update idempotent.

### Startup

Implement:

1. Start Status Consumer.
2. Recover/process outstanding Status Topic records.
3. Ensure Status Consumer has caught up to the required recovery point.
4. Only then enable the DB Publisher.
5. Publisher starts selecting `published=false` records.

### Normal operation

Status Consumer should remain running continuously. Startup recovery is a safety mechanism, not the only time the Status Topic is consumed.

---

## 16. Failure Scenarios to Test

The developer should explicitly test these cases.

### Case 1 — Kafka send fails

```text
Topic A      ❌
Status Topic ❌
```

Kafka transaction aborts. DB remains unpublished.

Expected: transaction can be retried.

### Case 2 — Kafka transaction commits successfully

```text
Topic A      ✅
Status Topic ✅
```

Status Consumer eventually marks DB as published.

Expected:

```text
published=true
```

### Case 3 — Application crashes after Kafka commit

```text
Topic A      ✅
Status Topic ✅
DB           false
```

On restart, Status Topic is processed before DB publishing resumes.

Expected:

```text
DB → published=true
```

and TX123 must not be selected for republishing.

### Case 4 — DB update fails in Status Consumer

```text
Status Topic → TX123
DB update → ❌
```

Do not commit the Kafka consumer offset.

Expected: TX123 is redelivered/retried.

### Case 5 — Status message delivered twice

```text
TX123
TX123
```

Expected:

```text
First DB update  → 1 row
Second DB update → 0 rows
```

No business problem.

### Case 6 — Application crashes before Kafka transaction

```text
DB → TX123 unpublished
Kafka → nothing
```

Expected: TX123 is selected and published after restart.

### Case 7 — Producer and Status Consumer running concurrently

Ensure the publisher cannot select a transaction that has an already-committed Status Topic record which the Status Consumer has not yet applied to PostgreSQL during startup recovery.

---

## 17. Final Design Decision

For the stated constraints, implement:

**Single Producer + PostgreSQL + Kafka Transaction + Topic A + Status Topic + Continuous Status Consumer + Startup Recovery**

Use:

```text
txn_id
```

as the stable business/idempotency identity.

The core principle is:

```text
Kafka Transaction
    ├── Topic A       → complete transaction
    └── Status Topic  → txn_id

Status Consumer
    └── txn_id → PostgreSQL published=true
```

And:

```text
Application startup
    ↓
Recover Status Topic
    ↓
Synchronize PostgreSQL
    ↓
Enable DB Publisher
```

This is the recommended implementation for the current single-producer architecture, while recognizing that DB and Kafka are still separate transactional systems.
