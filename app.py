import streamlit as st
from pymongo import MongoClient
from PIL import Image
import openai
import io
from datetime import datetime
import time
import pytz

# === CONFIGURACIÓN INICIAL ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === SECRETS Y ZONA HORARIA ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

openai.api_key = st.secrets["openai_api_key"]
tz = pytz.timezone("America/Bogota")

# === VARIABLES DE SESIÓN ===
if "objetos" not in st.session_state:
    st.session_state.objetos = []
if "iniciar_tiempo" not in st.session_state:
    st.session_state.iniciar_tiempo = False
if "inicio_objeto" not in st.session_state:
    st.session_state.inicio_objeto = None
if "objetos_finalizados" not in st.session_state:
    st.session_state.objetos_finalizados = []
if "registro" not in st.session_state:
    st.session_state.registro = []

# === SUBIR IMAGEN ===
imagen = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if imagen:
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    if st.button("🧠 Detectar objetos"):
        try:
            image = Image.open(imagen).convert("RGB")
            buf = io.BytesIO()
            image.save(buf, format='PNG')
            byte_im = buf.getvalue()

            prompt = "Describe brevemente los objetos visibles en esta imagen en formato lista simple, sin detalles ni contexto, solo nombres de objetos."
            base64_image = f"data:image/png;base64,{imagen.getvalue().hex()[:50]}"  # Dummy just to show size

            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Eres un asistente de visión artificial que identifica objetos."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.2
            )
            texto = response.choices[0].message.content
            objetos_detectados = [line.strip("-• ").strip() for line in texto.splitlines() if line.strip()]
            st.session_state.objetos = objetos_detectados
            st.session_state.objetos_finalizados = []
            st.session_state.registro = []
            st.success("✅ Objetos detectados por IA.")

        except Exception as e:
            st.error(f"Error en la detección: {e}")

# === MOSTRAR OBJETOS DETECTADOS CON CHECKS ===
if st.session_state.objetos:
    st.subheader("📦 Objetos detectados:")
    for obj in st.session_state.objetos:
        if obj not in st.session_state.objetos_finalizados:
            if st.button(f"✅ Iniciar con: {obj}"):
                st.session_state.inicio_objeto = (obj, time.time())
                st.session_state.iniciar_tiempo = True

# === CRONÓMETRO OBJETO ===
if st.session_state.iniciar_tiempo and st.session_state.inicio_objeto:
    obj, inicio = st.session_state.inicio_objeto
    st.markdown(f"⏳ **Ordenando:** `{obj}`")

    elapsed = int(time.time() - inicio)
    st.markdown(f"🧭 Tiempo transcurrido: **{elapsed} segundos**")

    if elapsed >= 120:  # 2 minutos por objeto
        st.success(f"✅ Objeto `{obj}` ordenado en {elapsed} segundos.")
        st.session_state.objetos_finalizados.append(obj)
        st.session_state.registro.append({"objeto": obj, "duracion": elapsed})

        st.session_state.iniciar_tiempo = False
        st.session_state.inicio_objeto = None

        # Guardar en MongoDB
        doc = {
            "timestamp": datetime.now(tz),
            "objetos": [obj],
            "duracion_segundos": elapsed
        }
        try:
            col.insert_one(doc)
        except Exception as err:
            st.warning(f"No se pudo guardar en MongoDB: {err}")

        st.rerun()

# === HISTORIAL DE SESIONES ===
with st.expander("📚 Historial de sesiones"):
    try:
        registros = list(col.find().sort("timestamp", -1))
        for reg in registros:
            try:
                fecha = reg["timestamp"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
            except KeyError:
                fecha = "Fecha no disponible"
            objetos = ", ".join(reg.get("objetos", []))
            dur = reg.get("duracion_segundos", 0)
            st.markdown(f"- **{fecha}** → ⏱ {dur} seg | 📦 {objetos}")
    except Exception as err:
        st.error(f"Error al acceder al historial: {err}")