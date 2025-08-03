import streamlit as st
from pymongo import MongoClient
from datetime import datetime
from PIL import Image
import base64
from io import BytesIO
import openai
import pytz
import time

# === CONFIGURACIÓN DE LA APP ===
st.set_page_config(page_title="Visión GPT-4o – Proyecto 10K", layout="wide")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === CARGA DE SECRETOS ===
MONGO_URI = st.secrets["mongo_uri"]
OPENAI_API_KEY = st.secrets["openai_api_key"]

# === CONFIGURACIÓN DE CONEXIONES ===
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

openai.api_key = OPENAI_API_KEY
tz = pytz.timezone("America/Bogota")

# === FUNCIÓN PARA CONVERTIR IMAGEN A BASE64 ===
def convertir_imagen_base64(imagen):
    buffer = BytesIO()
    imagen.save(buffer, format="JPEG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/jpeg;base64,{img_b64}"

# === INICIALIZAR SESSION_STATE PARA LA SELECCIÓN ORDENADA ===
if "seleccionados" not in st.session_state:
    st.session_state.seleccionados = []

# === SUBIDA DE IMAGEN ===
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if uploaded_file:
    imagen = Image.open(uploaded_file)
    st.image(imagen, caption="✅ Imagen cargada", use_container_width=True)

    if st.button("🔍 Detectar objetos"):
        with st.spinner("Analizando imagen con GPT-4o..."):
            try:
                b64_img = convertir_imagen_base64(imagen)
                respuesta = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "user", "content": [
                            {"type": "text", "text": "Detecta solo objetos u elementos visibles. Devuelve una lista clara y concisa de los objetos sin descripciones largas ni contexto adicional."},
                            {"type": "image_url", "image_url": {"url": b64_img}}
                        ]}
                    ],
                    max_tokens=300,
                )

                # EXTRAER OBJETOS
                contenido = respuesta.choices[0].message.content
                objetos = [obj.strip("-• ") for obj in contenido.split("\n") if obj.strip()]

                # REINICIAR LISTA DE SELECCIONADOS SI HAY NUEVA DETECCIÓN
                st.session_state.seleccionados = []

                if objetos:
                    st.success("✅ Objetos detectados:")
                    st.write(objetos)

                    st.session_state.objetos_actuales = objetos

                else:
                    st.warning("⚠️ No se detectaron objetos en la imagen.")

            except Exception as e:
                st.error(f"Error en la detección: {e}")

# === INTERFAZ DE SELECCIÓN CON CHECKBOXES Y MULTISELECT ===
if "objetos_actuales" in st.session_state:
    restantes = [obj for obj in st.session_state.objetos_actuales if obj not in st.session_state.seleccionados]

    st.markdown("**🖱️ Marca los elementos para la tarea monotarea:**")
    for i, obj in enumerate(restantes):
        if st.checkbox(obj, key=f"chk_{obj}"):
            st.session_state.seleccionados.append(obj)
            st.rerun()  # ✅ CORRECTO

    if st.session_state.seleccionados:
        seleccionados_numerados = [f"{i+1}. {item}" for i, item in enumerate(st.session_state.seleccionados)]
        st.markdown("**📋 Orden de ejecución:**")
        st.multiselect("Seleccionados:", options=seleccionados_numerados, default=seleccionados_numerados, disabled=True)

    # === BOTÓN DE GUARDADO MANUAL ===
    if st.button("💾 Guardar sesión"):
        doc = {
            "timestamp": datetime.now(tz),
            "objetos": st.session_state.objetos_actuales,
            "nombre_archivo": uploaded_file.name
        }
        col.insert_one(doc)
        st.success("✅ Sesión guardada en la base de datos.")

# === HISTORIAL DE SESIONES ===
st.subheader("📚 Historial de sesiones")
registros = list(col.find().sort("timestamp", -1))
if registros:
    for reg in registros:
        fecha = reg.get("timestamp", datetime.now()).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(f"**🕓 {fecha}**")
        st.write("📦 Objetos detectados:")
        for i, obj in enumerate(reg.get("objetos", []), 1):
            st.write(f"- {obj}")
        st.markdown("---")
else:
    st.info("No hay sesiones completas registradas aún.")