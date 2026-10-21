# Examples: backend v2 (hexagonal Spring)

## Purpose

These are compliant and non-compliant code examples for backend v2, showing how the rules in `architecture-rules.md` (AAC-001 to AAC-022) look in real Spring code.

The examples use the package names of the Spring service template: root package `com.starterkit.checkout`, functional module `payments`. Imports and boilerplate are trimmed. `architecture.md` remains the reference.

---

# 1. Compliant Module

## Package Layout

```text
com.starterkit.checkout.payments
├── domain/model/            Payment, Money, PaymentStatus
├── domain/ports/            PaymentRepository
├── domain/exceptions/       PaymentNotFoundException
├── business/                CapturePayment
└── infrastructure/
    ├── api/rest/            PaymentController, dto/, mapper/
    └── persistence/         JpaPaymentRepositoryAdapter, entity/, repository/, mapper/
```

## Domain Model

Plain Java. No Spring, JPA or Jackson imports (AAC-003). Money uses `BigDecimal` (DR-005).

```java
package com.starterkit.checkout.payments.domain.model;

public record Money(BigDecimal amount, String currency) {
    public Money {
        if (amount.signum() < 0) throw new IllegalArgumentException("negative amount");
    }
}

public class Payment {
    private final PaymentId id;
    private final Money amount;
    private PaymentStatus status;

    public void capture() {
        if (status != PaymentStatus.AUTHORIZED) throw new IllegalStateException("not authorized");
        status = PaymentStatus.CAPTURED;
    }
}
```

## Port

The port lives in `domain.ports` and speaks only domain types.

```java
package com.starterkit.checkout.payments.domain.ports;

public interface PaymentRepository {
    Optional<Payment> findById(PaymentId id);
    void save(Payment payment);
}
```

## Use Case

`business` orchestrates and owns the transaction. Spring is allowed for injection and transactions, not for web or data access.

```java
package com.starterkit.checkout.payments.business;

@Service
public class CapturePayment {
    private final PaymentRepository payments;

    @Transactional
    public Payment execute(PaymentId id) {
        Payment payment = payments.findById(id)
                .orElseThrow(() -> new PaymentNotFoundException(id));
        payment.capture();
        payments.save(payment);
        return payment;
    }
}
```

## REST Adapter

The controller translates HTTP to a use case call. It holds no business logic (AAC-003, AAC-004).

```java
package com.starterkit.checkout.payments.infrastructure.api.rest;

@RestController
@RequestMapping("/payments")
class PaymentController {
    private final CapturePayment capturePayment;
    private final PaymentRestMapper mapper;

    @PostMapping("/{id}/capture")
    PaymentResponse capture(@PathVariable UUID id) {
        return mapper.toResponse(capturePayment.execute(new PaymentId(id)));
    }
}
```

## Persistence Adapter and Mapping

The JPA entity is an infrastructure model (AAC-012). The adapter implements the domain port and maps both ways.

```java
package com.starterkit.checkout.payments.infrastructure.persistence;

@Component
class JpaPaymentRepositoryAdapter implements PaymentRepository {
    private final SpringDataPaymentRepository repository;
    private final PaymentEntityMapper mapper;

    public Optional<Payment> findById(PaymentId id) {
        return repository.findById(id.value()).map(mapper::toDomain);
    }

    public void save(Payment payment) {
        repository.save(mapper.toEntity(payment));
    }
}
```

```java
package com.starterkit.checkout.payments.infrastructure.persistence.mapper;

@Component
class PaymentEntityMapper {
    Payment toDomain(PaymentEntity e) {
        return Payment.restore(new PaymentId(e.getId()),
                new Money(e.getAmount(), e.getCurrency()), PaymentStatus.valueOf(e.getStatus()));
    }

    PaymentEntity toEntity(Payment p) {
        return new PaymentEntity(p.id().value(), p.amount().amount(),
                p.amount().currency(), p.status().name());
    }
}
```

## ArchUnit Check

This excerpt from `ArchitectureTest.java` enforces the dependency direction (AAC-002, AAC-022). It runs in `./mvnw verify`.

```java
@Test
void businessDoesNotDependOnInfrastructure() {
    check(noClasses().that().resideInAPackage(ROOT + ".*.business..")
            .should().dependOnClassesThat().resideInAPackage(ROOT + ".*.infrastructure..")
            .because("of architecture rule AAC-002"));
}
```

---

# 2. Non-Compliant Examples

## JPA Annotation in the Domain

```java
package com.starterkit.checkout.payments.domain.model;

@Entity
@Table(name = "payment")
public class Payment { @Id private UUID id; ... }
```

**Why:** breaks AAC-003 (domain depends on JPA) and AAC-012 (a JPA entity becomes the domain model). `domainIsFreeOfFrameworksAndProviders` fails.

**Fix:** keep `Payment` plain. Add `PaymentEntity` in `infrastructure.persistence.entity` and map it in the persistence adapter.

## Controller Calling a Repository

```java
@RestController
class PaymentController {
    private final SpringDataPaymentRepository repository;

    @PostMapping("/{id}/capture")
    void capture(@PathVariable UUID id) {
        PaymentEntity e = repository.findById(id).orElseThrow();
        e.setStatus("CAPTURED");
        repository.save(e);
    }
}
```

**Why:** breaks AAC-003 (the capture rule is hidden in a controller) and AAC-002 in spirit: the request skips `business` and `domain`. The rule "only authorized payments can be captured" is lost.

**Fix:** the controller calls the `CapturePayment` use case. The use case calls `Payment.capture()` and the `PaymentRepository` port.

## Module Reading Another Module's Table

```java
package com.starterkit.checkout.payments.business;

import com.starterkit.checkout.orders.infrastructure.persistence.repository.SpringDataOrderRepository;

class CapturePayment {
    private final SpringDataOrderRepository orders; // reads the orders table
}
```

**Why:** breaks AAC-006 (module ownership) and AAC-002 (`business` depends on `infrastructure`). `modulesDoNotUseOtherModulesPersistence` fails.

**Fix:** `payments` declares a port in its own domain, for example `OrderLookup`, with a domain-oriented return type. An adapter in `payments.infrastructure` implements it by calling the interface that `orders` publishes (a use case, API or event), never its tables or entities.

---

# 3. Migrating from Backend v1

Backend v1 used technical layers (`controller`, `service`, `repository`) with JPA entities used everywhere.

## Before (v1)

```java
package com.starterkit.checkout.service;

@Service
public class PaymentService {
    @Autowired private PaymentJpaRepository repository;

    public PaymentEntity capture(UUID id) {
        PaymentEntity e = repository.findById(id).orElseThrow();
        if (!"AUTHORIZED".equals(e.getStatus())) throw new IllegalStateException();
        e.setStatus("CAPTURED");
        return repository.save(e);
    }
}
```

## After (v2)

```text
payments/domain/model/Payment.java                       rule moves into Payment.capture()
payments/domain/ports/PaymentRepository.java             new port
payments/business/CapturePayment.java                    replaces PaymentService.capture
payments/infrastructure/persistence/
    entity/PaymentEntity.java                            former PaymentEntity, moved
    repository/SpringDataPaymentRepository.java          former PaymentJpaRepository
    JpaPaymentRepositoryAdapter.java                     implements the port
payments/infrastructure/api/rest/PaymentController.java  calls CapturePayment
```

Steps:

1. Create the module package (`payments`) and its three layers (AAC-001).
2. Move the business rule from the service into the domain model.
3. Define the port with domain types, then write the use case against it.
4. Move the JPA entity and repository under `infrastructure.persistence` and add the adapter and mapper.
5. Run `./mvnw verify`. `ArchitectureTest` must pass without weakening any rule (AAC-022).

Migrate one use case at a time. Do not mix v1 layers and v2 packages inside the same module.
