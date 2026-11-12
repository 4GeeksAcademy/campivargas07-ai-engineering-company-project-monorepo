# Brasaland — guion del pitch de cinco minutos

Formato horizontal, 1080p si es posible. Carlos presenta a cámara y narra la pantalla con su propia voz. Ensayar dos veces y medir los bloques con el recorrido abierto.

| Tiempo | Toma |
|---|---|
| 0:00–0:30 | Presentación a cámara. Mostrar el nombre después de la frase inicial. |
| 0:30–1:30 | Problema del encargado. Corte breve a Resumen. |
| 1:30–3:30 | Captura del backoffice. Resumen → Chat → consulta → interrupción → respuesta corregida. |
| 3:30–4:15 | Decisión de ingeniería. Corte al estado «interrumpido» y al nuevo turno. |
| 4:15–5:00 | Q&A a cámara. Dos segundos completos de pausa antes y después de cada respuesta. |

## Texto para ensayar

### Gancho y presentación

Un encargado de restaurante necesita consultar el manual justo cuando menos tiempo tiene para buscarlo. Soy Carlos Vargas y este es Brasaland, un backoffice de operaciones con un asistente que consulta los manuales de la empresa. Voy a mostrar cómo un encargado puede hacer una pregunta y corregirla mientras el asistente todavía está respondiendo.

### Problema y oportunidad

Imagina que estás atendiendo un turno y te preguntan por un plato. Tienes que encontrar la advertencia exacta y saber de qué manual salió. Si la pregunta cambia mientras consultas, también necesitas poder corregir el rumbo. Elegí este caso porque junta dos necesidades del encargado: encontrar una respuesta respaldada y mantener el control de la conversación.

### Solución y demo

Entro al backoffice con una cuenta de prueba. Desde Resumen abro Chat. Voy a preguntar qué indica el manual sobre los alérgenos de la Costilla BBQ y pedirle la fuente.

El asistente busca fragmentos relevantes en los manuales y los usa para responder. Eso es RAG. LangGraph coordina los pasos y el chat va mostrando el texto a medida que se genera.

Mientras responde, le pido que se centre en la advertencia sobre contaminación cruzada. Aquí queda visible la respuesta interrumpida. Debajo aparece la nueva respuesta, ajustada a lo que pedí.

### Decisión de ingeniería

El reto fue hacer que el botón Detener cancelara la generación y dejara la conversación en un estado coherente. Elegí WebSocket en vez de reutilizar SSE porque el navegador necesita enviar la corrección mientras recibe texto. Lo que más me gusta de esta decisión es lo que queda visible: la respuesta parcial sigue en el hilo y la corrección abre un turno nuevo.

### Q&A

1. **¿Qué te hizo decidirte a estudiar Ingeniería de IA — y qué estuvo a punto de detenerte?** «Decidí estudiar Ingeniería de IA porque [motivación real]. Lo que estuvo a punto de detenerme fue [obstáculo concreto]».
2. **¿Hubo un momento, un proyecto o una persona durante el programa en el que todo encajó de verdad?** «Para mí, todo encajó cuando [momento real]. Ahí entendí [qué cambió para mí]».
3. **¿Qué le dirías a alguien que está indeciso sobre unirse a 4Geeks?** «A alguien que está indeciso sobre unirse a 4Geeks le diría [consejo basado en tu experiencia]».

Completa los corchetes con tu historia. Dedica unos diez segundos de voz por respuesta y mira al objetivo.

## Acciones de pantalla

1. Desde Resumen, haz clic en Chat e inicia sesión de chat en un local válido.
2. Envía «¿Qué indica el manual sobre los alérgenos de la Costilla BBQ? Explica las advertencias y cita la fuente».
3. Mientras aparece el texto, pega «Resume en dos frases la advertencia del manual sobre contaminación cruzada al preparar la Costilla BBQ y cita la sección» y pulsa **Detener**.
4. Mantén en pantalla el parcial interrumpido y la respuesta nueva con su fuente. Contrasta la respuesta con el [manual](../company-knowledge-base/brasaland-menu-allergens.es.md) antes de usar la toma.

Graba las tomas a cámara con luz frontal y el micrófono cerca. Quita notificaciones y datos personales de la captura. Edita con acercamientos legibles y subtítulos, conservando la pausa de cada respuesta. Graba la toma final desde `main` después de integrar y verificar el sistema con el proveedor real.

## Entrega

- `CarlosVargas-Brasaland.mp4`.
- [CarlosVargas-Brasaland-description.txt](CarlosVargas-Brasaland-description.txt).
- `CarlosVargas-media-release.pdf` firmado o el archivo de exclusión de difusión pública según la elección de Carlos y la rúbrica.

Subir los tres archivos a una carpeta con enlace permanente. Comprobar el acceso con los permisos del instructor y entregar la URL de la carpeta en el LMS. Añadir el enlace al README con la visibilidad elegida. [Rúbrica oficial](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-eng-capstone-project/README.es.md)
