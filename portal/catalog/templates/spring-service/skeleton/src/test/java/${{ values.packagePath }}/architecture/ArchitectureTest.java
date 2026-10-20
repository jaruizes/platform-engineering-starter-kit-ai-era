package ${{ values.rootPackage }}.architecture;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import com.tngtech.archunit.core.domain.Dependency;
import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.lang.ArchCondition;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.lang.ConditionEvents;
import com.tngtech.archunit.lang.SimpleConditionEvent;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * The checkable part of the engineering standards (architecture rules AAC-001 to
 * AAC-004, AAC-006, AAC-012, AAC-014 and AAC-022). It runs in {@code ./mvnw verify}
 * for every change, written by a person or by an AI agent.
 *
 * <p>Do not weaken or skip these rules to make a change pass. If a rule cannot be
 * met, change the implementation or get an approved ADR (architecture-rules.md).
 */
class ArchitectureTest {

    private static final String ROOT = "${{ values.rootPackage }}";

    private static final String[] FRAMEWORK_AND_PROVIDER_PACKAGES = {
            "org.springframework..",
            "jakarta.persistence..",
            "jakarta.servlet..",
            "org.hibernate..",
            "com.fasterxml.jackson..",
            "tools.jackson..",
            "java.sql..",
            "javax.sql..",
            "org.apache.kafka..",
            "software.amazon..",
            "com.openai..",
            "com.anthropic..",
            "com.google.cloud..",
    };

    private static JavaClasses classes;

    @BeforeAll
    static void importProductionClasses() {
        classes = new ClassFileImporter()
                .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
                .importPackages(ROOT);
    }

    /** AAC-001: code is organized module first, then domain, business and infrastructure. */
    @Test
    void codeIsOrganizedByFunctionalModuleThenLayer() {
        check(classes().should().haveNameMatching(
                        ROOT.replace(".", "\\.") + "\\.([A-Z][\\w$]*|[a-z][a-z0-9]*\\.(domain|business|infrastructure)\\..+)")
                .as("classes live in <functional-module>.domain, .business or .infrastructure "
                        + "(only the application class lives in the root package)")
                .because("of architecture rule AAC-001"));
    }

    /** AAC-002: infrastructure -> business -> domain, never the other way. */
    @Test
    void domainDoesNotDependOnBusinessOrInfrastructure() {
        check(noClasses().that().resideInAPackage(ROOT + ".*.domain..")
                .should().dependOnClassesThat().resideInAnyPackage(ROOT + ".*.business..", ROOT + ".*.infrastructure..")
                .because("of architecture rule AAC-002"));
    }

    /** AAC-002 */
    @Test
    void businessDoesNotDependOnInfrastructure() {
        check(noClasses().that().resideInAPackage(ROOT + ".*.business..")
                .should().dependOnClassesThat().resideInAPackage(ROOT + ".*.infrastructure..")
                .because("of architecture rule AAC-002"));
    }

    /** AAC-003 and AAC-014: the domain is plain Java, free of frameworks and providers. */
    @Test
    void domainIsFreeOfFrameworksAndProviders() {
        check(noClasses().that().resideInAPackage(ROOT + ".*.domain..")
                .should().dependOnClassesThat().resideInAnyPackage(FRAMEWORK_AND_PROVIDER_PACKAGES)
                .because("of architecture rules AAC-003 and AAC-014"));
    }

    /** AAC-003 and AAC-014: business logic does not use persistence, HTTP or provider types. */
    @Test
    void businessDoesNotUseAdapterTechnology() {
        check(noClasses().that().resideInAPackage(ROOT + ".*.business..")
                .should().dependOnClassesThat().resideInAnyPackage(
                        "jakarta.persistence..",
                        "jakarta.servlet..",
                        "org.springframework.web..",
                        "org.springframework.data..",
                        "org.springframework.jdbc..",
                        "org.springframework.kafka..",
                        "org.apache.kafka..",
                        "software.amazon..",
                        "com.openai..",
                        "com.anthropic..",
                        "com.google.cloud..")
                .because("of architecture rules AAC-003 and AAC-014"));
    }

    /** AAC-004: REST controllers live in infrastructure.api.rest. */
    @Test
    void restControllersLiveInInfrastructureApiRest() {
        check(classes().that().areAnnotatedWith(org.springframework.web.bind.annotation.RestController.class)
                .should().resideInAPackage(ROOT + ".*.infrastructure.api.rest..")
                .because("of architecture rule AAC-004")
                .allowEmptyShould(true));
    }

    /** AAC-004 and AAC-012: JPA entities and Spring Data repositories live in infrastructure.persistence. */
    @Test
    void persistenceLivesInInfrastructurePersistence() {
        check(classes().that().areAnnotatedWith(jakarta.persistence.Entity.class)
                .or().areAssignableTo(org.springframework.data.repository.Repository.class)
                .should().resideInAPackage(ROOT + ".*.infrastructure.persistence..")
                .because("of architecture rules AAC-004 and AAC-012")
                .allowEmptyShould(true));
    }

    /** AAC-012: direct JDBC is an exception and stays inside persistence adapters. */
    @Test
    void directJdbcStaysInPersistenceAdapters() {
        check(noClasses().that().resideOutsideOfPackage(ROOT + ".*.infrastructure.persistence..")
                .should().dependOnClassesThat().resideInAnyPackage("org.springframework.jdbc..", "java.sql..")
                .because("of architecture rule AAC-012")
                .allowEmptyShould(true));
    }

    /** AAC-006: a module never reads or writes another module's persistence. */
    @Test
    void modulesDoNotUseOtherModulesPersistence() {
        check(classes().should(notUseThePersistenceOfOtherModules())
                .because("of architecture rule AAC-006")
                .allowEmptyShould(true));
    }

    private static ArchCondition<JavaClass> notUseThePersistenceOfOtherModules() {
        return new ArchCondition<>("not use the persistence of other functional modules") {
            @Override
            public void check(JavaClass origin, ConditionEvents events) {
                String module = moduleOf(origin.getPackageName());
                for (Dependency dependency : origin.getDirectDependenciesFromSelf()) {
                    String target = dependency.getTargetClass().getPackageName();
                    String targetModule = moduleOf(target);
                    if (targetModule != null && !targetModule.equals(module)
                            && target.contains(".infrastructure.persistence")) {
                        events.add(SimpleConditionEvent.violated(dependency, dependency.getDescription()));
                    }
                }
            }
        };
    }

    private static String moduleOf(String packageName) {
        if (!packageName.startsWith(ROOT + ".")) {
            return null;
        }
        String rest = packageName.substring(ROOT.length() + 1);
        int dot = rest.indexOf('.');
        return dot < 0 ? rest : rest.substring(0, dot);
    }

    private static void check(ArchRule rule) {
        rule.check(classes);
    }
}
