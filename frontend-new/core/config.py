import streamlit as st

# Render sidebar configuration panel
def render_sidebar():
    with st.sidebar:
        st.header("Configuration")

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
            # Model selection dropdown
            plate_model_option = st.selectbox(
                "Select recognize plate model:",
                ["YOLOv11m"],
                index=0
            )

            # Model selection dropdown
            number_model_option = st.selectbox(
                "Select recognize number model:",
                ["YOLOv11m"],
                index=0
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
        "max_length": max_length,
        "min_length": min_length,
        "plate_model_option":plate_model_option,
        "number_model_option":number_model_option
    }