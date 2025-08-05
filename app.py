import streamlit as st
from datetime import datetime, timedelta
import base64
import openai
from pymongo import MongoClient
import pytz
import time

# === CONFIGURACIÓN ===
st.set_page_config(page_title="🧠 orden-ador", layout="centered")
openai.api_key = st.secrets["openai_api_key"]
client = MongoClient(st.secrets["mongo_uri"])
db = client["ordenador"]
historial_col = db["historial"]
dev_col = db["dev_tracker"]
tz = pytz.timezone("America/Bogota")

# === ESTADO BASE ===
for key, val in {
    "orden_detectados": [],
    "orden_seleccionados": [],
    "orden_confirmados": False,
    "orden_actual": None,
    "orden_timer_start": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# === DETECCIÓN DE OBJETOS ===
def detectar_objetos_con_openai(imagen_bytes):
    base64_image = base64.b64encode(imagen_bytes).decode("utf-8")
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe brevemente los objetos comunes que aparecen en esta imagen."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ],
                }
            ],
            max_tokens=100
        )
        texto = response.choices[0].message.content
        if "no puedo ayudarte" in texto.lower():
            raise ValueError("Contenido bloqueado")
        objetos = [x.strip(" -•0123456789. ") for x in texto.split("\n") if x.strip()]
        return objetos
    except Exception:
        st.error("⚠️ No se pudo procesar la imagen. Intenta con otra distinta.")
        st.session_state.orden_detectados = []
        st.stop()

# === SELECCIÓN DE SECCIÓN ===
seccion = st.selectbox("¿Dónde estás trabajando?", ["🐍 Desarrollo", "📸 Ordenador", "📂 Historial"])

# === MÓDULO: DESARROLLO ===
if seccion == "🐍 Desarrollo":
    st.subheader("🐍 Tiempo dedicado al desarrollo de orden-ador")
    evento = dev_col.find_one({"tipo": "ordenador_dev", "en_curso": True})

    if evento:
        hora_inicio = evento["inicio"].astimezone(tz)
        segundos_transcurridos = int((datetime.now(tz) - hora_inicio).total_seconds())
        st.success(f"🧠 Desarrollo en curso desde las {hora_inicio.strftime('%H:%M:%S')}")
        cronometro = st.empty()
        stop_button = st.button("⏹️ Finalizar desarrollo")

        for i in range(segundos_transcurridos, segundos_transcurridos + 100000):
            if stop_button:
                dev_col.update_one({"_id": evento["_id"]}, {"$set": {"fin": datetime.now(tz), "en_curso": False}})
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

# === MÓDULO: ORDENADOR ===
elif seccion == "📸 Ordenador":
    st.subheader("📸 Ordenador con visión GPT-4o")

    if not st.session_state.orden_detectados:
        imagen = st.file_uploader("Subí una imagen", type=["jpg", "jpeg", "png"])
        if imagen:
            with st.spinner("Detectando objetos..."):
                detectados = detectar_objetos_con_openai(imagen.read())
                st.session_state.orden_detectados = detectados
                st.success("Objetos detectados correctamente.")

    if st.session_state.orden_detectados and not st.session_state.orden_confirmados:
        seleccion = st.multiselect(
            "Seleccioná los objetos para enfocar (el orden de tap define el orden):",
            options=st.session_state.orden_detectados,
            default=st.session_state.orden_seleccionados,
            key="orden_seleccionados"
        )
        if seleccion and st.button("✅ Confirmar y enfocar"):
            st.session_state.orden_confirmados = True
            st.session_state.orden_seleccionados = seleccion
            st.rerun()

    if st.session_state.orden_confirmados and not st.session_state.orden_actual:
        if st.session_state.orden_seleccionados:
            st.session_state.orden_actual = st.session_state.orden_seleccionados.pop(0)
            st.session_state.orden_timer_start = datetime.now(tz)
            st.rerun()

    if st.session_state.orden_actual:
        st.markdown(f"### 🔍 Enfocado en: **{st.session_state.orden_actual}**")
        cronometro = st.empty()
        stop_button = st.button("✅ Finalizar este enfoque")

        segundos = int((datetime.now(tz) - st.session_state.orden_timer_start).total_seconds())
        for i in range(segundos, segundos + 100000):
            if stop_button:
                duracion = datetime.now(tz) - st.session_state.orden_timer_start
                historial_col.insert_one({
                    "ítem": st.session_state.orden_actual,
                    "duración": str(duracion).split(".")[0],
                    "timestamp": datetime.now(tz),
                })
                st.session_state.orden_actual = None
                st.session_state.orden_timer_start = None
                if not st.session_state.orden_seleccionados:
                    st.success("🎯 Sesión completada.")
                    st.session_state.orden_detectados = []
                    st.session_state.orden_confirmados = False
                st.rerun()
            duracion = str(timedelta(seconds=i))
            cronometro.markdown(f"### ⏱️ Duración: {duracion}")
            time.sleep(1)

# === MÓDULO: HISTORIAL ===
elif seccion == "📂 Historial":
    st.subheader("📂 Historial de ejecución")

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