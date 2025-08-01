import streamlit as st
from deal_manager import DealManager, enhanced_deal_interface

# Page config
st.set_page_config(
    page_title="Fashion Deal Finder",
    page_icon="👗",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
.metric-container {
    background-color: #f0f2f6;
    padding: 1rem;
    border-radius: 0.5rem;
    margin: 0.5rem 0;
}
.deal-card {
    border: 1px solid #e6e9ef;
    border-radius: 0.5rem;
    padding: 1rem;
    margin: 1rem 0;
    background-color: white;
}
.discount-badge {
    background-color: #ff4b4b;
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# Run the main interface
if __name__ == "__main__":
    enhanced_deal_interface()
