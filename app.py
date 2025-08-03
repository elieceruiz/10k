import streamlit as st
from pymongo import MongoClient
import openai
from datetime import datetime
from PIL import Image
import pytz
import time
import base64
from io import BytesIO

# === CONFIGURACIÓN ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === CREDENCIALES Y CONEXIÓN ===
openai.api_key = st.secrets["openai_api_key"]
client = MongoClient(st.secrets["mongo_uri"])
db = client["proyecto_10k"]
col = db["registro_sesiones"]
tz = pytz.timezone("America/Bogota")

# === ESTADO DE SESIÓN ===
if "objetos" not in st.session_state:
    st.session_state.objetos = []
if "orden" not in st.session_state:
    st.session_state.orden = []
if "tiempos" not in st.session_state:
    st.session_state.tiempos = {}
if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "imagen_guardada" not in st.session_state:
    st.session_state.imagen_guardada = None

# === SUBIR IMAGEN ===
imagen = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if imagen:
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    # Guardar imagen temporalmente
    img = Image.open(imagen)
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    img_bytes = buffered.getvalue()
    encoded_image = base64.b64encode(img_bytes).decode()

    # Detectar objetos automáticamente solo si aún no se ha hecho
    if not st.session_state.objetos:
        try:
            respuesta = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un asistente que detecta solo los objetos visibles en una imagen. Devuélvelos como lista en Python. Sin explicaciones."
                    },
                    {
                        "role": "user",
                        "content": f"La siguiente imagen está codificada en base64:\n{encoded_image}"
                    }
                ],
                max_tokens=300,
                temperature=0.2
            )
            texto = respuesta.choices[0].message.content

            # Extraer lista con expresiones regulares si no es un formato válido
            import re
            posibles = re.findall(r'"(.*?)"|\'(.*?)\'|(?<=- )(.+)', texto)
            planos = [x[0] or x[1] or x[2] for x in posibles if any(x)]

            if planos:
                st.session_state.objetos = planos
            else:
                st.warning("❌ No se detectaron objetos.")

        except Exception as e:
            st.error(f"Error en la detección: {e}")

# === MOSTRAR OBJETOS Y SELECCIÓN DE ORDEN ===
if st.session_state.objetos:
    st.subheader("📦 Objetos detectados")
    seleccionados = {}
    for i, obj in enumerate(st.session_state.objetos):
        seleccionados[obj] = st.checkbox(f"{i+1}. {obj}")

    if st.button("✅ Iniciar cronómetro con seleccionados"):
        orden = [obj for obj, marcado in seleccionados.items() if marcado]
        if orden:
            st.session_state.orden = orden
            st.session_state.start_time = time.time()
            st.rerun()
        else:
            st.warning("Selecciona al menos un objeto para iniciar.")

# === CRONÓMETRO Y REGISTRO ===
if st.session_state.start_time and st.session_state.orden:
    st.subheader("⏱ Cronómetro en marcha...")
    now = time.time()
    elapsed = int(now - st.session_state.start_time)
    minutos, segundos = divmod(elapsed, 60)
    st.markdown(f"🧭 Tiempo transcurrido: **{minutos:02d}:{segundos:02d}**")

    # Mostrar objetos en orden para "ubicar"
    st.markdown("### 🗂 Orden actual:")
    for i, obj in enumerate(st.session_state.orden, 1):
        st.write(f"{i}. {obj}")

    if elapsed >= 120:  # A los 2 minutos se permite registrar
        if st.button("📥 Guardar sesión y reiniciar"):
            doc = {
                "objetos": st.session_state.orden,
                "duracion_segundos": elapsed,
                "timestamp": datetime.now(tz),
                "imagen": encoded_image
            }
            col.insert_one(doc)
            st.success("✅ Sesión registrada exitosamente.")
            st.session_state.objetos = []
            st.session_state.orden = []
            st.session_state.start_time = None
            st.session_state.tiempos = {}
            st.session_state.imagen_guardada = None
            st.rerun()

# === USO API OPENAI ===
st.markdown("---")
st.markdown("🔎 [Consulta tu uso de créditos OpenAI](https://platform.openai.com/usage)")