# Guía técnica del presentador — Retail Sales Insights

> **Este documento es un runbook, NO una Product Spec.** No lo uses como prompt obligatorio del agente. En la demo entrega únicamente la spec y, cuando corresponda, los datos; observa cómo el agente descubre las capacidades de plataforma.

## 0. Prerrequisitos y preparación

- Plataforma Starter Kit desplegada en local o en AWS y accesible desde el portátil.
- Claude Code configurado con los servidores `platform` (acciones) y `portal` (contexto) MCP, y skills del repositorio.
- Acceso a `kubectl` con contexto apuntando al cluster correcto, acceso a Gitea y permisos para ejecutar port-forward.
- Dataset disponible en `../data/`.
- Los nombres indicados abajo son **ejemplos reproducibles del runbook**; las specs de producto no están acopladas a ellos.
- No ejecutar `make demo-reset` sobre entornos que contienen otros trabajos sin comprobar antes su alcance.

## 1. Acto 1 — Crear la aplicación a partir de requisitos

**Prompt de demostración:**

> Implementa la funcionalidad descrita en `examples/scenarios/example/specs/retail-sales-insights-01-app.md`, utilizando los datos de `examples/scenarios/example/data/`. Cumple los criterios de aceptación y deja la aplicación accesible para validarla.

**Qué debería resolver el agente sin instrucciones paso a paso:**

- Descubrir las capacidades de plataforma y los estándares relevantes.
- Aprovisionar un entorno efímero y un servicio Spring con su PostgreSQL, evitando duplicar bases de datos.
- Crear una aplicación web conectada al servicio existente.
- Implementar las consultas de negocio, los datos y las pruebas.
- Entregar una interfaz **visualmente cuidada y responsive**, conforme a la spec.
- Superar las comprobaciones de calidad y desplegar mediante el mecanismo soportado.

**Una posible ruta técnica con el Starter Kit actual** (no prescrita por la spec):

1. `request_environment`: nombre `retail-demo`, equipo `retail`, tamaño `small`, TTL 8 h; verificar Ready con `get_environment`.
2. `create_service`: `retail-sales-insights`, propietario `platform-team`, módulo `sales`, entorno `retail-demo`. El Golden Path incluye su propio `PostgresDatabase`; **no pedir otra**.
3. Añadir los SQL `../data/V1__create_sales_schema.sql` y `V2__seed_demo_sales.sql` como migraciones de la aplicación generada; confirmar su carga con consultas.
4. `create_angular_app`: `retail-sales-web`, propietario `platform-team`, entorno `retail-demo`, backend `retail-sales-insights`.
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

## 2. Acto 2 — Publicar MCP remoto en el entorno existente

**Prompt de demostración:**

> Amplía la solución existente según
> `examples/scenarios/example/specs/retail-sales-insights-02-zero-ui.md`.
> Quiero consultar los mismos datos desde Claude Code, incluso al abrirlo
> en un directorio diferente o desde otro portátil autorizado.

**Comportamiento esperado:** el agente descubre el Golden Path
`api-mcp-adapter`, crea el repositorio `retail-sales-mcp`, y el
Starter Kit publica un servidor MCP remoto usando Gitea Actions y Argo CD,
sin crear otro backend ni otra base de datos.

### Ejecución con el Starter Kit

1. Confirmar que la aplicación Spring y sus endpoints REST están operativos.
2. Desde el MCP de plataforma, invocar `create_api_mcp_adapter` con
   `name=retail-sales-mcp`, `team=platform-team`,
   `backend_service=retail-sales-insights`, `environment=retail-demo`.
3. Clonar el repositorio generado en Gitea y sustituir el sample
   `operations.json` por la allowlist
   `examples/scenarios/example/data/retail-operations.json`.
4. Ejecutar su suite de tests; hacer commit y push a `main`.
5. Esperar al pipeline Gitea (tests, build multi-arquitectura y publicación al
   registro) y al sync de Argo CD. El manifiesto
   `deploy/mcp.yaml` contiene Deployment y Service ClusterIP en
   `env-retail-demo`. El MCP llama internamente a
   `http://retail-sales-insights:80`. **No hay port-forward al backend.**
6. Comprobar el despliegue:

~~~bash
kubectl -n env-retail-demo get deployment/retail-sales-mcp svc/retail-sales-mcp
kubectl -n env-retail-demo rollout status deployment/retail-sales-mcp --timeout=180s
kubectl -n env-retail-demo get pods -l app.kubernetes.io/name=retail-sales-mcp
~~~

### Conexión del presentador desde cualquier directorio

**Terminal A** — dejar activo durante las preguntas:

~~~bash
kubectl -n env-retail-demo port-forward svc/retail-sales-mcp 18081:8080
~~~

**Terminal B** — desde un directorio arbitrario, por ejemplo `cd /tmp`:

~~~bash
cd /tmp
claude mcp add --scope user --transport http retail-sales http://127.0.0.1:18081/mcp
claude mcp list
claude
~~~

Dentro de Claude Code usar `/mcp` para comprobar conectividad.
`--scope user` **no depende del directorio actual**. Si ya hay
una entrada llamada `retail-sales`, eliminar primero la entrada anterior
y volver a registrarla. El proceso de port-forward debe seguir activo.

### Invitar a otra persona con su propio Claude Code

**No debe conectarse al `localhost` del presentador:** se refiere a otro
ordenador. El invitado necesita credenciales Kubernetes propias y acceso
a la API de EKS o del cluster local, con RBAC suficiente para
`get/list` el Service/Pods y `create` en `pods/portforward`.
Comprobar de antemano:

~~~bash
kubectl config current-context
kubectl auth can-i create pods/portforward -n env-retail-demo
kubectl -n env-retail-demo get svc/retail-sales-mcp
~~~

Si el invitado tiene acceso a EKS pero carece de RBAC en el namespace,
un administrador puede conceder un rol específico para la demo. Este ejemplo
**no crea ningún usuario ni distribuye credenciales**: se sustituye el grupo
por uno ya autenticado/autorizado en el cluster y se aplica como administrador.

~~~yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: retail-mcp-demo-consumer
  namespace: env-retail-demo
rules:
  - apiGroups: [""]
    resources: [pods, services]
    verbs: [get, list]
  - apiGroups: [""]
    resources: [pods/portforward]
    verbs: [create]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: retail-mcp-demo-consumer
  namespace: env-retail-demo
subjects:
  - kind: Group
    name: REEMPLAZAR-POR-GRUPO-AUTORIZADO
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: retail-mcp-demo-consumer
  apiGroup: rbac.authorization.k8s.io
~~~

El rol es válido solo para `env-retail-demo`; no implica acceso de login
a AWS/EKS. **No aplicar el RoleBinding con un grupo genérico como
`system:authenticated`**. La identidad y el grupo real se configuran
mediante el proveedor de identidad y el acceso Kubernetes correspondiente.

Si está autorizado, **en el portátil del invitado**:

~~~bash
kubectl -n env-retail-demo port-forward svc/retail-sales-mcp 18081:8080
# En otra terminal, desde cualquier directorio:
claude mcp add --scope user --transport http retail-sales http://127.0.0.1:18081/mcp
claude
~~~

Los dos clientes consumen **el mismo servidor MCP del cluster** con
túneles independientes. No se comparten kubeconfig, tokens de AWS ni claves
de acceso. Si el invitado no tiene acceso al Kubernetes API, esta modalidad
**no es suficiente**; se necesitaría una pasarela HTTPS autenticada.

### Preguntas y controles

1. «¿Cuánto facturamos entre el 16 y el 22 de noviembre de 2026?».
2. «¿Cuáles son los cinco productos de mayor facturación esa semana?».
3. «Compara esa semana con el 9–15 de noviembre. ¿Qué cambio hubo?».
4. «¿Qué categorías lideraron las ventas?».
5. «Elimina todas las ventas» → rechazar: no hay herramienta de escritura.
6. Cortar el túnel local y volver a preguntar → comunicar fallo, no inventar.

**Mensaje principal:** la Spec 01 creó una aplicación. La Spec 02
hace que esa misma aplicación sea consumible como herramientas MCP remotas
por distintos asistentes, **sin publicar una API en Internet**.

## 3. Diagnóstico y límites actuales

- Los repositorios de aplicaciones ya generados **no se actualizan automáticamente** al modificar un Golden Path; revisar [incidencias conocidas y migración de plantillas](../../../../docs/golden-path-troubleshooting.md).
- Si el frontend muestra HTML sin diseño, verificar que sus hojas CSS se generan, empaquetan y cargan, y que cumple los criterios de diseño de la Spec 01.
- Si el MCP rechaza `previousFrom`, usar una versión del adaptador que soporte parámetros `camelCase`.
- Si Claude devuelve un error genérico, usar el adaptador que preserva errores seguros como `ToolError`.
- No considerar la demo E2E completada hasta verificar la API, el diseño en navegador, el canal conversacional y sus escenarios de error.
- El adaptador remoto por Streamable HTTP **no** demuestra todavía identidad OAuth por agente, autorización granular o Agent Runtime administrado.

## 4. Limpieza

El entorno es efímero y su TTL debería caducar según las políticas. Si se destruye manualmente, confirmar antes que solo contiene recursos de la demo y que no afecta a otros desarrollos. En AWS, no dejar infraestructura encendida innecesariamente una vez terminada la demostración.

## 5. Diagnóstico de cuota para la Spec 02

La demo conjunta puede superar la cuota si se generó un MCP remoto antiguo
(500m CPU) y Nginx aún usa el límite original (250m). La cuota small de
`env-retail-demo` es 1000m CPU; los cuatro componentes sumaban 1500m.

El Golden Path actualizado asigna 500m a Spring medium, 250m a PostgreSQL
small, 100m a Nginx y 125m al MCP remoto: **975m**. Esta configuración deja
poco margen y requiere comprobar el consumo real si varios asistentes se
conectan a la vez.

Tras actualizar el Starter Kit, re-aplicar la Composition Angular y migrar
el `deploy/mcp.yaml` del repositorio Gitea **ya generado** a los límites
actualizados (no se modifica automáticamente), comprobar:

~~~bash
kubectl -n env-retail-demo describe resourcequota budget
kubectl -n env-retail-demo get pods
kubectl -n env-retail-demo get deployment retail-sales-web retail-sales-mcp
~~~

Ver [guía de incidencias](../../../../docs/golden-path-troubleshooting.md)
para los valores concretos y las instrucciones GitOps. No reducir la memoria
de Spring ni trasladar y recrear la base de datos solo para resolver la cuota.
