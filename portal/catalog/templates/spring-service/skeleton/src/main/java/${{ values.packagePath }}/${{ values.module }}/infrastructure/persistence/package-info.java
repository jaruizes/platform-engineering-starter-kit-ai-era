/**
 * Persistence adapters: they implement domain ports with Spring Data JPA.
 * JPA entities go in {@code entity} and are never used as domain models;
 * repositories go in {@code repository} (AAC-012). Schema changes are Flyway
 * migrations in {@code src/main/resources/db/migration}.
 */
package ${{ values.rootPackage }}.${{ values.module }}.infrastructure.persistence;
