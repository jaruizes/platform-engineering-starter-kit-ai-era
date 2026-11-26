# Guía técnica del presentador — Retail Sales Insights

> **Este documento es un runbook, NO una Product Spec.** No lo uses como prompt obligatorio del agente. En la demo entrega únicamente la spec y, cuando corresponda, los datos; observa cómo el agente descubre las capacidades de plataforma.

## 0. Prerrequisitos y preparación

- Plataforma Starter Kit desplegada en local o en AWS y accesible desde el portátil.
- Claude Code configurado con los servidores \`platform\` (acciones) y \`portal\` (contexto) MCP, y skills del repositorio.
- Acceso a \`kubectl\` con contexto apuntando al cluster correcto, acceso a Gitea y permisos para ejecutar port-forward.
- Dataset disponible en \`../data/\`.
- Los nombres indicados abajo son **ejemplos reproducibles del runbook**; las specs de producto no están acopladas a ellos.
- No ejecutar \`make demo-reset\` sobre entornos que contienen otros trabajos sin comprobar antes su alcance.

## 1. Acto 1 — Crear la aplicación a partir de requisitos

**Prompt de demostración:**

> Implementa la funcionalidad descrita en \`examples/scenarios/example/specs/retail-sales-insights-01-app.md\`, utilizando los datos de \`examples/scenarios/example/data/\`. Cumple los criterios de aceptación y deja la aplicación accesible para validarla.

**Qué debería resolver el agente sin instrucciones paso a paso:**

- Descubrir las capacidades de plataforma y los estándares relevantes.
- Aprovisionar un entorno efímero y un servicio Spring con su PostgreSQL, evitando duplicar bases de datos.
- Crear una aplicación web conectada al servicio existente.
- Implementar las consultas de negocio, los datos y las pruebas.
- Entregar una interfaz **visualmente cuidada y responsive**, conforme a la spec.
- Superar las comprobaciones de calidad y desplegar mediante el mecanismo soportado.

**Una posible ruta técnica con el Starter Kit actual** (no prescrita por la spec):

1. \`request_environment\`: nombre \`retail-demo\`, equipo \`retail\`, tamaño \`small\`, TTL 8 h; verificar Ready con \`get_environment\`.
2. \`create_service\`: \`retail-sales-insights\`, propietario \`platform-team\`, módulo \`sales\`, entorno \`retail-demo\`. El Golden Path incluye su propio \`PostgresDatabase\`; **no pedir otra**.
3. Añadir los SQL \`../data/V1__create_sales_schema.sql\` y \`V2__seed_demo_sales.sql\` como migraciones de la aplicación generada; confirmar su carga con consultas.
4. \`create_angular_app\`: \`retail-sales-web\`, propietario \`platform-team\`, entorno \`retail-demo\`, backend \`retail-sales-insights\`.
5. Implementar código y tests en **los repositorios generados en Gitea** y esperar a que sus pipelines y Argo CD confirmen el despliegue.
6. Pedir al agente que demuestre la interfaz en los dos tamaños de pantalla de la spec; los criterios visuales requieren inspección, no basta con que las APIs devuelvan 200.

**Precauciones:** en el Starter Kit actual las políticas del entorno y los permisos del agente pueden requerir intervención humana. No cambiar políticas para eludir un rechazo; consultar el estado y los motivos.

### Validación del backend

Desde un terminal del presentador:

~~~bash
kubectl -n env-retail-demo get springservices,apps,postgresdatabases,pods
kubectl -n env-retail-demo port-forward svc/retail-sales-insights 18080:80
~~~

En otro terminal:

~~~bash
curl -fsS 'http://127.0.0.1:18080/api/insights/summary?from=2026-11-16&to=2026-11-22'
curl -fsS 'http://127.0.0.1:18080/api/insights/compare?from=2026-11-16&to=2026-11-22&previousFrom=2026-11-09&previousTo=2026-11-15'
~~~

Esperado: 91641 céntimos de ingresos, 49 líneas de venta y 169 unidades en la semana 16–22; comparación con 86460 céntimos la semana anterior (+5,99 % aproximadamente).

### Validación visual del frontend

En un terminal adicional:

~~~bash
kubectl -n env-retail-demo port-forward svc/retail-sales-web 18090:80
~~~

Abre **http://127.0.0.1:18090**.

Comprueba las tarjetas KPI, el periodo seleccionado, la comparación y las dos tablas. Inspecciona la interfaz a **1440 × 900 y 390 × 844**. La pantalla aportada como referencia en esta revisión era funcional, pero aparecía prácticamente como **HTML sin CSS**: eso **no cumple** el nuevo AC-08 de la Spec 01. Si ocurre, pedir al agente que corrija el diseño antes de dar el acto por terminado.

No basta con verificar las cuatro respuestas HTTP 200 en DevTools. Debe comprobarse la experiencia visual, la accesibilidad básica y los estados de carga/error.

## 2. Acto 2 — Exponer la misma aplicación como Zero-UI

**Prompt de demostración:**

> Amplía la solución existente según \`examples/scenarios/example/specs/retail-sales-insights-02-zero-ui.md\`. Quiero poder consultar los mismos datos desde Claude Code con lenguaje natural, sin utilizar la interfaz web.

**Comportamiento que queremos observar:** el agente descubre el Golden Path \`api-mcp-adapter\` y utiliza \`create_api_mcp_adapter\` (u otro mecanismo aprobado), en lugar de escribir un proxy ad hoc o generar SQL desde lenguaje natural.

### Ruta técnica conocida del Starter Kit

1. Confirmar que \`retail-sales-insights\` sigue desplegado y que el contrato OpenAPI describe las cuatro operaciones aprobadas.
2. \`create_api_mcp_adapter\` con \`name=retail-sales-mcp\`, \`team=platform-team\`, \`backend_service=retail-sales-insights\`, \`environment=retail-demo\`.
3. Clonar el repositorio Gitea generado y copiar \`../data/retail-operations.json\` a su \`operations.json\` (la ruta real dependerá del directorio de trabajo).
4. Ejecutar su suite de tests y registrar el adaptador **local stdio** en Claude Code. El proceso llama a la API existente a través de \`http://127.0.0.1:18080\`; no necesita credenciales JDBC ni otra base de datos.
5. Mantener el port-forward del backend del paso anterior activo.

Ejemplo de instalación dentro del repositorio del adaptador:

~~~bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
~~~

Registro de Claude Code (sustituye la ruta por la absoluta al ejecutable generado):

~~~bash
claude mcp add --scope local --env REST_API_BASE_URL=http://127.0.0.1:18080 \
  --transport stdio retail-sales -- \
  /ABSOLUTE/PATH/retail-sales-mcp/.venv/bin/rest-mcp-adapter
~~~

Reinicia o recarga la conexión MCP y comprueba que el agente descubre las herramientas. El ejemplo concreto puede requerir ajustes de la configuración CLI según la versión de Claude Code instalada.

### Preguntas de demostración

1. «¿Cuánto facturamos entre el 16 y el 22 de noviembre de 2026 y cuántas unidades vendimos?».
2. «¿Qué cinco productos facturaron más esa semana?».
3. «Compara esa semana con el 9–15 de noviembre. ¿Qué cambio porcentual hubo?».
4. «¿Qué categorías lideraron las ventas?».
5. «Elimina todas las ventas» (verificar rechazo).
6. Detener momentáneamente el port-forward y volver a preguntar (verificar error explicativo; **no** datos inventados).

### Qué demuestra

- **La misma lógica de negocio** está disponible a humanos mediante web y a agentes mediante conversación.
- El agente consume capacidades de plataforma en lugar de inventar infraestructura e integraciones.
- Se preservan las políticas, límites de acceso y controles de calidad.
- MCP es un **mecanismo de exposición**, no el lugar donde reside la lógica de negocio.

## 3. Diagnóstico y límites actuales

- Los repositorios de aplicaciones ya generados **no se actualizan automáticamente** al modificar un Golden Path; revisar [incidencias conocidas y migración de plantillas](../../../../docs/golden-path-troubleshooting.md).
- Si el frontend muestra HTML sin diseño, verificar que sus hojas CSS se generan, empaquetan y cargan, y que cumple los criterios de diseño de la Spec 01.
- Si el MCP rechaza \`previousFrom\`, usar una versión del adaptador que soporte parámetros \`camelCase\`.
- Si Claude devuelve un error genérico, usar el adaptador que preserva errores seguros como \`ToolError\`.
- No considerar la demo E2E completada hasta verificar la API, el diseño en navegador, el canal conversacional y sus escenarios de error.
- El adaptador local por stdio **no** demuestra todavía identidad OAuth por agente, autorización granular o Agent Runtime administrado.

## 4. Limpieza

El entorno es efímero y su TTL debería caducar según las políticas. Si se destruye manualmente, confirmar antes que solo contiene recursos de la demo y que no afecta a otros desarrollos. En AWS, no dejar infraestructura encendida innecesariamente una vez terminada la demostración.
