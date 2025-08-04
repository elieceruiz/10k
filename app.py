import streamlit as st
from datetime import datetime
import base64
import openai
from pymongo import MongoClient
import pytz

# === CONFIGURACIÓN GENERAL ===
st.set_page_config(page_title="🧠 orden-ador", layout="centered")
tz = pytz.timezone("America/Bogota")

# Claves de acceso desde .streamlit/secrets.toml
openai.api_key = st.secrets["openai_api_key"]
client = MongoClient(st.secrets["mongo_uri"])
db = client["ordenador"]
historial_col = db["historial"]

# === ESTADO BASE ===
for key, val in {
    "orden_detectados": [],
    "orden_seleccionados": [],
    "orden_confirmado": False,
    "orden_en_ejecucion": None,
    "orden_timer_start": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# === FUNCIÓN OPENAI VISUAL ===
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

# === INTERFAZ PRINCIPAL ===
seccion = st.selectbox("¿Dónde estás trabajando?", ["⏱ Desarrollo", "📸 Ordenador", "📂 Historial"])

# === OPCIÓN 1: Desarrollo (vacío) ===
if seccion == "⏱ Desarrollo":
    st.subheader("⏱ Módulo de desarrollo")
    st.info("Esta sección aún no está implementada.")

# === OPCIÓN 2: ORDENADOR VISUAL CON OPENAI ===
elif seccion == "📸 Ordenador":
    st.subheader("📸 Análisis de entorno con visión GPT-4o")

    imagen = st.file_uploader("Subí una imagen del entorno", type=["jpg", "jpeg", "png"])

    # 1. Detectar objetos si aún no hay
    if imagen and not st.session_state.orden_detectados and not st.session_state.orden_confirmado:
        with st.spinner("Detectando objetos..."):
            detectados = detectar_objetos_con_openai(imagen.read())
            st.session_state.orden_detectados = detectados
            st.success("Objetos detectados: " + ", ".join(detectados))
            st.rerun()

    # 2. Selección del orden
    if st.session_state.orden_detectados and not st.session_state.orden_confirmado and not st.session_state.orden_en_ejecucion:
        seleccionados = st.multiselect(
            "Seleccioná los elementos a organizar, en el orden deseado:",
            options=st.session_state.orden_detectados,
            default=st.session_state.get("orden_seleccionados", []),
            key="multiselect_orden"
        )
        st.session_state.orden_seleccionados = seleccionados

        if seleccionados and st.button("✅ Confirmar orden"):
            st.session_state.orden_confirmado = True
            st.success("Orden confirmado. Enfocando ejecución...")
            st.rerun()

    # 3. Ejecución centrada
    if st.session_state.orden_confirmado:

        # Si hay ítem en ejecución
        if st.session_state.orden_en_ejecucion:
            st.success(f"🟢 Ejecutando: **{st.session_state.orden_en_ejecucion}**")
            tiempo = datetime.now(tz) - st.session_state.orden_timer_start
            st.markdown(f"⏱ Tiempo transcurrido: `{str(tiempo).split('.')[0]}`")

            if st.button("✅ Finalizar este ítem"):
                historial_col.insert_one({
                    "ítem": st.session_state.orden_en_ejecucion,
                    "duración": str(tiempo).split(".")[0],
                    "timestamp": datetime.now(tz),
                })

                if st.session_state.orden_seleccionados:
                    siguiente = st.session_state.orden_seleccionados.pop(0)
                    st.session_state.orden_en_ejecucion = siguiente
                    st.session_state.orden_timer_start = datetime.now(tz)
                else:
                    st.session_state.orden_en_ejecucion = None
                    st.session_state.orden_timer_start = None
                    st.success("✅ Todos los ítems han sido ejecutados.")
                    st.session_state.orden_confirmado = False
                    st.session_state.orden_detectados = []
                    st.session_state.orden_seleccionados = []
                st.rerun()

        # Si aún no ha comenzado la ejecución
        elif st.session_state.orden_seleccionados:
            st.info("📝 Orden confirmado. Listo para iniciar.")
            st.markdown("**Orden establecido:**")
            for i, item in enumerate(st.session_state.orden_seleccionados, 1):
                st.markdown(f"{i}. {item}")
            if st.button("🚀 Iniciar ejecución"):
                st.session_state.orden_en_ejecucion = st.session_state.orden_seleccionados.pop(0)
                st.session_state.orden_timer_start = datetime.now(tz)
                st.rerun()

        # Si ya terminó todo
        else:
            st.success("✅ Todos los ítems ejecutados.")

# === OPCIÓN 3: HISTORIAL (vacío) ===
elif seccion == "📂 Historial":
    st.subheader("📂 Historial de ejecución")
    docs = list(historial_col.find({}).sort("timestamp", -1))
    if docs:
        for d in docs:
            st.markdown(f"**{d['ítem']}** — {d['duración']} ⏱")
            st.caption(d["timestamp"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S"))
            st.markdown("---")
    else:
        st.info("Aún no hay registros.")