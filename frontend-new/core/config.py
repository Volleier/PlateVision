import streamlit as st

# Render sidebar configuration panel
def render_sidebar():
    with st.sidebar:
        st.header("Configuration")

        # Model selection dropdown
        model_option = st.selectbox(
            "Select model:",
            ["YOLOv11m"],
            index=0
        )

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
            "Line 2",
            min_value=10,
            max_value=100,
            value=30,
            step=5
        )

        # Advanced options expander
        with st.expander("Advanced options"):
            # Whether to enable sampling
            do_sample = st.checkbox("Boolean", value=False)
            # Sampling temperature
            temperature = st.slider("Line 3", 0.1, 1.0, 0.7)
            # Number of beams for beam search
            num_beams = st.slider("Line 4", 1, 8, 4)

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
        "model_option": model_option,
        "max_length": max_length,
        "min_length": min_length,
        "do_sample": do_sample,
        "temperature": temperature,
        "num_beams": num_beams
    }