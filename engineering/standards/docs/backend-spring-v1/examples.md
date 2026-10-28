# Examples: backend v1 (layered)

## Purpose

Short, realistic Java examples of compliant and non-compliant code for Backend Spring v1 (layered, deprecated), each tied to the rules in `architecture-rules.md`.

The examples use an `orders` service under `com.example.orders`. They show the minimum needed to make the point; imports and some annotations are omitted.

---

# Compliant Examples

## Controller

Validates input, maps DTOs and delegates to the service (BL-004, BL-006, BL-007, BL-008).

```java
package com.example.orders.controller;

@RestController
@RequestMapping("/api/v1/orders")
@RequiredArgsConstructor
class OrderController {

    private final OrderService orderService;
    private final OrderMapper mapper;

    @PostMapping
    ResponseEntity<OrderResponse> create(@Valid @RequestBody CreateOrderRequest request) {
        Order order = orderService.create(mapper.toCommand(request));
        return ResponseEntity.created(URI.create("/api/v1/orders/" + order.getId()))
                .body(mapper.toResponse(order));
    }

    @GetMapping("/{id}")
    OrderResponse get(@PathVariable UUID id) {
        return mapper.toResponse(orderService.get(id));
    }
}
```

## Service

Owns the business rule and the transaction (BL-003, BL-011).

```java
package com.example.orders.service;

@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderRepository orders;

    @Transactional
    public Order create(CreateOrderCommand command) {
        if (command.lines().isEmpty()) {
            throw new InvalidOrderException("An order needs at least one line");
        }
        return orders.save(Order.place(command.customerId(), command.lines()));
    }

    @Transactional(readOnly = true)
    public Order get(UUID id) {
        return orders.findById(id).orElseThrow(() -> new OrderNotFoundException(id));
    }
}
```

## Repository

Spring Data JPA with a JPQL fetch join instead of native SQL (BL-013).

```java
package com.example.orders.repository;

public interface OrderRepository extends JpaRepository<Order, UUID> {

    @Query("select o from Order o join fetch o.lines where o.customerId = :customerId")
    List<Order> findWithLinesByCustomerId(UUID customerId);
}
```

## DTO and Mapping

Request DTO with Bean Validation, and a MapStruct mapper (BL-006, BL-008).

```java
package com.example.orders.dto;

public record CreateOrderRequest(
        @NotNull UUID customerId,
        @NotEmpty List<@Valid OrderLineRequest> lines) {}

public record OrderResponse(UUID id, String status, BigDecimal total) {}

@Mapper(componentModel = "spring")
public interface OrderMapper {
    CreateOrderCommand toCommand(CreateOrderRequest request);

    @Mapping(target = "status", expression = "java(order.getStatus().name())")
    OrderResponse toResponse(Order order);
}
```

## Error Handler

One global handler producing Problem Details (BL-010).

```java
package com.example.orders.exception;

@RestControllerAdvice
class GlobalExceptionHandler {

    @ExceptionHandler(OrderNotFoundException.class)
    ProblemDetail notFound(OrderNotFoundException ex) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
    }

    @ExceptionHandler(InvalidOrderException.class)
    ProblemDetail invalid(InvalidOrderException ex) {
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
@AnalyzeClasses(packages = "com.example.orders", importOptions = DoNotIncludeTests.class)
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
            slices().matching("com.example.orders.(**)").should().beFreeOfCycles();

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
Order get(@PathVariable UUID id) {
    return orderRepository.findById(id).orElseThrow();
}
```

**Why it fails:** the controller accesses a repository directly (BL-004) and returns a JPA entity to the client (BL-006). Lazy associations, internal fields and the table structure leak into the API, and `orElseThrow()` produces a generic `500` instead of a `404` (BL-010).

**Fix:** call `orderService.get(id)`, which throws `OrderNotFoundException`, and return `mapper.toResponse(...)`, as in the compliant controller above.

## 2. Business Logic and Transaction in the Controller

```java
@PostMapping("/{id}/cancel")
@Transactional
ResponseEntity<Void> cancel(@PathVariable UUID id) {
    Order order = orderService.get(id);
    if (order.getStatus() == Status.SHIPPED) {
        return ResponseEntity.status(409).build();
    }
    order.setStatus(Status.CANCELLED);
    return ResponseEntity.noContent().build();
}
```

**Why it fails:** the state transition rule lives in the controller (BL-007), the transaction is opened in the controller (BL-011), and the error response is built by hand instead of by the global handler (BL-010).

**Fix:** move the rule into the entity or service and keep the controller thin.

```java
// service
@Transactional
public void cancel(UUID id) {
    get(id).cancel(); // throws InvalidOrderStateException if already shipped
}

// controller
@PostMapping("/{id}/cancel")
ResponseEntity<Void> cancel(@PathVariable UUID id) {
    orderService.cancel(id);
    return ResponseEntity.noContent().build();
}
```

## 3. Half-Mixed Hexagonal Packages

```text
com.example.orders/
├── controller/
├── service/
│   ├── OrderService.java
│   └── ports/              ← new "port" interfaces
│       └── PaymentPort.java
└── domain/                 ← new plain domain classes
    └── Payment.java
```

**Why it fails:** hexagonal packages were added inside a layered service without an ADR (BL-015). The result is neither v1 nor v2: the layered ArchUnit test does not know about `domain`, and no v2 rule checks it. `PaymentPort` inside `service/` also blurs who owns the payment logic.

**Fix:** either keep the change inside the existing layers, or write an ADR and migrate the payment area as a full v2 module:

```text
com.example.orders/
├── controller/  service/  repository/  model/  dto/   (remaining v1 code)
└── payment/
    ├── domain/
    ├── business/
    └── infrastructure/
```

with its own v2 ArchUnit rules, and with the layered code calling `payment` only through its published port.
