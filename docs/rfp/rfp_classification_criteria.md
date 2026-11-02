# RFP classification criteria

Clasificación implementada en `data/process/rfp.py::classify_rfp`:
- Señales RFP: request for proposal, rfp, catering, concession, concesión, propuesta, servicio.
- Una consulta de franquicia sin alcance, presupuesto ni fecha límite se descarta.
- En caso contrario se requiere señal + (alcance o fecha límite o presupuesto o contacto).

Estados resultantes: `analisis_completo` o `descartado`.
