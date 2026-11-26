# Examples: backend v1 (layered)

## Purpose

Short, realistic Java examples of compliant and non-compliant code for Backend Spring v1 (layered, deprecated), each tied to the rules in `architecture-rules.md`.

The examples use a `records` service under `com.example.records`. They show the minimum needed to make the point; imports and some annotations are omitted.

---

# Compliant Examples

## Controller

Validates input, maps DTOs and delegates to the service (BL-004, BL-006, BL-007, BL-008).

```java
package com.example.records.controller;

@RestController
@RequestMapping("/api/v1/records")
@RequiredArgsConstructor
class RecordController {

    private final RecordService recordService;
    private final RecordMapper mapper;

    @PostMapping
    ResponseEntity<RecordResponse> create(@Valid @RequestBody CreateRecordRequest request) {
        Record record = recordService.create(mapper.toCommand(request));
        return ResponseEntity.created(URI.create("/api/v1/records/" + record.getId()))
                .body(mapper.toResponse(record));
    }

    @GetMapping("/{id}")
    RecordResponse get(@PathVariable UUID id) {
        return mapper.toResponse(recordService.get(id));
    }
}
```

## Service

Owns the business rule and the transaction (BL-003, BL-011).

```java
package com.example.records.service;

@Service
@RequiredArgsConstructor
public class RecordService {

    private final RecordRepository records;

    @Transactional
    public Record create(CreateRecordCommand command) {
        if (command.attributes().isEmpty()) {
            throw new InvalidRecordException("A record needs at least one line");
        }
        return records.save(Record.place(command.ownerId(), command.attributes()));
    }

    @Transactional(readOnly = true)
    public Record get(UUID id) {
        return records.findById(id).orElseThrow(() -> new RecordNotFoundException(id));
    }
}
```

## Repository

Spring Data JPA with a JPQL fetch join instead of native SQL (BL-013).

```java
package com.example.records.repository;

public interface RecordRepository extends JpaRepository<Record, UUID> {

    @Query("select o from Record o join fetch o.attributes where o.ownerId = :ownerId")
    List<Record> findWithAttributesByOwnerId(UUID ownerId);
}
```

## DTO and Mapping

Request DTO with Bean Validation, and a MapStruct mapper (BL-006, BL-008).

```java
package com.example.records.dto;

public record CreateRecordRequest(
        @NotNull UUID ownerId,
        @NotEmpty Map<String, String> attributes) {}

public record RecordResponse(UUID id, String status, BigDecimal total) {}

@Mapper(componentModel = "spring")
public interface RecordMapper {
    CreateRecordCommand toCommand(CreateRecordRequest request);

    @Mapping(target = "status", expression = "java(record.getStatus().name())")
    RecordResponse toResponse(Record record);
}
```

## Error Handler

One global handler producing Problem Details (BL-010).

```java
package com.example.records.exception;

@RestControllerAdvice
class GlobalExceptionHandler {

    @ExceptionHandler(RecordNotFoundException.class)
    ProblemDetail notFound(RecordNotFoundException ex) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
    }

    @ExceptionHandler(InvalidRecordException.class)
    ProblemDetail invalid(InvalidRecordException ex) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.UNPROCESSABLE_ENTITY, ex.getMessage());
    }

    @ExceptionHandler(Exception.class)
    ProblemDetail unexpected(Exception ex) {
        log.error("Unexpected error", ex);
        return ProblemDetail.forStatusAndDetail(HttpStatus.INTERNAL_SERVER_ERROR, "Unexpected error");
    }
}
```

## ArchUnit Layered Test

Enforces BL-002 to BL-006 and BL-011 (BL-014).

```java
@AnalyzeClasses(packages = "com.example.records", importOptions = DoNotIncludeTests.class)
class LayeredArchitectureTest {

    @ArchTest
    static final ArchRule layers = layeredArchitecture().consideringOnlyDependenciesInLayers()
            .layer("Controller").definedBy("..controller..")
            .layer("Service").definedBy("..service..")
            .layer("Repository").definedBy("..repository..")
            .whereLayer("Controller").mayNotBeAccessedByAnyLayer()
            .whereLayer("Service").mayOnlyBeAccessedByLayers("Controller")
            .whereLayer("Repository").mayOnlyBeAccessedByLayers("Service");

    @ArchTest
    static final ArchRule noCycles =
            slices().matching("com.example.records.(**)").should().beFreeOfCycles();

    @ArchTest
    static final ArchRule noEntitiesInControllerApi = methods()
            .that().areDeclaredInClassesThat().resideInAPackage("..controller..")
            .should().notHaveRawReturnType(annotatedWith(Entity.class));

    @ArchTest
    static final ArchRule transactionsInServices = noMethods()
            .that().areAnnotatedWith(Transactional.class)
            .should().beDeclaredInClassesThat().resideOutsideOfPackage("..service..");
}
```

---

# Non-Compliant Examples

## 1. Controller Calls the Repository

```java
@GetMapping("/{id}")
Record get(@PathVariable UUID id) {
    return recordRepository.findById(id).orElseThrow();
}
```

**Why it fails:** the controller accesses a repository directly (BL-004) and returns a JPA entity to the client (BL-006). Lazy associations, internal fields and the table structure leak into the API, and `orElseThrow()` produces a generic `500` instead of a `404` (BL-010).

**Fix:** call `recordService.get(id)`, which throws `RecordNotFoundException`, and return `mapper.toResponse(...)`, as in the compliant controller above.

## 2. Business Logic and Transaction in the Controller

```java
@PostMapping("/{id}/cancel")
@Transactional
ResponseEntity<Void> cancel(@PathVariable UUID id) {
    Record record = recordService.get(id);
    if (record.getStatus() == Status.SHIPPED) {
        return ResponseEntity.status(409).build();
    }
    record.setStatus(Status.CANCELLED);
    return ResponseEntity.noContent().build();
}
```

**Why it fails:** the state transition rule lives in the controller (BL-007), the transaction is opened in the controller (BL-011), and the error response is built by hand instead of by the global handler (BL-010).

**Fix:** move the rule into the entity or service and keep the controller thin.

```java
// service
@Transactional
public void cancel(UUID id) {
    get(id).cancel(); // throws InvalidRecordStateException if already shipped
}

// controller
@PostMapping("/{id}/cancel")
ResponseEntity<Void> cancel(@PathVariable UUID id) {
    recordService.cancel(id);
    return ResponseEntity.noContent().build();
}
```

## 3. Half-Mixed Hexagonal Packages

```text
com.example.records/
├── controller/
├── service/
│   ├── RecordService.java
│   └── ports/              ← new "port" interfaces
│       └── RecordPort.java
└── domain/                 ← new plain domain classes
    └── Record.java
```

**Why it fails:** hexagonal packages were added inside a layered service without an ADR (BL-015). The result is neither v1 nor v2: the layered ArchUnit test does not know about `domain`, and no v2 rule checks it. `RecordPort` inside `service/` also blurs who owns the module behavior.

**Fix:** either keep the change inside the existing layers, or write an ADR and migrate the module as a full v2 module:

```text
com.example.records/
├── controller/  service/  repository/  model/  dto/   (remaining v1 code)
└── records/
    ├── domain/
    ├── business/
    └── infrastructure/
```

with its own v2 ArchUnit rules, and with the layered code calling `module` only through its published port.
