import streamlit as st
from datetime import datetime
import time
import openai
import base64
from pymongo import MongoClient
import pytz

# === CONFIGURACIÓN ===
st.set_page_config(page_title="🧠 orden-ador", layout="centered")

# Claves desde secrets (en minúscula, como las definiste)
openai.api_key = st.secrets["openai_api_key"]
client = MongoClient(st.secrets["mongo_uri"])
db = client["ordenador"]
historial_col = db["historial"]

# Zona horaria Colombia
tz = pytz.timezone("America/Bogota")

# === ESTADO DE SESIÓN ===
for key, default in {
    "dev_timer_running": False,
    "dev_timer_start": None,
    "dev_total_seconds": 0,
    "orden_detectados": [],
    "orden_asignados": [],
    "orden_en_ejecucion": None,
    "orden_timer_start": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# === FUNCIÓN GPT-4o VISIÓN ===
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

# === NAVEGACIÓN PRINCIPAL ===
seccion = st.selectbox("¿Dónde estás trabajando?", ["⏱ Desarrollo", "📸 Ordenador", "📂 Historial"])

# === MÓDULO 1: DESARROLLO ===
if seccion == "⏱ Desarrollo":
    st.subheader("⏱ Tiempo dedicado al desarrollo de orden-ador")

    if st.button("Iniciar" if not st.session_state.dev_timer_running else "Pausar"):
        if not st.session_state.dev_timer_running:
            st.session_state.dev_timer_start = datetime.now(tz)
        else:
            elapsed = (datetime.now(tz) - st.session_state.dev_timer_start).total_seconds()
            st.session_state.dev_total_seconds += elapsed
        st.session_state.dev_timer_running = not st.session_state.dev_timer_running

    if st.session_state.dev_timer_running:
        elapsed = (datetime.now(tz) - st.session_state.dev_timer_start).total_seconds()
    else:
        elapsed = 0

    total = st.session_state.dev_total_seconds + elapsed
    horas, rem = divmod(int(total), 3600)
    minutos, segundos = divmod(rem, 60)
    st.metric("Tiempo acumulado", f"{horas:02}:{minutos:02}:{segundos:02}")

# === MÓDULO 2: ORDENADOR ===
elif seccion == "📸 Ordenador":
    st.subheader("📸 Cargar imagen y asignar orden de ejecución")

    imagen = st.file_uploader("Subí una imagen", type=["jpg", "jpeg", "png"])

    if imagen and not st.session_state.orden_detectados:
        with st.spinner("Detectando objetos con GPT-4o..."):
            detectados = detectar_objetos_con_openai(imagen.read())
            st.session_state.orden_detectados = detectados
            st.success("Objetos detectados: " + ", ".join(detectados))

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

# === MÓDULO 3: HISTORIAL ===
elif seccion == "📂 Historial":
    st.subheader("📂 Historial registrado (MongoDB)")
    datos = list(historial_col.find().sort("timestamp", -1))

    if not datos:
        st.info("Aún no hay datos registrados.")
    else:
        for i, r in enumerate(datos, 1):
            fecha = r['timestamp'].astimezone(tz).strftime('%Y-%m-%d %H:%M:%S')
            st.write(f"{i}. **{r['ítem']}** — {r['duración']} ({fecha})")