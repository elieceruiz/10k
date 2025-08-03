import streamlit as st
from datetime import datetime
from pymongo import MongoClient
import openai
import base64
from PIL import Image
from io import BytesIO
import time

# === CONFIGURACIÓN ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="wide")
st.title("👁️ Visión GPT-4o – Proyecto 10K")
st.markdown("📎 [Ver uso actual en OpenAI](https://platform.openai.com/usage)")

# === SECRETS ===
openai.api_key = st.secrets["openai_api_key"]
MONGO_URI = st.secrets["mongo_uri"]

# === CONEXIÓN A MONGO ===
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col_registros = db["registros"]
col_uso = db["uso_api"]

# === SUBIR IMAGEN ===
imagen_subida = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if imagen_subida:
    st.image(imagen_subida, caption="Imagen cargada", use_container_width=True)

    # Codificar imagen en base64 con cabecera
    imagen = Image.open(imagen_subida)
    buffered = BytesIO()
    imagen.save(buffered, format="JPEG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode()
    data_url = f"data:image/jpeg;base64,{img_b64}"

    # === DETECTAR SOLO UNA VEZ ===
    if "objetos_detectados" not in st.session_state:
        with st.spinner("🔍 Detectando objetos con GPT-4o..."):
            try:
                respuesta = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": data_url}},
                                {"type": "text", "text": "Devuélveme una lista de los objetos visibles en la imagen, separados por comas. No escribas explicaciones ni introducciones."}
                            ]
                        }
                    ],
                    max_tokens=100,
                    temperature=0.2,
                )

                contenido = respuesta.choices[0].message.content
                objetos = [x.strip() for x in contenido.split(",") if x.strip()]
                st.session_state.objetos_detectados = objetos

                # Guardar en Mongo
                col_registros.insert_one({
                    "timestamp": datetime.utcnow(),
                    "objetos_detectados": objetos,
                    "tokens_usados": 100
                })
                col_uso.insert_one({
                    "fecha": datetime.utcnow(),
                    "api_key_usada": openai.api_key[-6:],
                    "tokens_estimados": 100
                })

            except openai.RateLimitError:
                st.error("🚫 Has superado el límite de uso de la API de OpenAI.")
            except openai.AuthenticationError:
                st.error("❌ API Key inválida o no autorizada.")
            except Exception as e:
                st.error(f"⚠️ Error inesperado: {e}")

# === MOSTRAR RESULTADOS ===
if "objetos_detectados" in st.session_state:
    objetos_detectados = st.session_state.objetos_detectados
    st.success("✅ Objetos detectados por IA:")
    st.write(objetos_detectados)

    st.markdown("### ✅ Organiza:")

    orden_usuario = []
    for idx, obj in enumerate(objetos_detectados):
        if st.checkbox(obj, key=f"check_{idx}"):
            orden_usuario.append(obj)

    if orden_usuario and st.button("🕐 Iniciar sesión de orden"):
        st.session_state["tiempo_inicio"] = time.time()
        st.session_state["orden_usuario"] = orden_usuario
        st.success("⏱️ Cronómetro iniciado...")

    if "tiempo_inicio" in st.session_state:
        tiempo_actual = time.time()
        duracion = int(tiempo_actual - st.session_state["tiempo_inicio"])
        minutos, segundos = divmod(duracion, 60)
        st.info(f"🧭 Tiempo transcurrido: {minutos:02d}:{segundos:02d}")

        st.markdown("### 📦 Elementos seleccionados:")
        for i, item in enumerate(st.session_state["orden_usuario"], 1):
            st.markdown(f"- {i}. {item}")