import streamlit as st
import openai
from PIL import Image
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="🧠 Visión IA 10K", layout="centered")
st.title("👁️ Visión IA – Detección de objetos")
openai.api_key = st.secrets["openai_api_key"]

# --- ESTADO INICIAL ---
if "objetos_detectados" not in st.session_state:
    st.session_state.objetos_detectados = []
if "seleccionados" not in st.session_state:
    st.session_state.seleccionados = []

# --- FUNCIÓN DE ANÁLISIS ---
def analizar_imagen(imagen_pil):
    buffered = io.BytesIO()
    imagen_pil.save(buffered, format="PNG")
    imagen_bytes = buffered.getvalue()

    try:
        respuesta = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un experto en identificar objetos en imágenes. Describe solo los objetos principales como si fueran etiquetas, separados por coma."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Describe brevemente los objetos visibles como lista."},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + imagen_bytes.decode("latin1")}}
                ]}
            ],
            max_tokens=100
        )

        texto = respuesta.choices[0].message.content
        objetos = [obj.strip(" .,-") for obj in texto.split(",") if obj.strip()]
        return objetos

    except Exception as e:
        st.error(f"❌ Error en la detección: {e}")
        return []

# --- SUBIR IMAGEN ---
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if uploaded_file:
    imagen = Image.open(uploaded_file)
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    if st.button("🔍 Detectar objetos con IA"):
        objetos = analizar_imagen(imagen)
        if objetos:
            st.session_state.objetos_detectados = objetos
            st.session_state.seleccionados = []
        else:
            st.warning("⚠️ No se detectaron objetos.")

# --- MOSTRAR OBJETOS DETECTADOS CON CHECKS ---
if st.session_state.objetos_detectados:
    st.markdown("### 📦 Objetos detectados:")
    nuevos = []
    for i, obj in enumerate(st.session_state.objetos_detectados):
        if st.checkbox(obj, key=f"check_{i}"):
            nuevos.append(obj)
    st.session_state.seleccionados = nuevos