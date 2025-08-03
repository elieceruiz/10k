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

    # Codificar imagen
    img_bytes = imagen_subida.read()
    img_b64 = base64.b64encode(img_bytes).decode()

    # Enviar a OpenAI
    with st.spinner("🔍 Detectando objetos con GPT-4o..."):
        try:
            respuesta = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un modelo de visión. Devuelve solo una lista de objetos detectados en la imagen, separados por comas. No escribas explicaciones.",
                    },
                    {
                        "role": "user",
                        "content": f"A continuación, una imagen en base64: {img_b64[:500]}... (truncado)",
                    },
                ],
                max_tokens=100,
                temperature=0.2,
            )
            contenido = respuesta.choices[0].message.content
            objetos_detectados = [x.strip() for x in contenido.split(",") if x.strip()]
            st.success("✅ Objetos detectados por IA:")
            st.write(objetos_detectados)

            # Mostrar checkboxes y orden
            st.markdown("### ✅ Organiza:")
            orden_usuario = []
            for idx, obj in enumerate(objetos_detectados):
                if st.checkbox(obj, key=obj):
                    orden_usuario.append(obj)

            # Contador simple
            if "llamadas_api" not in st.session_state:
                st.session_state["llamadas_api"] = 0
            st.session_state["llamadas_api"] += 1

            # Cronómetro y registro si ordenó algo
            if orden_usuario:
                if st.button("🕐 Iniciar sesión de orden"):
                    start_time = datetime.utcnow()
                    st.session_state["tiempo_inicio"] = time.time()
                    st.success("⏱️ Cronómetro iniciado...")

            if "tiempo_inicio" in st.session_state:
                tiempo_actual = time.time()
                duracion = int(tiempo_actual - st.session_state["tiempo_inicio"])
                st.info(f"⏳ Tiempo: {duracion // 60:02d}:{duracion % 60:02d}")

            # Guardar en Mongo
            doc = {
                "timestamp": datetime.utcnow(),
                "objetos_detectados": objetos_detectados,
                "orden_usuario": orden_usuario,
                "llamada_nro": st.session_state["llamadas_api"],
            }
            col_registros.insert_one(doc)

            col_uso.insert_one({
                "fecha": datetime.utcnow(),
                "api_key_usada": openai.api_key[-6:],  # Final para referencia
                "tokens_estimados": 100
            })

        except openai.RateLimitError:
            st.error("🚫 Has superado el límite de uso de la API de OpenAI.")
        except openai.AuthenticationError:
            st.error("❌ API Key inválida o no autorizada.")
        except Exception as e:
            st.error(f"⚠️ Error inesperado: {e}")
else:
    st.info("📷 Carga una imagen para comenzar.")