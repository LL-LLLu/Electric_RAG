import streamlit as st
import requests
import os

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Equipment Browser", page_icon="", layout="wide")

st.title("Equipment Browser")

col1, col2 = st.columns([2, 2])

with col1:
    search_term = st.text_input("Search equipment", placeholder="Enter equipment tag...")

with col2:
    try:
        types_response = requests.get(f"{BACKEND_URL}/api/equipment/types", timeout=5)
        if types_response.status_code == 200:
            equipment_types = ["All"] + types_response.json()
        else:
            equipment_types = ["All"]
    except Exception:
        equipment_types = ["All"]

    selected_type = st.selectbox("Filter by type", equipment_types)

try:
    params = {"limit": 100}
    if search_term:
        params["search"] = search_term
    if selected_type != "All":
        params["equipment_type"] = selected_type

    response = requests.get(f"{BACKEND_URL}/api/equipment/", params=params, timeout=10)

    if response.status_code == 200:
        equipment_list = response.json()

        if not equipment_list:
            st.info("No equipment found.")
        else:
            st.markdown(f"**Found {len(equipment_list)} equipment items**")

            for eq in equipment_list:
                with st.expander(f"{eq['tag']} - {eq.get('equipment_type', 'Unknown')}"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown(f"**Tag:** {eq['tag']}")
                        st.markdown(f"**Type:** {eq.get('equipment_type', 'N/A')}")
                        if eq.get('description'):
                            st.markdown(f"**Description:** {eq['description'][:200]}...")

                    with col2:
                        if eq.get('manufacturer'):
                            st.markdown(f"**Manufacturer:** {eq['manufacturer']}")
                        if eq.get('model_number'):
                            st.markdown(f"**Model:** {eq['model_number']}")

                    if st.button("View Details", key=f"details_{eq['id']}"):
                        detail_response = requests.get(f"{BACKEND_URL}/api/equipment/{eq['tag']}", timeout=10)
                        if detail_response.status_code == 200:
                            detail = detail_response.json()

                            if detail.get('locations'):
                                st.markdown("**Locations:**")
                                for loc in detail['locations']:
                                    st.write(f"- {loc['document_filename']}, Page {loc['page_number']}")

                            if detail.get('controls'):
                                st.markdown("**Controls:**")
                                for rel in detail['controls']:
                                    st.write(f"- {rel['target_tag']}")

                            if detail.get('controlled_by'):
                                st.markdown("**Controlled by:**")
                                for rel in detail['controlled_by']:
                                    st.write(f"- {rel['source_tag']}")

except requests.exceptions.ConnectionError:
    st.error("Could not connect to backend.")
except Exception as e:
    st.error(f"Error: {str(e)}")
