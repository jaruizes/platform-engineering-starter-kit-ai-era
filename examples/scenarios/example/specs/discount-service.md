# Spec: servicio de cálculo de descuento

## Qué necesitamos

Queremos premiar la fidelidad de los clientes y ofrecerles un descuento en el momento de la compra.
Se necesita un servicio que reciba el id del cliente y devuelva el porcentaje de descuento a aplicar.

## Datos del servicio
- **Nombre**: discount-service
- **Versión**: 0.0.1
- **Arquitectura**: Backend v2
- **Despliegue**: Kubernetes
- **Paquete base**: `com.starterkit.discountservice` (el que genera la plantilla Spring del Golden Path)
- **Módulo principal**: discounts

## API Rest

### Obtener descuento
Obtiene el descuento del cliente dependiendo de su fidelidad.
Endpoint:
- `GET /discounts/{customerId}`
Salida:
- Json con el porcentaje de descuento. Ejemplo: ```{ "discount": 10 }```


## Requisitos y reglas de negocio

### Requisitos funcionales
- El cliente debe existir y estar registrado.
- El descuento debe ser un porcentaje entre 0 y 15.

### Requisitos no funcionales
- Debe cumplir las reglas de arquitectura y estándares corporativos.

### Reglas de negocio
1. El cliente debe existir y estar registrado.
2. Para el cáculo del descuento, en debe obtener el importe total de los pedidos realizados en año en curso. Se utilizará el servicio de pedidos ("/orders?customerId={customerId}&year={year}")
3. Si el importe total es mayor que 0€ pero menor de 100€, se devuelve un 5%. Si está entre 100€ y 500€ (ambos incluidos), se devuelve un 10%. Si es mayor de 500€, se devuelve un 15%.

## Criterios de aceptación
- Si se recibe un cliente que no existe, se devuelve 0% (sin responder 404)
- Dado un cliente sin compras en el año en curso, se devuelve 0%
- Dado un cliente con compras en el año en curso, cuyo importe total es menor de 100€, se devuelve un 5%
- Dado un cliente con compras en el año en curso, cuyo importe total es 100€, se devuelve un 10%
- Dado un cliente con compras en el año en curso, cuyo importe total está entre 100€ y 500€, se devuelve un 10%
- Dado un cliente con compras en el año en curso, cuyo importe total es 500€, se devuelve un 10%
- Dado un cliente con compras en el año en curso, cuyo importe total es mayor de 500€, se devuelve un 15%

## Consideraciones adicionales
Esta primera versión simula la llamada al servicio de pedidos
("/orders?customerId={customerId}&year={year}") con datos fijos en un adaptador
en memoria. No hace falta añadir una base de datos propia ni otra tecnología.
La respuesta de `GET /discounts/{customerId}` es JSON con un campo numérico
`discount`; por ejemplo `{ "discount": 10 }`. El adaptador usa estos clientes:
- Cliente "C001": no tiene compras en el año en curso.
- Cliente "C002": tiene un total de 80€ en año en curso.
- Cliente "C003": tiene un total de 100€ en año en curso.
- Cliente "C004": tiene un total de 500€ en año en curso.
- Cliente "C005": tiene un total de 600€ en año en curso.

La prueba end-to-end consulta el endpoint para C001..C005 y un cliente
desconocido (C999), y espera los descuentos 0, 5, 10, 10, 15 y 0,
respectivamente.

## Equipo responsable del servicio
El equipo responsable del servicio es **checkout**.

