import streamlit as st
from datetime import datetime
import base64
import openai
from pymongo import MongoClient
import pytz

# === CONFIGURACIÓN ===
st.set_page_config(page_title="🧠 orden-ador", layout="centered")

# Claves desde secrets
openai.api_key = st.secrets["openai_api_key"]
client = MongoClient(st.secrets["mongo_uri"])
db = client["ordenador"]
historial_col = db["historial"]

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

# === OPCIÓN 1: Desarrollo (vacío) ===
if seccion == "⏱ Desarrollo":
    st.subheader("⏱ Módulo de desarrollo")
    st.info("Esta sección aún no está implementada.")

# === OPCIÓN 2: Ordenador (funcional con OpenAI) ===
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

# === OPCIÓN 3: Historial (vacío) ===
elif seccion == "📂 Historial":
    st.subheader("📂 Historial de ejecución")
    st.info("Esta sección aún no está implementada.")