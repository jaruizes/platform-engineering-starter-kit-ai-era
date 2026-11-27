# Usuarios y equipos de la demo

Organización de ejemplo con la que se inicia sesión en el portal, en `platformctl` y en los agentes (Claude Code, Gemini CLI, Codex). Todas las personas existen a la vez en Keycloak (realm `platform`) y en el catálogo del portal, generadas desde un único fichero: [`platform/access/identity/organization.yaml`](../../../../platform/access/identity/organization.yaml).

- **Contraseña:** `demo` en local (`make up`). En AWS es aleatoria: la muestra `make aws-up` al terminar y está en `DEMO_PASSWORD` de `deploy/aws/.state/tokens.env`.
- **Dónde se inicia sesión:** portal <http://localhost:7007>, Keycloak <http://localhost:8180/realms/platform/account>, `platform/access/cli/platformctl.py login`, y el navegador que abre el agente la primera vez que usa el servidor MCP `platform`.
- **Cambiar de persona en el portal:** menú de usuario, *Sign out*, y volver a entrar. Si Keycloak recuerda la sesión anterior, cerrarla en <http://localhost:8180/realms/platform/account> o usar una ventana privada (una ventana por persona es lo más cómodo en la demo).

## Equipos

| Equipo | Qué representa | Miembros | Aprobadores |
|---|---|---|---|
| `platform-team` | Equipo de plataforma. Propone capacidades y ve todo | ana, pablo | ana (aprueba para todos los equipos) |
| `checkout` | Checkout de la tienda online. Protagonista del acto 2 | marta, carlos, irene | carlos |
| `payments` | Medios de pago y devoluciones. Actos 1, 4 y 5 | luis, sofia, irene | luis |
| `retail` | Ventas en tienda. Demo Retail Sales Insights | elena, diego | elena |

## Personas

| Usuario | Nombre | Equipos | Roles | Para qué sirve en las pruebas |
|---|---|---|---|---|
| `ana` | Ana García | platform-team | developer, approver | Aprobadora de plataforma: ve todo y aprueba peticiones de cualquier equipo. Propone capacidades. No puede pedir entornos para otros equipos |
| `pablo` | Pablo Herrera | platform-team | developer | Ingeniero de plataforma sin rol de aprobador: ve todo y propone capacidades, pero no aprueba |
| `marta` | Marta López | checkout | developer | Desarrolladora con su agente (acto 2). Su agente nunca hace más que ella, y ella no aprueba lo que su agente pide |
| `carlos` | Carlos Ruiz | checkout | developer, approver | Responsable técnico de checkout: aprueba lo que el agente de Marta no puede hacer solo |
| `luis` | Luis Martín | payments | developer, approver | Aprobador de otro equipo: no ve ni puede aprobar peticiones de checkout |
| `sofia` | Sofía Navarro | payments | developer | Desarrolladora de payments: actos 1, 4 y 5 en el portal |
| `elena` | Elena Torres | retail | developer, approver | Responsable de retail: aprueba las peticiones de los agentes de retail |
| `diego` | Diego Sánchez | retail | developer | Desarrollador de retail: ejecuta la demo Retail Sales Insights con su agente |
| `irene` | Irene Gómez | checkout, payments | developer | Pertenece a dos equipos: ella y su agente pueden actuar para ambos, y para nada más |
| `nora` | Nora Vidal | (ninguno) | developer | Recién incorporada sin equipo: puede iniciar sesión, pero no ve ni puede pedir nada |

Reglas que aplica la API de la plataforma (ver [identidad y acceso](../../../../docs/identity-and-access.md)):

- **Ámbito de equipo:** cada persona crea, lee y borra solo lo de sus equipos; `platform-team` lee todo. Un agente tiene exactamente los equipos de su persona.
- **Guardarraíles de agentes:** los agentes solo piden entornos `small` por su cuenta; lo demás pasa a aprobación. Una persona no tiene ese límite.
- **Aprobaciones:** solo personas con rol `approver`, para sus equipos (los aprobadores de `platform-team`, para todos), y nunca sobre una petición hecha en su nombre (cuatro ojos). Los agentes nunca aprueban.
- **Propuestas de capacidades:** solo personas de `platform-team`.
- **Para todos:** TTL máximo 72 h y como mucho 3 entornos activos por equipo; aprobar no se salta estos límites.

## Agentes (clientes de Keycloak)

| Cliente | Quién es | Cómo inicia sesión |
|---|---|---|
| `claude-code` | Claude Code, en nombre de la persona que inicia sesión | OAuth con PKCE: `/mcp` en Claude Code abre el navegador (puerto de retorno 33418) |
| `gemini-cli` | Gemini CLI, en nombre de la persona | OAuth con PKCE desde Gemini CLI |
| `codex` | Codex, en nombre de la persona | `platformctl.py login --client codex` y `PLATFORM_TOKEN` |
| `ci-agent` | Agente autónomo del equipo checkout (`make demo-agent`) | Credenciales de cliente, sin persona detrás |
| `capability-tests` | Agente autónomo de las pruebas de capacidades | Credenciales de cliente |
| `portal` | El portal (Backstage), para las personas | Login OIDC; el portal envía el token de la persona a la API |
| `platformctl` | La línea de comandos, para las personas | Device flow: `platformctl.py login` |

## Matriz de pruebas

Cada fila se puede probar desde el portal, con `platformctl` o con un agente que haya iniciado sesión como esa persona. Los nombres de entorno son ejemplos.

| # | Quién | Qué hace | Resultado esperado |
|---|---|---|---|
| 1 | sofia (portal) | Entorno `payments-dev`, equipo payments, medium, 48 h | Creado; *requested by* sofia, humano |
| 2 | sofia (portal) | Entorno para checkout | **Denegado**: no está en checkout |
| 3 | agente de marta | Entorno small para checkout | Creado; agente `claude-code` en nombre de marta |
| 4 | agente de marta | Entorno para payments | **Denegado** por ámbito de equipo (API y Kyverno) |
| 5 | agente de marta | Entorno large para checkout | Pasa a **aprobación** con un id |
| 6 | marta (portal) | Abre la petición del paso 5 | La ve, pero sin botón *Approve*: no es aprobadora y es en su nombre |
| 7 | luis (portal) | Busca la petición del paso 5 | No la ve: es de checkout |
| 8 | carlos (portal o `platformctl approve <id>`) | Aprueba la petición del paso 5 | **Aprobada**; el entorno lleva *approved by* carlos y *on behalf of* marta |
| 9 | agente de marta | Entorno de 2 semanas | **Denegado** por el TTL de 72 h, aunque alguien lo apruebe |
| 10 | agente de irene | Entornos para checkout y para payments | Ambos creados; para retail, denegado |
| 11 | nora (portal) | Abre AI Platform o pide un entorno | No ve nada; cualquier petición, **denegada** (sin equipo) |
| 12 | pablo (portal) | Ve AI Platform y una aprobación pendiente | Ve todos los equipos, pero no puede aprobar (no es aprobador) |
| 13 | ana o pablo (portal) | *New platform capability* | Abre el pull request; sofia recibe una denegación |
| 14 | agente de marta | Borra el entorno de sofia (`payments-dev`) | **Denegado**: no es de su equipo ni lo pidió un agente para marta |
| 15 | diego con su agente | Demo Retail Sales Insights en el equipo retail | Igual que la [guía de ejecución](execution-guide.md), con propietario `retail` |
| 16 | administrador de Keycloak | Desactiva el cliente `claude-code` o cierra la sesión de marta | En menos de 5 minutos, la siguiente llamada del agente recibe 401 |

La consola (<http://localhost:8080>) es de solo lectura: muestra todo, pero no permite aprobar.

## Añadir personas o equipos

1. Editar [`platform/access/identity/organization.yaml`](../../../../platform/access/identity/organization.yaml).
2. `python3 platform/access/identity/sync-organization.py` regenera el realm de Keycloak y el catálogo del portal (`python3 deploy/check-repository.py` falla si no coinciden).
3. `make up` vuelve a importar el realm y reconstruye el portal.

En un cliente, Keycloak se federa con su proveedor de identidad (Entra ID, Okta...) y transforma sus grupos corporativos en estos equipos; este fichero solo es la organización de ejemplo de la demo.
