import streamlit as st
from pathlib import Path

# Render sidebar configuration panel
def render_sidebar():
    with st.sidebar:
        st.header("Configuration")

        # Automatically scan the model files (.pt) in the backend/static/models/plate directory
        def scan_plate_models(subpath="backend/static/models/plate", patterns=("*.pt",)):
            project_root = Path(__file__).resolve().parents[2]
            models_dir = project_root / subpath
            models = []
            try:
                for pat in patterns:
                    models.extend([p.stem for p in sorted(models_dir.glob(pat)) if p.is_file()])
            except Exception:
                models = []
            return models or ["No recognize plate models found"]

        plate_models = scan_plate_models("backend/static/models/plate", ("*.pt",))
        plate_model_option = st.selectbox(
            "Select recognize plate model:",
            plate_models,
            index=0
        )

        # Automatically scan the model files (.pt) in the backend/static/models/number directory
        def scan_number_models(subpath="backend/static/models/number", patterns=("*.pt",)):
            project_root = Path(__file__).resolve().parents[2]
            models_dir = project_root / subpath
            models = []
            try:
                for pat in patterns:
                    models.extend([p.stem for p in sorted(models_dir.glob(pat)) if p.is_file()])
            except Exception:
                models = []
            return models or ["No recognize number models found"]

        number_models = scan_number_models("backend/static/models/number", ("*.pt",))
        number_model_option = st.selectbox(
            "Select recognize number model:",
            number_models,
            index=0
        )

        # Advanced options expander
        with st.expander("Advanced options"):
            # Max summary length slider
            max_length = st.slider(
                "Line 1:",
                min_value=50,
                max_value=300,
                value=150,
                step=10
            )

            # Min summary length slider
            min_length = st.slider(
                "Line 2:",
                min_value=10,
                max_value=100,
                value=30,
                step=5
            )

        st.markdown("---")
        # Usage instructions
        st.info("""
        **Instructions:**
        1. Enter or paste image below
        2. Adjust parameters on the left
        3. Click the 'Generate Recognition' button
        4. View results and evaluation metrics
        """)

    # Return configuration dict for main app
    return {
        "models": {
            "plate_model": plate_model_option,
            "number_model": number_model_option
        },
        "options": {
            "max_length": max_length,
            "min_length": min_length
        }
    }
