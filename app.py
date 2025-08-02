import streamlit as st
import openai
import base64
import requests
from datetime import datetime
from pymongo import MongoClient

# === CONFIGURACIÓN GENERAL ===
st.set_page_config(page_title="👁️ Visión 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === CARGA DE SECRETOS DESDE STREAMLIT CLOUD ===
openai.api_key = st.secrets["openai_api_key"]
mongo_uri = st.secrets["mongo_uri"]

# === CONEXIÓN CON MONGO ===
client = MongoClient(mongo_uri)
db = client["proyecto10k"]
col = db["detecciones_10k"]

# === FUNCIÓN PARA OBTENER SALDO (con logs) ===
@st.cache_data(ttl=600)
def get_credit_balance():
    try:
        headers = {"Authorization": f"Bearer {openai.api_key}"}
        url = "https://api.openai.com/v1/dashboard/billing/credit_grants"
        response = requests.get(url, headers=headers)

        st.write("🔍 Status HTTP:", response.status_code)

        if response.status_code == 200:
            data = response.json()
            st.write("🧾 Respuesta:", data)
            return data.get("total_available", "No disponible")
        elif response.status_code == 401:
            return "❌ API Key inválida o no autorizada"
        elif response.status_code == 403:
            return "🔒 No tenés acceso a la API de facturación"
        else:
            return f"⚠️ Error HTTP {response.status_code}"
    except Exception as e:
        return f"⚠️ Error general: {str(e)}"

# === SUBIR IMAGEN ===
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if uploaded_file:
    st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)
    username = st.text_input("🧍 Tu nombre (opcional):", "eliecer")

    bytes_data = uploaded_file.read()
    encoded_image = base64.b64encode(bytes_data).decode("utf-8")
    image_url = f"data:image/jpeg;base64,{encoded_image}"

    # === CONSULTAR GPT-4o CON VISIÓN ===
    with st.spinner("Analizando imagen con GPT-4o..."):
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Eres un asistente que describe con detalle lo que ve en una imagen."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "¿Qué ves en esta imagen?"},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                ],
                max_tokens=300
            )
            result = response.choices[0].message.content
            st.success("🔎 Resultado del análisis:")
            st.write(result)

            # === REGISTRAR EN MONGO ===
            doc = {
                "usuario": username,
                "fecha": datetime.utcnow(),
                "descripcion": result,
                "nombre_imagen": uploaded_file.name,
                "saldo_openai": get_credit_balance()
            }
            col.insert_one(doc)
            st.info("✅ Registro guardado en MongoDB")

        except Exception as e:
            st.error(f"❌ Error al analizar la imagen: {str(e)}")

# === MOSTRAR SALDO DE OPENAI CON MANEJO DE ERRORES ===
st.divider()
st.subheader("💳 Saldo OpenAI actual:")
saldo = get_credit_balance()
if isinstance(saldo, float):
    st.write(f"**{saldo:.2f} USD**")
else:
    st.warning(f"{saldo}")

# === HISTORIAL DESDE MONGO ===
st.divider()
st.subheader("📚 Últimos análisis:")

registros = list(col.find().sort("fecha", -1))
if registros:
    for r in registros[:10]:
        st.markdown(f"**🧍 Usuario:** {r.get('usuario', 'Desconocido')}")
        st.markdown(f"🕒 **Fecha:** {r['fecha'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
        st.markdown(f"📝 **Descripción:** {r['descripcion']}")
        st.markdown(f"💳 **Saldo en ese momento:** {r.get('saldo_openai', 'N/A')} USD")
        st.markdown("---")
else:
    st.info("No hay registros guardados aún.")
