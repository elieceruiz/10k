import streamlit as st
import openai
import base64
import requests
from datetime import datetime
from pymongo import MongoClient

# === CONFIG APP ===
st.set_page_config(page_title="👁️ Visión 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === SECRETS ===
openai.api_key = st.secrets["openai_api_key"]
mongo_uri = st.secrets["mongo_uri"]

# === CONEXIÓN MONGO ===
client = MongoClient(mongo_uri)
db = client["proyecto10k"]
col = db["detecciones_10k"]

# === CONSULTA DE SALDO OPENAI ===
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

# === CARGA DE IMAGEN ===
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if uploaded_file:
    st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)
    username = st.text_input("🧍 Tu nombre (opcional):", "eliecer")

    bytes_data = uploaded_file.read()
    encoded_image = base64.b64encode(bytes_data).decode("utf-8")
    image_url = f"data:image/jpeg;base64,{encoded_image}"

    # === GPT-4o LISTA OBJETOS ===
    with st.spinner("Detectando objetos en la imagen..."):
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Sos un asistente que detecta objetos en imágenes. Solo lista los objetos, sin contexto adicional."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Enumera los objetos principales que aparecen en esta imagen, separados por comas. No des ninguna explicación ni contexto extra."},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                ],
                max_tokens=150,
            )

            result = response.choices[0].message.content.strip()
            st.success("🧠 Objetos detectados por IA:")
            st.write(result)

            # Procesar lista de objetos
            objetos = [obj.strip() for obj in result.split(",") if obj.strip()]
            seleccionados = st.multiselect("✔️ ¿Cuáles objetos organizaste ya?", objetos)

            # === GUARDAR EN MONGO ===
            doc = {
                "usuario": username,
                "fecha": datetime.utcnow(),
                "objetos_detectados": objetos,
                "objetos_organizados": seleccionados,
                "nombre_imagen": uploaded_file.name,
                "saldo_openai": get_credit_balance()
            }
            col.insert_one(doc)
            st.info("✅ Registro guardado en MongoDB")

        except Exception as e:
            st.error(f"❌ Error al analizar la imagen: {str(e)}")

# === SALDO OPENAI + LINK ===
st.divider()
st.subheader("💳 Saldo en OpenAI:")
saldo = get_credit_balance()
if isinstance(saldo, float):
    st.write(f"**{saldo:.2f} USD**")
else:
    st.warning(saldo)

st.markdown("🔗 [Consulta tu uso de tokens en OpenAI Platform](https://platform.openai.com/usage)")

# === HISTORIAL DE REGISTROS ===
st.divider()
st.subheader("📚 Historial reciente:")

registros = list(col.find().sort("fecha", -1))
if registros:
    for r in registros[:10]:
        st.markdown(f"**🧍 Usuario:** {r.get('usuario', 'Desconocido')}")
        st.markdown(f"🕒 **Fecha:** {r['fecha'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
        st.markdown(f"🧠 **Detectado:** {', '.join(r.get('objetos_detectados', []))}")
        st.markdown(f"✔️ **Organizado:** {', '.join(r.get('objetos_organizados', []))}")
        st.markdown(f"💳 **Saldo en ese momento:** {r.get('saldo_openai', 'N/A')} USD")
        st.markdown("---")
else:
    st.info("No hay registros previos.")

