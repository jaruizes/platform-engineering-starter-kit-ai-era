package ${{ values.rootPackage }};

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.boot.health.actuate.endpoint.HealthEndpoint;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;

/** The service starts against a real PostgreSQL (Testcontainers) and reports itself healthy. */
@SpringBootTest
@Testcontainers
class ApplicationIT {

    @Container
    @ServiceConnection
    static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer("postgres:17-alpine");

    @Autowired
    private HealthEndpoint health;

    @Test
    void givenADatabase_whenTheServiceStarts_thenItIsHealthy() {
        assertThat(health.health().getStatus().getCode()).isEqualTo("UP");
    }
}
