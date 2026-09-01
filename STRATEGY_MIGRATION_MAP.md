# Strategy Migration Map - ZenAlgo Strategy Builder

This document details the mapping of Strategy Builder JSON fields (schema version `2.0.0`) to the relational PostgreSQL database tables.

---

## 1. Database Model Field Mapping

The existing `strategies` and `strategy_versions` tables in PostgreSQL will remain the source-of-truth. High-fidelity Strategy Builder JSON fields will be mapped as follows:

| Strategy JSON Field (Version 2.0.0) | Relational Database Column | Notes / Storage Model |
| :--- | :--- | :--- |
| `schemaVersion` | - | Validated in parser; not stored in DB columns |
| `executionEngine` | - | Validated in parser; always `ZENALGO_QUANT_ENGINE` |
| `meta.strategyId` | `strategies.id` (mapped as string/int) | Generated automatically by PostgreSQL PK |
| `meta.strategyName` | `strategies.name` | Synchronized on insert/update |
| `meta.status` | `strategies.status` | State transitions validated by service |
| `description` | `strategies.description` | Text description column |
| `youtubeUrl` | `strategies.parameters` &rarr; `youtubeUrl` | Saved inside serialized parameters JSON |
| `coreIdea` | `strategies.parameters` &rarr; `coreIdea` | Saved inside serialized parameters JSON |
| `category` | `strategies.parameters` &rarr; `category` | Saved inside serialized parameters JSON |
| `marketBias` | `strategies.parameters` &rarr; `marketBias` | Saved inside serialized parameters JSON |
| `timeframe` | `strategies.parameters` &rarr; `timeframe` | Inherited as default rules timeframe |
| `instrument` | `strategy_versions.underlying` | Underlying index stored on active version |
| `schedule.entryFrom` | `strategy_entry_settings.entry_time` | Relational execution schedule |
| `schedule.entryTo` | `strategies.parameters` &rarr; `entryTo` | Serialized parameter check |
| `schedule.forcedExitTime` | `strategy_exit_settings.exit_time` | Relational execution exit |
| `schedule.applicableDays` | `strategy_entry_days.day_of_week` | Relational entry day restrictions |
| `entryConditions` | `strategies.parameters` &rarr; `entryConditions` | Serialized structured logical tree JSON |
| `exitConditions` | `strategies.parameters` &rarr; `exitConditions` | Serialized structured logical tree JSON |
| `keyRememberPoints` | `strategies.parameters` &rarr; `keyRememberPoints` | Serialized confirmations JSON |
| `riskManagement` | `strategies.parameters` &rarr; `riskManagement` | Serialized structured risk configs |
| `target` | `strategies.parameters` &rarr; `target` | Serialized structured targets JSON |

---

## 2. API Endpoints Upgraded

The endpoints will be restructured from `/api/v1/admin/strategies` to `/api/v1/strategies` for strategy builders:

* **`POST /api/v1/strategies`**: Creates a new strategy with logic verification and serializes parameters.
* **`GET /api/v1/strategies/{id}`**: Deserializes the strategy builder JSON structure and returns it.
* **`PUT /api/v1/strategies/{id}`**: Handles updates, validating if the version has executions to enforce version immutability.
* **`POST /api/v1/strategies/validate`**: Performs full schema, metadata, rules, and risk validation.
* **`POST /api/v1/strategies/preview`**: Translates a natural language string and explains the logical crossover/candle close semantics.
* **`POST /api/v1/strategies/generate`**: Accepts rule inputs and generates a ready-to-run schema version `2.0.0` Strategy JSON.
