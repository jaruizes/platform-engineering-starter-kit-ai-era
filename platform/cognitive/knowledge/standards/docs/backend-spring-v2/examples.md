# Examples: backend v2 (hexagonal Spring)

## Purpose

These examples illustrate architecture rules `AAC-001` to `AAC-022` using a neutral example module. They are illustrative; service-specific terminology and behavior come from the service's product definition.

---

# 1. Compliant Module

## Package Layout

```text
com.example.application.records
├── domain/model/            Record, RecordId, RecordStatus
├── domain/ports/            RecordRepository
├── domain/exceptions/       RecordNotFoundException
├── business/                UpdateRecord
└── infrastructure/
    ├── api/rest/            RecordController, dto/, mapper/
    └── persistence/         JpaRecordRepositoryAdapter, entity/, repository/, mapper/
```

## Domain Model

Domain types contain product rules but no framework or persistence annotations (AAC-003).

```java
package com.example.application.records.domain.model;

public record RecordId(UUID value) {}

public class Record {
    private final RecordId id;
    private RecordStatus status;

    public void complete() {
        if (status != RecordStatus.ACTIVE) {
            throw new IllegalStateException("record is not active");
        }
        status = RecordStatus.COMPLETE;
    }
}
```

## Port

A domain port uses domain types and expresses the capability needed by the application core.

```java
package com.example.application.records.domain.ports;

public interface RecordRepository {
    Optional<Record> findById(RecordId id);
    void save(Record record);
}
```

## Use Case

The business layer coordinates the operation through domain behavior and ports.

```java
package com.example.application.records.business;

@Service
public class UpdateRecord {
    private final RecordRepository records;

    @Transactional
    public Record complete(RecordId id) {
        Record record = records.findById(id)
                .orElseThrow(() -> new RecordNotFoundException(id));
        record.complete();
        records.save(record);
        return record;
    }
}
```

## REST Adapter

The adapter translates the transport contract into an application call. It contains no product rules.

```java
package com.example.application.records.infrastructure.api.rest;

@RestController
@RequestMapping("/records")
class RecordController {
    private final UpdateRecord updateRecord;
    private final RecordRestMapper mapper;

    @PostMapping("/{id}/complete")
    RecordResponse complete(@PathVariable UUID id) {
        return mapper.toResponse(updateRecord.complete(new RecordId(id)));
    }
}
```

## Architecture Test

An ArchUnit test can enforce the dependency direction (AAC-002, AAC-022).

```java
@Test
void businessDoesNotDependOnInfrastructure() {
    check(noClasses().that().resideInAPackage(ROOT + ".*.business..")
            .should().dependOnClassesThat().resideInAPackage(ROOT + ".*.infrastructure.."));
}
```

---

# 2. Non-Compliant Examples

## Persistence Annotation in the Domain

```java
@Entity
@Table(name = "records")
public class Record { @Id private UUID id; }
```

**Why:** the domain now depends on a persistence framework and its representation becomes the persistence model (AAC-003, AAC-012).

**Fix:** keep the domain type framework-independent. Add a persistence entity under `infrastructure.persistence.entity` and map it in the adapter.

## Controller Calling a Repository

```java
@RestController
class RecordController {
    private final SpringDataRecordRepository repository;

    @PostMapping("/{id}/complete")
    void complete(UUID id) {
        RecordEntity record = repository.findById(id).orElseThrow();
        record.setStatus("COMPLETE");
        repository.save(record);
    }
}
```

**Why:** the transport adapter bypasses the application and domain behavior (AAC-003, AAC-004).

**Fix:** call an application use case which invokes domain behavior through a port.

## Cross-Module Persistence Access

```java
class RebuildIndex {
    private final OtherModuleJpaRepository repository;
}
```

**Why:** one module depends on another module's persistence representation (AAC-006).

**Fix:** depend on an explicit published interface, port, API, or contract.
