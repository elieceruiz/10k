import streamlit as st
from datetime import datetime, timedelta
import base64
import openai
from pymongo import MongoClient
import pytz
import time

# === CONFIGURACIÓN ===
st.set_page_config(page_title="🧠 orden-ador", layout="centered")

# Claves desde secrets
openai.api_key = st.secrets["openai_api_key"]
client = MongoClient(st.secrets["mongo_uri"])
db = client["ordenador"]
historial_col = db["historial"]
dev_col = db["dev_tracker"]

tz = pytz.timezone("America/Bogota")

# Estado base
for key, val in {
    "orden_detectados": [],
    "orden_asignados": [],
    "orden_en_ejecucion": None,
    "orden_timer_start": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# Función visión
def detectar_objetos_con_openai(imagen_bytes):
    base64_image = base64.b64encode(imagen_bytes).decode("utf-8")
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "¿Qué objetos ves en esta imagen? Solo da una lista simple."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ],
            }
        ],
        max_tokens=100
    )
    texto = response.choices[0].message.content
    objetos = [x.strip(" -•0123456789. ") for x in texto.split("\n") if x.strip()]
    return objetos

# === INTERFAZ ===
seccion = st.selectbox("¿Dónde estás trabajando?", ["⏱ Desarrollo", "📸 Ordenador", "📂 Historial"])

# === OPCIÓN 1: Desarrollo
if seccion == "⏱ Desarrollo":
    st.subheader("⏱ Tiempo dedicado al desarrollo de orden-ador")

    evento = dev_col.find_one({"tipo": "ordenador_dev", "en_curso": True})

    if evento:
        hora_inicio = evento["inicio"].astimezone(tz)
        segundos_transcurridos = int((datetime.now(tz) - hora_inicio).total_seconds())
        st.success(f"🧠 Desarrollo en curso desde las {hora_inicio.strftime('%H:%M:%S')}")
        cronometro = st.empty()
        stop_button = st.button("⏹️ Finalizar desarrollo")

        for i in range(segundos_transcurridos, segundos_transcurridos + 100000):
            if stop_button:
                dev_col.update_one(
                    {"_id": evento["_id"]},
                    {"$set": {"fin": datetime.now(tz), "en_curso": False}}
                )
                st.success("✅ Registro finalizado.")
                st.rerun()

            duracion = str(timedelta(seconds=i))
            cronometro.markdown(f"### ⏱️ Duración: {duracion}")
            time.sleep(1)

    else:
        if st.button("🟢 Iniciar desarrollo"):
            dev_col.insert_one({
                "tipo": "ordenador_dev",
                "inicio": datetime.now(tz),
                "en_curso": True
            })
            st.rerun()

# === OPCIÓN 2: Ordenador (visión + ejecución)
elif seccion == "📸 Ordenador":
    st.subheader("📸 Ordenador con visión GPT-4o")

    imagen = st.file_uploader("Subí una imagen", type=["jpg", "jpeg", "png"])

    if imagen and not st.session_state.orden_detectados:
        with st.spinner("Detectando objetos..."):
            detectados = detectar_objetos_con_openai(imagen.read())
            st.session_state.orden_detectados = detectados
            st.success("Detectados: " + ", ".join(detectados))

    opciones_restantes = [o for o in st.session_state.orden_detectados if o not in st.session_state.orden_asignados]

    if opciones_restantes and not st.session_state.orden_en_ejecucion:
        seleccion = st.selectbox("Seleccioná el siguiente en el orden:", opciones_restantes)
        if st.button("Asignar al orden"):
            st.session_state.orden_asignados.append(seleccion)
            st.success(f"'{seleccion}' agregado como paso #{len(st.session_state.orden_asignados)}")

    if st.session_state.orden_asignados and not st.session_state.orden_en_ejecucion:
        if st.button("Iniciar ejecución"):
            st.session_state.orden_en_ejecucion = st.session_state.orden_asignados.pop(0)
            st.session_state.orden_timer_start = datetime.now(tz)

    if st.session_state.orden_en_ejecucion:
        st.info(f"🟢 Ejecutando: **{st.session_state.orden_en_ejecucion}**")
        tiempo = datetime.now(tz) - st.session_state.orden_timer_start
        st.write(f"⏱ Tiempo transcurrido: {str(tiempo).split('.')[0]}")
        if st.button("Finalizar este ítem"):
            registro = {
                "ítem": st.session_state.orden_en_ejecucion,
                "duración": str(tiempo).split(".")[0],
                "timestamp": datetime.now(tz),
            }
            historial_col.insert_one(registro)
            st.session_state.orden_en_ejecucion = None
            st.session_state.orden_timer_start = None

# === OPCIÓN 3: Historial
elif seccion == "📂 Historial":
    st.subheader("📂 Historial de ejecución")

    # --- BLOQUE 1: Ejecuciones desde visión ---
    st.markdown("### 🧩 Objetos ejecutados con visión")

    registros = list(historial_col.find().sort("timestamp", -1))

    if registros:
        data_vision = []
        for i, reg in enumerate(registros, 1):
            fecha = reg["timestamp"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
            data_vision.append({
                "#": i,
                "Ítem": reg["ítem"],
                "Duración": reg["duración"],
                "Fecha": fecha
            })
        st.dataframe(data_vision, use_container_width=True)
    else:
        st.info("No hay ejecuciones registradas desde la visión.")

    # --- BLOQUE 2: Sesiones de desarrollo ---
    st.markdown("### ⌛ Tiempo dedicado al desarrollo")

    sesiones = list(dev_col.find({"en_curso": False}).sort("inicio", -1))
    total_segundos = 0
    data_dev = []

    for i, sesion in enumerate(sesiones, 1):
        ini = sesion["inicio"].astimezone(tz)
        fin = sesion.get("fin", ini).astimezone(tz)
        segundos = int((fin - ini).total_seconds())
        total_segundos += segundos

        duracion = str(timedelta(seconds=segundos))
        data_dev.append({
            "#": i,
            "Inicio": ini.strftime("%Y-%m-%d %H:%M:%S"),
            "Fin": fin.strftime("%Y-%m-%d %H:%M:%S"),
            "Duración": duracion
        })

    if data_dev:
        st.dataframe(data_dev, use_container_width=True)
        st.markdown(f"**🧠 Total acumulado:** `{str(timedelta(seconds=total_segundos))}`")
    else:
        st.info("No hay sesiones de desarrollo finalizadas.")