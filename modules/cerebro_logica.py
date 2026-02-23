import json
import re

def generar_prompt_paso1_filtro(relato):
    return f"""
    ERES UN INVESTIGADOR EXPERTO DE LA SUSESO CHILE (Manual OIT/SUSESO).
    OBJETIVO: Aplicar el Filtro de la Verdad (Pág. 37-39) al siguiente relato.
    RELATO: "{relato}"

    REGLA DE ORO (ATOMIZACIÓN DE HECHOS): 
    Un hecho no puede contener dos variables. Divide la información en unidades MÍNIMAS indivisibles. 

    Desfragmenta el texto en:
    1. HECHOS: Datos concretos, reales y comprobables atómicos. (span HTML verde #2ecc71, font-weight:bold).
    2. INTERPRETACIONES: Suposiciones físicas a verificar. (span HTML amarillo #f1c40f, font-weight:bold).
    3. JUICIOS DE VALOR: Subjetividades, estados mentales no demostrables o culpas. (span HTML rojo #e74c3c, font-weight:bold).

    RESPONDE SOLO EN JSON:
    {{
      "relato_marcado": "Texto original con los spans incrustados",
      "hechos": ["Hecho atómico 1", "Hecho atómico 2..."],
      "interpretaciones": ["Interpretación 1"],
      "juicios": ["Juicio 1", "Juicio 2"]
    }}
    """

def generar_prompt_paso2_arbol(hechos_limpios):
    return f"""
    ERES UN INVESTIGADOR EXPERTO DE LA SUSESO CHILE.
    REGLA CERO ABSOLUTA: TIENES PROHIBIDO USAR INFORMACIÓN DE INTERNET. TU ÚNICA VERDAD ES EL MANUAL OIT/SUSESO.

    OBJETIVO: Construir Árbol de Causas (Pág. 40-42) UTILIZANDO EXCLUSIVAMENTE esta lista de hechos atómicos:
    {hechos_limpios}

    INSTRUCCIONES METODOLÓGICAS Y FILTRADO ESTRICTO (Regla del "NO" - Pág. 43):
    1. CONSTRUCCIÓN: Empieza por el último hecho (la lesión final) y remonta hacia atrás cronológicamente.
    2. LA PRUEBA DE FUEGO: Para cada hecho de la lista pregúntate: "Si esto NO hubiera ocurrido, ¿el accidente habría pasado igual?".
       - Si la respuesta es SÍ -> ELIMÍNALO DEL ÁRBOL POR COMPLETO.
       - Si la respuesta es NO -> INCLÚYELO en el árbol.
    3. CONTEXTO VS ANOMALÍA: Las tareas rutinarias habituales NO son causas raíces. Busca la variación o el estado anormal.
    4. LÓGICA DE RAMAS: Aplica relaciones "En Cadena" (1 a 1), "En Conjunción" (2 o más hechos) y "Disyunción".

    INSTRUCCIONES GRÁFICAS ESTRICTAS (Graphviz DOT - Estética Manual OIT):
    Debes generar un código DOT válido que siga EXACTAMENTE esta estética visual:

    1. CONFIGURACIÓN GLOBAL:
       - Dirección: De abajo hacia arriba (rankdir=BT).
       - Fuente: Arial, tamaño 10 para todo.

    2. ESTILOS DE NODOS (La estética es CRUCIAL):
       - LESIÓN FINAL (El hecho más alto): Debe ser DOBLE CÍRCULO rojo intenso.
         (Estilo: node [shape=doublecircle, style=filled, color="#c0392b", fillcolor="#faddd8", fontcolor="#922b21"];)
       - CAUSAS RAÍZ (Los hechos en el extremo inferior): Deben ser CÍRCULOS rojos.
         (Estilo: node [shape=circle, style=filled, color="#c0392b", fillcolor="#faddd8", fontcolor="#922b21"];)
       - HECHOS INTERMEDIOS (Conectores): Deben ser CÍRCULOS azules claros.
         (Estilo por defecto: node [shape=circle, style=filled, color="#3498db", fillcolor="#ebf5fb", fontcolor="#154360"];)

    3. CONSTRUCCIÓN DEL DOT (Sigue este orden para evitar errores):
       a. Define el digraph G {{ rankdir=BT; node [fontname="Arial", fontsize=10]; }}
       b. Define PRIMERO los estilos rojos e inserta los nodos de Lesión y Causas Raíz.
       c. Define LUEGO el estilo azul por defecto e inserta el resto de hechos intermedios.
       d. Define FINALMENTE las relaciones (aristas) usando -> asegurando que la flecha vaya de la CAUSA al EFECTO (ej: "Rampa podrida" -> "Rampa cedió").

    DEFINICIÓN DE CAUSA RAÍZ (Pág. 44):
    Debe ser ÚNICAMENTE el texto exacto de la condición subestándar técnica o la falla de gestión que quedó en los extremos superiores del gráfico (las fallas base o primeras en orden cronológico).

    RESPONDE SOLO EN JSON:
    {{
      "dot_code": "digraph G {{ rankdir=BT; node [fontname='Arial', fontsize=10]; ... }}",
      "causa_raiz": "Descripción única y exacta de la anomalía o falla de gestión principal, extraída directamente de los extremos del árbol."
    }}
    """

# --- MEMORIA INTERNA SUSESO (ANEXO I COMPLETO) ---
MEMORIA_ANEXO_I = """
MATRIZ DE FACTORES DE CAUSAS DE ACCIDENTES DEL TRABAJO (SUSESO)

1. GESTIÓN PREVENTIVA DE LA EMPRESA
1101: Inexistencia de un programa de prevención de riesgos laborales.
1102: No se han identificado los peligros y los riesgos no están evaluados.
1103: Deficiencias en la organización preventiva de la empresa.
1104: Inexistencia procedimientos de evaluación y auditoría en el sistema de gestión.
1105: Falta de coordinación entre empresas sobre procedimientos de trabajo seguro (PTS).
1106: Inexistencia o deficiencia en la coordinación entre trabajadores.
1107: Inexistencia o deficiencias de Procedimiento de Trabajo Seguro (PTS).
1108: Sistema inexistente, inadecuado o mal aplicado de asignación de tareas.
1109: Los trabajadores no participan en la gestión preventiva.
1110: No considerar las características de los trabajadores para la realización de la tarea.
1111: Política de compras inexistente o inadecuada desde el punto de vista de prevención.
1112: No existe plan de emergencia o el plan es inadecuado.
1113: Inexistencia de procedimiento de investigación de incidentes.
1201: Falta de control del cumplimiento del Plan de seguridad.
1202: No existe programa de mantenimiento preventivo.
1202a: Mantenimiento preventivo inexistente o inadecuado de máquinas y herramientas.
1202b: Mantenimiento preventivo inexistente o inadecuado de vías interiores.
1203: No identificación de peligros y evaluación de riesgos de la tarea.
1204: Falta o deficiencias en los controles de salud.
1205: Ausencia/deficiencias de permisos de trabajo en intervenciones peligrosas.
1206: Deficiente gestión en la selección y control de EPP.
1206a: Falta de EPP.
1206b: EPP no adecuados al riesgo.
1206c: EPP en malas condiciones.
1206d: No hay supervisión para el uso de EPP.
1207: Ausencia o falla en procedimientos de control y supervisión.

2. FACTORES DE LA ORGANIZACIÓN DEL TRABAJO
2101: Exceder la jornada máxima legal diaria y/o semanal.
2102: Exceder el máximo de horas de conducción continuas.
2103: Descanso inferior al legal.
2104: Ausencia de pausas programadas.
2201: Ritmo de trabajo elevado.
2202: Trabajo monótono o rutinario.
2203: Trabajo solitario sin medidas de asistencia.
2204: Sobrecarga mental en supervisión.
2205: Organizar el trabajo sin tomar en cuenta condiciones meteorológicas.
2212: Ritmo de trabajo impuesto.
2213: Elevado nivel de atención.
2214: Falta de autonomía en la toma de decisiones.
2301: Trabajador no cuenta con capacitación o no ha sido informado de riesgos.
2301a: Conductor sin capacitación.
2302: Operador de máquinas sin la capacitación suficiente.
2303: Inexistencia o deficiencias en información sobre cómo actuar en condiciones críticas.
2304: Trabajador no capacitado en uso de EPP.
2401: Abuso o maltrato (2401a jefaturas, 2401b compañeros).
2402: Excesiva verticalidad del mando.
2403: Falta de participación en toma de decisiones.
2404: Comunicaciones inexistentes o insuficientes desde los mandos.

3. FACTORES INDIVIDUALES
3101: Fatiga del trabajador.
3102: Enfermedad.
3103: Trastornos del sueño.
3104: Consumo de fármacos.
3105: Sensibilidad o alergias a sustancias.
3106: Deficiencia o limitación de los sentidos.
3107: Incapacidad para realizar la tarea (3107a física, 3107b mental).
3201: Consumo de alcohol (3201a conducción, 3201d trabajar bajo influencia).
3202: Consumo drogas ilícitas.

4. FACTORES ASOCIADOS AL MEDIO
4101: Camino en mal estado.
4102: Diseño de la vía o camino inadecuado.
4103: Iluminación deficiente de la vía.
4104: Inexistencia de barreras de contención.
4110: Vías de circulación de personas estrechas o poco iluminadas.
4111: Obstrucción de vías de circulación de personas.
4112: Vías de circulación de personas con baches o peligro de colapso.
4113: Falta de protección colectiva contra caídas en vías.
4114: Vías con desniveles peligrosos.
4115: Estructuras del lugar de trabajo mal construidas.
4116: Estructuras mal mantenidas con probabilidad de colapso.
4201: Camino resbaladizo por condiciones climáticas (4201a lluvia, 4201b nieve, 4201c hielo).
4202: Baja visibilidad climática.
4301 a 4308: Señalización vial inexistente o deficiente.
4309: Señales de peligro inexistentes o no visibles en lugar de trabajo.
4310: Señalización inexistente en zonas delimitadas.
4311: Vías de evacuación no señalizada.
4312: Señales inexistentes sobre uso obligatorio de EPP.
4401: Exposición a hiperbaría / 4402: hipobaría.
4403: Deslumbramiento natural.
4404: Exposición a frío o calor del medio ambiente.
4501: Exposición a calor extremo por fuentes antropogénicas.
4502: Ruido excesivo.
4503: Superficies de trabajo inestables, frágiles o resbaladizas.
4504: Ausencia o deficiencia de protecciones colectivas frente a caída de personas.
4505: Inexistencia de barreras ante excavaciones o huecos.
4508: Inexistencia u obstrucción de vías de evacuación.
4509: Ineficacia de aislamiento en espacios peligrosos.
4511: No delimitación de zonas de trabajo peligrosas.
4512: Pisos resbaladizos por derrames.
4514: Deficiencia en orden y limpieza.
4515: Sistema de ventilación deficiente.
4517: Deficiencia en iluminación en el puesto.
4519: Equipos de izaje inadecuados.
4520: Apilamiento de carga inseguro.
4521: Exceso de carga en el sistema de izaje o transporte.
4522: Manejo manual de carga en condiciones inseguras.
4523: Vehículo con sobrecarga o mal estibado.
4524: Sistemas eléctricos no protegidos.
4529: Sistemas de detección y extinción de incendios insuficientes.
4530: Almacenamiento de sustancias peligrosas no reglamentario.
4604: Manipulación o presencia de sustancias químicas peligrosas.

5. FACTORES TECNOLÓGICOS
5101: Vehículo inadecuado para el transporte.
5107: Ausencia o deficiencia de alarmas de retroceso.
5201: Sistema de frenado inseguro.
5301: Ausencia de cinturón de seguridad.
5404: Fallas mecánicas del sistema de frenos.
5406: Fallas de neumáticos.
5501: Diseño riesgoso de máquinas o uso no concebido.
5502: Modificaciones en la máquina que generan riesgo.
5504: Máquinas sin enclavamiento o estibación segura.
5505: Falta o falla de elementos de protección y aislación de máquinas.
5507: Fallas en sistema eléctrico, neumático o hidráulico.
5512: Partes estructurales de máquinas o herramientas en mal estado.
5513: Ausencia de sistemas de bloqueo automático.

6. FACTORES EXTERNOS / 7. OTROS
6101: Desastres naturales (terremotos, aluviones).
6102: Desastres tecnológicos (explosiones, incendios mayores).
6103: Acciones delictuales o sabotaje.
6104: Accidentes por terceros no relacionados con la empresa.
7999: Otros factores no considerados.
"""

def generar_prompt_paso3_medidas(causa_raiz):
    return f"""
    ERES UN INVESTIGADOR EXPERTO DE LA SUSESO CHILE (Manual OIT/SUSESO).
    REGLA CERO: TIENES PROHIBIDO INVENTAR INFORMACIÓN O CÓDIGOS. TU ÚNICA FUENTE DE CÓDIGOS ES LA SIGUIENTE MEMORIA INTERNA OFICIAL:

    [INICIO MEMORIA ANEXO I]
    {MEMORIA_ANEXO_I}
    [FIN MEMORIA ANEXO I]

    OBJETIVO: Diseñar plan de acción (Pág. 43-47) SOLO para esta causa raíz:
    "{causa_raiz}"

    1. CÓDIGO SUSESO: Busca en la MEMORIA ANEXO I el código que mejor describa la causa raíz. DEBES usar EXACTAMENTE el número de 4 dígitos y la glosa de esa lista. Si no hay uno exacto, usa el más cercano o 7999. ¡PROHIBIDO INVENTAR NÚMEROS!
    2. MEDIDA CORRECTORA (Pág. 44): Acción técnica inmediata y directa sobre el lugar del accidente para eliminar la causa hoy.
    3. FPA Y MEDIDA PREVENTIVA (Pág. 45-46): Transforma la causa raíz en un Factor Potencial de Accidente (FPA). Mantén la medida acotada y realista, sin generalización excesiva.

    RESPONDE SOLO EN JSON:
    {{
      "codigo_suseso": "Código 4 dígitos - Glosa exacta oficial de la memoria",
      "medida_correctora": "Acción técnica inmediata",
      "fpa_y_preventiva": "FPA acotado + Medida preventiva sistémica realista"
    }}
    """

def limpiar_respuesta_ia(texto_raw):
    try:
        txt = re.sub(r'```json\s*|```', '', texto_raw).strip()
        txt = txt.replace('\n', ' ').replace('\r', '')
        return json.loads(txt, strict=False)
    except:
        return {}