import streamlit as st
import requests

st.set_page_config(page_title='AI Research Assistant', page_icon='[]', layout='wide')

st.title('AI Research Assistant')
st.caption('Powered by Langraph multi-agent system')

query = st.text_area('Enter your research question:', height=100, placeholder=
'e.g. What are the latest techniques for multi-agent coordination in LLMs?')

if st.button('Research', type='primary', use_container_width=True):
    if query.strip():
        with st.spinner('Agents working...'):
            try:
                response = requests.post('http://localhost:8000/research',
                json={'query': query})

                data = response.json()

                col1, col2 = st.columns([2, 1])

                with col1:
                    st.subheader('Answer')
                    st.markdown(data['answer'])

                with col2:
                    st.metric('Quality Score', f'{data["quality_score"]:.0%}')
                    with st.expander('Agent Log'):
                        for msg in data['messages']:
                            st.text(msg)

            except Exception as e:
                st.error(f'Error: {e}')
    else:
        st.warning('Please enter a question')
        