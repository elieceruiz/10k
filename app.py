import streamlit as st
from datetime import datetime, timedelta
import time
import base64
import openai
from pymongo import MongoClient
from PIL import Image
from io import BytesIO

# === CONFIGURACIÓN ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

openai.api_key = st.secrets["openai_key"]
client = MongoClient(st.secrets["mongo_uri"])
db = client["proyecto_10k"]
col = db["objetos_organizados"]

# === SUBIDA DE IMAGEN ===
imagen = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if imagen:
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    # Codificamos para guardar
    bytes_imagen = imagen.read()
    imagen_pil = Image.open(BytesIO(bytes_imagen))
    buffered = BytesIO()
    imagen_pil.save(buffered, format="JPEG")
    imagen_codificada = base64.b64encode(buffered.getvalue()).decode()
    st.session_state.imagen_codificada = imagen_codificada
    st.session_state.imagen_nombre = imagen.name

    # === DETECCIÓN IA ===
    with st.spinner("Analizando con GPT-4o..."):
        prompt = "Enumera brevemente los objetos que aparecen en esta imagen. Solo lista los nombres, separados por comas. No des descripción."
        respuesta = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un asistente de visión que identifica objetos."},
                {"role": "user", "content": prompt},
                {"role": "user", "content": f"Imagen: {imagen_codificada}"},
            ],
            max_tokens=150
        )

    contenido = respuesta.choices[0].message.content
    objetos_detectados = [x.strip() for x in contenido.split(",") if x.strip()]

    st.markdown("### 🔎 Objetos detectados por IA:")
    seleccionados = {}

    for idx, obj in enumerate(objetos_detectados):
        check = st.checkbox(f"{obj}", key=f"chk_{idx}")
        if check:
            orden = st.number_input(f"Orden para '{obj}':", min_value=1, step=1, key=f"orden_{idx}")
            seleccionados[obj] = {"orden": orden}

    # === FLUJO DE ORGANIZACIÓN ===
    if seleccionados:
        st.divider()
        st.subheader("🛠️ Organización guiada")

        if "lista_ordenada" not in st.session_state:
            st.session_state.lista_ordenada = sorted(seleccionados.items(), key=lambda x: x[1]["orden"])
            st.session_state.paso_actual = 0

        lista_ordenada = st.session_state.lista_ordenada
        paso = st.session_state.paso_actual

        if paso < len(lista_ordenada):
            objeto_actual, data = lista_ordenada[paso]
            orden_actual = data["orden"]
            st.markdown(f"### 👉 Objeto {orden_actual}: **{objeto_actual}**")

            key_inicio = f"inicio_{objeto_actual}"
            key_tiempo = f"tiempo_{objeto_actual}"

            if key_inicio not in st.session_state:
                st.session_state[key_inicio] = None
                st.session_state[key_tiempo] = 0

            if st.session_state[key_inicio] is None:
                if st.button("⏱️ Iniciar organización"):
                    st.session_state[key_inicio] = time.time()
                    st.rerun()
            else:
                tiempo_actual = int(time.time() - st.session_state[key_inicio])
                st.session_state[key_tiempo] = tiempo_actual
                formato = str(timedelta(seconds=tiempo_actual))

                color = "green" if tiempo_actual < 120 else "red"
                icono = "" if tiempo_actual < 120 else "🔔"

                st.markdown(f"<h4>⏱️ Tiempo organizando: <span style='color:{color}'>{formato}</span> {icono}</h4>", unsafe_allow_html=True)

                # Alerta sonora cada 30s desde 2 min
                if tiempo_actual >= 120 and tiempo_actual % 30 == 0:
                    st.markdown("""
                        <audio autoplay>
                            <source src="https://www.soundjay.com/button/beep-07.wav" type="audio/wav">
                        </audio>
                    """, unsafe_allow_html=True)

                time.sleep(1)
                st.rerun()

            lugar = st.text_input(f"📍 ¿Dónde quedará '{objeto_actual}'?")

            if lugar and st.session_state[key_inicio] is not None:
                if st.button("✅ Registrar y pasar al siguiente"):
                    col.insert_one({
                        "fecha": datetime.utcnow(),
                        "objeto": objeto_actual,
                        "orden": orden_actual,
                        "lugar_asignado": lugar,
                        "tiempo_organizacion_segundos": st.session_state[key_tiempo],
                        "nombre_imagen": st.session_state.imagen_nombre,
                        "imagen_base64": st.session_state.imagen_codificada
                    })
                    st.success(f"📦 '{objeto_actual}' registrado.")
                    st.session_state.paso_actual += 1
                    st.rerun()
        else:
            st.balloons()
            st.success("🎉 Todos los objetos fueron organizados.")
            if st.button("🔄 Reiniciar todo"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

# === HISTORIAL ===
with st.expander("📜 Historial"):
    docs = list(col.find().sort("fecha", -1))
    if docs:
        import pandas as pd
        df = pd.DataFrame(docs)
        df["fecha"] = df["fecha"].dt.strftime("%Y-%m-%d %H:%M:%S")
        df = df[["fecha", "objeto", "orden", "lugar_asignado", "tiempo_organizacion_segundos"]]
        df["tiempo_h:m:s"] = df["tiempo_organizacion_segundos"].apply(lambda s: str(timedelta(seconds=s)))
        st.dataframe(df)

        # Progreso acumulado
        total_segundos = sum(doc.get("tiempo_organizacion_segundos", 0) for doc in docs)
        total_horas = total_segundos / 3600
        porcentaje = min(total_horas / 10000, 1.0)
        tiempo_formateado = str(timedelta(seconds=total_segundos))

        st.subheader("⏱️ Progreso hacia las 10.000 horas")
        st.markdown(f"**Tiempo acumulado organizando:** `{tiempo_formateado}`")
        st.progress(porcentaje, text=f"{total_horas:.2f} horas / 10.000 horas")
    else:
        st.info("Aún no hay registros.")