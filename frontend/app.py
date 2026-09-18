import streamlit as st
import requests
from streamlit.components.v1 import html
from streamlit_extras.let_it_rain import rain
import json
import os

# Backend base URL: overridden by BACKEND_URL in Docker (http://backend:8000)
API_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# Configuration de la page
st.set_page_config(
    page_title="AIMMUNE - Diagnostic Expert des Maladies Auto-immunes",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🩺"
)

# CSS personnalisé premium avec animations
st.markdown("""
<style>
    /* Police premium */
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700&display=swap');
    
    :root {
        --primary: #2563eb;
        --primary-dark: #1d4ed8;
        --secondary: #7c3aed;
        --accent: #f59e0b;
        --light: #f8fafc;
        --dark: #0f172a;
        --success: #10b981;
        --warning: #f59e0b;
        --error: #ef4444;
        --gray: #94a3b8;
    }
    
    * {
        font-family: 'Montserrat', sans-serif;
        transition: all 0.3s ease;
    }
    
    /* Fond dégradé subtil */
    body {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        background-attachment: fixed;
    }
    
    /* En-tête animé */
    .header-animation {
        background: linear-gradient(90deg, var(--primary), var(--secondary));
        background-size: 200% auto;
        animation: gradient 8s ease infinite;
        color: white;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        margin-bottom: 2rem;
        text-align: center;
    }
    
    @keyframes gradient {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Cartes avec effet de profondeur */
    .card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(10px);
        transition: transform 0.3s, box-shadow 0.3s;
    }
    
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
    }
    
    /* Inputs stylisés */
    .stNumberInput > div > div > input, 
    .stTextInput > div > div > input,
    .stSelectbox > div > select {
        border: 2px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        font-size: 0.95rem;
    }
    
    .stNumberInput > div > div > input:focus, 
    .stTextInput > div > div > input:focus {
        border-color: var(--primary);
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
    }
    
    /* Bouton principal avec effet */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        color: white;
        border: none;
        border-radius: 10px;
        padding: 1rem 2rem;
        font-weight: 600;
        font-size: 1rem;
        cursor: pointer;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: all 0.3s;
        width: 100%;
        position: relative;
        overflow: hidden;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    .stButton > button::after {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(
            to bottom right,
            rgba(255, 255, 255, 0.3),
            rgba(255, 255, 255, 0.1)
        );
        transform: rotate(30deg);
        transition: all 0.3s;
    }
    
    .stButton > button:hover::after {
        left: 100%;
    }
    
    /* Sidebar premium */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--dark), #1e293b);
        color: white;
    }
    
    .sidebar .sidebar-content {
        background: transparent !important;
    }
    
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3 {
        color: white !important;
        font-weight: 600;
    }
    
    /* Animation de chargement personnalisée */
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    .loading-spinner {
        border: 4px solid rgba(255, 255, 255, 0.3);
        border-radius: 50%;
        border-top: 4px solid var(--primary);
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
        margin: 20px auto;
    }
    
    /* Résultats avec apparition progressive */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .result-card {
        animation: fadeIn 0.6s ease-out forwards;
    }
    
    /* Tooltips élégants */
    .tooltip {
        position: relative;
        display: inline-block;
    }
    
    .tooltip .tooltiptext {
        visibility: hidden;
        width: 200px;
        background-color: var(--dark);
        color: white;
        text-align: center;
        border-radius: 6px;
        padding: 8px;
        position: absolute;
        z-index: 1;
        bottom: 125%;
        left: 50%;
        transform: translateX(-50%);
        opacity: 0;
        transition: opacity 0.3s;
        font-size: 0.8rem;
    }
    
    .tooltip:hover .tooltiptext {
        visibility: visible;
        opacity: 1;
    }
    
    /* Responsive design amélioré */
    @media (max-width: 768px) {
        .card {
            padding: 1rem;
        }
        
        .header-animation h1 {
            font-size: 1.5rem;
        }
    }
    
    /* Effet de vague décoratif */
    .wave {
        position: absolute;
        bottom: 0;
        left: 0;
        width: 100%;
        overflow: hidden;
        line-height: 0;
    }
    
    .wave svg {
        position: relative;
        display: block;
        width: calc(100% + 1.3px);
        height: 50px;
    }
    
    .wave .shape-fill {
        fill: var(--primary);
        opacity: 0.1;
    }
</style>
""", unsafe_allow_html=True)

# Animation JavaScript pour effets supplémentaires
def inject_js():
    js_code = """
    <script>
    // Effet de parallaxe sur les cartes
    document.addEventListener('mousemove', function(e) {
        const cards = document.querySelectorAll('.card');
        cards.forEach(card => {
            const speed = card.getAttribute('data-parallax-speed') || 10;
            const x = (window.innerWidth - e.pageX * speed) / 100;
            const y = (window.innerHeight - e.pageY * speed) / 100;
            card.style.transform = `translateY(-5px) translateX(${x}px) translateY(${y}px)`;
        });
    });
    
    // Animation au scroll
    function animateOnScroll() {
        const elements = document.querySelectorAll('.animate-on-scroll');
        elements.forEach(el => {
            const elTop = el.getBoundingClientRect().top;
            const isVisible = (elTop < window.innerHeight * 0.8);
            if (isVisible) {
                el.classList.add('animated');
            }
        });
    }
    
    window.addEventListener('scroll', animateOnScroll);
    document.addEventListener('DOMContentLoaded', animateOnScroll);
    </script>
    """
    html(js_code)

# Effet de pluie de confetti pour le succès
# def show_confetti():
#     rain(
#         emoji="🎉",
#         font_size=20,
#         falling_speed=5,
#         animation_length=2
#     )

# En-tête animé avec dégradé
st.markdown("""
<div class="header-animation">
    <h1 style="margin: 0; font-size: 2.2rem; font-weight: 700;">AUTO-IMMUNES DIAGNOSTIC</h1>
    <p style="margin: 0.5rem 0 0; opacity: 0.9; font-size: 1.1rem;">
    Système Expert de Diagnostic des Maladies Auto-immunes
    </p>
</div>
""", unsafe_allow_html=True)

# Sidebar premium
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h2 style="color: white; margin-bottom: 0.5rem;">🩺 AIDE DIAGNOSTIC</h2>
        <div style="height: 3px; background: linear-gradient(90deg, var(--primary), var(--secondary)); margin: 0 auto; width: 50%;"></div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="card" style="background: rgba(255, 255, 255, 0.1); border: none;">
        <h3 style="color: white; margin-top: 0;">📋 Instructions</h3>
        <ol style="color: #e2e8f0; padding-left: 1.2rem;">
            <li style="margin-bottom: 0.5rem;">Remplissez tous les paramètres biologiques</li>
            <li style="margin-bottom: 0.5rem;">Cliquez sur 'Analyser'</li>
            <li>Consultez les résultats détaillés</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # st.markdown("""
    # <div class="card" style="background: rgba(255, 255, 255, 0.1); border: none;">
    #     <h3 style="color: white; margin-top: 0;">⚙️ Paramètres techniques</h3>
    # </div>
    # """, unsafe_allow_html=True)
    
    try:
        response = requests.get(f"{API_URL}/features")
        # if response.status_code == 200:
        #     st.json(response.json())
    except:
        st.warning("API non connectée")

# Formulaire médical premium
with st.form("medical_form"):
    cols = st.columns([1, 1, 0.2])  # Ajout d'une colonne vide pour l'espacement
    
    with cols[0]:
        st.markdown("""
        <div class="card" data-parallax-speed="5">
            <h2 style="color: var(--primary); margin-top: 0;">🧪 Paramètres Hématologiques</h2>
        """, unsafe_allow_html=True)
        hemoglobin = st.number_input("Hémoglobine (g/dL)", 0.00000, 2000.0, 12.72, 
                                help="Concentration d'hémoglobine dans le sang")
        rbc_count = st.number_input("RBC_Count (millions/µL)", 0.00000, 10.0, 4.33)
        hematocrit = st.number_input("Hématocrite (%)", 0.00000, 60.0, 39.99)
        wbc_count = st.number_input("WBC_Count (10³/µL)", 0.00000, 1000000.0, 8828.0)
        plt_count = st.number_input("Plaquettes (10³/µL)", 0.00000, 10000000.0, 276336.0)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with cols[1]:
        st.markdown("""
        <div class="card" data-parallax-speed="8">
            <h2 style="color: var(--primary); margin-top: 0;">🧬 Paramètres Biochimiques</h2>
        """, unsafe_allow_html=True)
        esr = st.number_input("ESR (mm/h)", 0.00000, 15000.0, 23.72843)
        c3 = st.number_input("C3 (mg/dL)", 0.00000, 50000.0, 67.43937)
        c4 = st.number_input("C4 (mg/dL)", 0.00000, 5000.0, 4.355488)
        # CRP = st.number_input("CRP (mg/dL)", 0.00000, 300.0, 46.44854)
        mpv = st.number_input("MPV (fL)", 0.0, 5000.0, 8.4)
        mbl_level = st.number_input("MBL Level (µg/mL)", 0.0, 5000.0, 0.95)
        esbach = st.number_input("Esbach (mg/L)", 0.00000, 50000.0, 239.696)
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Section avancée avec accordéon animé
    with st.expander("🔬 Paramètres Avancés", expanded=False):
        adv_cols = st.columns(2)
        
        with adv_cols[0]:
            st.markdown("""
            <div class="card animate-on-scroll">
                <h3 style="color: var(--primary); margin-top: 0;">Indices Érythrocytaires</h3>
            """, unsafe_allow_html=True)
            mcv = st.number_input("MCV (fL)", 0.00000, 15000.0, 84.71)
            mch = st.number_input("MCH (pg)", 0.00000, 5000.0, 26.67)
            mchc = st.number_input("MCHC (g/dL)", 0.00000, 5000.0, 31.25)
            rdw = st.number_input("RDW (%)", 0.00000, 5000.0, 14.62)
            st.markdown("</div>", unsafe_allow_html=True)
            
        with adv_cols[1]:
            st.markdown("""
            <div class="card animate-on-scroll">
                <h3 style="color: var(--primary); margin-top: 0;">Formule Leucocytaire</h3>
            """, unsafe_allow_html=True)
            reticulocyte_count = st.number_input("Réticulocytes (%)", 0.00000, 5000.0, 1.63)
            neutrophils = st.number_input("Neutrophiles (%)", 0.00000, 10000.0, 34.62)
            lymphocytes = st.number_input("Lymphocytes (%)", 0.00000, 10000.0, 25.83)
            monocytes = st.number_input("Monocytes (%)", 0.00000, 5000.0, 3.3)
            eosinophils = st.number_input("Éosinophiles (%)", 0.00000, 5000.0, 2.3)
            basophils = st.number_input("Basophiles (%)", 0.00000, 5000.0, 0.81)
            st.markdown("</div>", unsafe_allow_html=True)
    
    # Démographie
    st.markdown("---")
    demo_cols = st.columns(2)
    with demo_cols[0]:
        st.markdown("""
        <div class="card" style="border-left: 4px solid var(--accent);">
            <h3 style="color: var(--primary); margin-top: 0;"> Démographie Patient</h3>
        """, unsafe_allow_html=True)
        age = st.number_input("Âge du patient", 0, 120, 22)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with demo_cols[1]:
        st.markdown("""
        <div class="card" style="border-left: 4px solid var(--accent);">
        """, unsafe_allow_html=True)
        sickness_duration = st.number_input("Durée des symptômes (mois)", 0, 120, 43)
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Bouton de soumission premium
    submitted = st.form_submit_button(
        "Lancer l'Analyse Diagnostique",
        help="Cliquez pour exécuter l'algorithme de diagnostic"
    )

# Traitement après soumission avec animations
if submitted:
    data = {
        "Hemoglobin": hemoglobin,
        "RBC_Count": rbc_count,
        "Esbach": esbach,
        "C4": c4,
        "PLT_Count": plt_count,
        "MCHC": mchc,
        "Eosinophils": eosinophils,
        "Hematocrit": hematocrit,
        "Sickness_Duration_Months": sickness_duration,
        "Reticulocyte_Count": reticulocyte_count,
        "RDW": rdw,
        "MPV": mpv,
        "Basophils": basophils,
        "Lymphocytes": lymphocytes,
        "MCH": mch,
        "MBL_Level": mbl_level,
        "MCV": mcv,
        "Neutrophils": neutrophils,
        "WBC_Count": wbc_count,
        "Monocytes": monocytes,
        "Age": age,
        "ESR": esr,
        "C3": c3,
        # "CRP": CRP
    }
    
    try:
        # Animation de chargement personnalisée
        with st.spinner("Analyse en cours par notre intelligence artificielle..."):
            response = requests.post(f"{API_URL}/predict", json=data)
            
        if response.status_code == 200:
            result = response.json()
            
            # Affichage des résultats avec animations
            st.markdown("""
            <div class="result-card" style="background: linear-gradient(135deg, var(--success), #34d399);
                padding: 2rem; border-radius: 12px; color: white; margin-bottom: 2rem;
                box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.3);">
                <h2 style="color: white; margin: 0; display: flex; align-items: center;">
                    <span style="margin-right: 10px;">✅</span> Résultats de l'Analyse
                </h2>
            </div>
            """, unsafe_allow_html=True)
            
            if result['status'] == 'success':
                cols = st.columns([1, 1])
                
                with cols[0]:
                    st.markdown("""
                    <div class="result-card card" style="animation-delay: 0.2s; border-left: 4px solid var(--primary);">
                        <h3 style="color: var(--primary); margin-top: 0;">Diagnostic Prédit</h3>
                        <div style="font-size: 1.8rem; font-weight: 700; color: var(--dark); margin: 1rem 0;">
                            {diagnosis}
                        </div>
                        <div style="background: rgba(37, 99, 235, 0.1); padding: 1rem; border-radius: 8px;
                            border-left: 4px solid var(--primary); margin-top: 1rem;">
                            <p style="margin: 0; color: var(--dark);">
                                <span style="font-weight: 600;">Confiance:</span> {confidence}%
                            </p>
                        </div>
                    </div>
                    """.format(
                        diagnosis=result.get('diagnosis', 'N/A'),
                        confidence=result.get('confidence', 85)
                    ), unsafe_allow_html=True)
                
                # with cols[1]:
                #     st.markdown("""
                #     <div class="result-card card" style="animation-delay: 0.4s; border-left: 4px solid var(--accent);">
                #         <h3 style="color: var(--primary); margin-top: 0;">Marqueurs Clés</h3>
                #         <div style="margin: 1rem 0;">
                #             {markers}
                #         </div>
                #     </div>
                #     """.format(
                #         markers="<br>".join([f"• {k}: {v}" for k,v in result.get('key_markers', {}).items()])
                #         if result.get('key_markers') 
                #         else "Aucun marqueur spécifique identifié"
                #     ), unsafe_allow_html=True)
                
                # Recommandations cliniques avec onglets
                tab1, tab2, tab3 = st.tabs(["📋 Recommandations", "🔍 Examens Complémentaires", "📈 Surveillance"])
                
                with tab1:
                    if "lupus" in result['diagnosis'].lower():
                        st.markdown("""
                        <div class="card" style="border-left: 4px solid var(--warning);">
                            <h4 style="color: var(--warning); margin-top: 0;">LUPUS ÉRYTHÉMATEUX SYSTÉMIQUE</h4>
                            <ul style="color: var(--dark);">
                                <li>Consultation rhumatologique urgente sous 7 jours</li>
                                <li>Dosage des anticorps anti-ADN natif et anti-Sm</li>
                                <li>Analyse du complément sérique (CH50, C3, C4)</li>
                                <li>Surveillance rénale: protéinurie des 24h, créatininémie</li>
                                <li>Évaluation cardiovasculaire et neurologique</li>
                            </ul>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class="card" style="border-left: 4px solid var(--primary);">
                            <h4 style="color: var(--primary); margin-top: 0;">RECOMMANDATIONS GÉNÉRALES</h4>
                            <ul style="colowhr: var(--dark);">
                                <li>Surveillance biologique mensuelle pendant 3 mois</li>
                                <li>Consultation spécialisée sous 15 jours</li>
                                <li>Éliminer les causes secondaires (infectieuses, médicamenteuses)</li>
                                <li>Bilan auto-immun complet: AAN, ENA, ANCA</li>
                                <li>Évaluation des comorbidités associées</li>
                            </ul>
                        </div>
                        """, unsafe_allow_html=True)
                
                with tab2:
                    st.markdown("""
                    <div class="card">
                        <h4 style="color: var(--primary); margin-top: 0;">EXAMENS COMPLÉMENTAIRES</h4>
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem;">
                            <div style="background: rgba(37, 99, 235, 0.05); padding: 0.75rem; border-radius: 8px;">
                                <p style="font-weight: 600; margin: 0 0 0.5rem 0; color: var(--primary);">Sérologie</p>
                                <ul style="margin: 0; padding-left: 1.2rem;">
                                    <li>AAN avec réflexe</li>
                                    <li>Anti-ADN natif</li>
                                    <li>Anti-ENA</li>
                                    <li>Facteur rhumatoïde</li>
                                </ul>
                            </div>
                            <div style="background: rgba(37, 99, 235, 0.05); padding: 0.75rem; border-radius: 8px;">
                                <p style="font-weight: 600; margin: 0 0 0.5rem 0; color: var(--primary);">Imagerie</p>
                                <ul style="margin: 0; padding-left: 1.2rem;">
                                    <li>Radiographie thorax</li>
                                    <li>Échographie articulaire</li>
                                    <li>IRM cérébrale (si neuro)</li>
                                </ul>
                            </div>
                            <div style="background: rgba(37, 99, 235, 0.05); padding: 0.75rem; border-radius: 8px;">
                                <p style="font-weight: 600; margin: 0 0 0.5rem 0; color: var(--primary);">Biopsie</p>
                                <ul style="margin: 0; padding-left: 1.2rem;">
                                    <li>Peau (lésion cutanée)</li>
                                    <li>Rein (si néphropathie)</li>
                                    <li>Glandes salivaires</li>
                                </ul>
                            </div>
                            <div style="background: rgba(37, 99, 235, 0.05); padding: 0.75rem; border-radius: 8px;">
                                <p style="font-weight: 600; margin: 0 0 0.5rem 0; color: var(--primary);">Autres</p>
                                <ul style="margin: 0; padding-left: 1.2rem;">
                                    <li>ECG + Échocardiographie</li>
                                    <li>Ponction lombaire (si neuro)</li>
                                    <li>Capillaroscopie</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with tab3:
                    st.markdown("""
                    <div class="card">
                        <h4 style="color: var(--primary); margin-top: 0;">PROTOCOLE DE SURVEILLANCE</h4>
                        <div style="overflow-x: auto;">
                            <table style="width: 100%; border-collapse: collapse;">
                                <thead>
                                    <tr style="background-color: var(--primary); color: white;">
                                        <th style="padding: 0.75rem; text-align: left;">Paramètre</th>
                                        <th style="padding: 0.75rem; text-align: left;">Fréquence</th>
                                        <th style="padding: 0.75rem; text-align: left;">Valeurs Cibles</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr style="border-bottom: 1px solid #e2e8f0;">
                                        <td style="padding: 0.75rem;">Hémogramme</td>
                                        <td style="padding: 0.75rem;">Mensuel</td>
                                        <td style="padding: 0.75rem;">Hb > 10 g/dL</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #e2e8f0;">
                                        <td style="padding: 0.75rem;">Fonction rénale</td>
                                        <td style="padding: 0.75rem;">Trimestriel</td>
                                        <td style="padding: 0.75rem;">Créat < 100 µmol/L</td>
                                    </tr>
                                    <tr style="border-bottom: 1px solid #e2e8f0;">
                                        <td style="padding: 0.75rem;">Protéinurie</td>
                                        <td style="padding: 0.75rem;">Trimestriel</td>
                                        <td style="padding: 0.75rem;">< 0.5 g/24h</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 0.75rem;">Marqueurs inflammatoires</td>
                                        <td style="padding: 0.75rem;">Selon clinique</td>
                                        <td style="padding: 0.75rem;">CRP < 5 mg/L</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Bouton d'export des résultats
                col1, col2, col3 = st.columns([2, 3, 2])
                with col2:
                    st.download_button(
                        label="📄 Exporter le Rapport Complet",
                        data=json.dumps(result, indent=2),
                        file_name="diagnostic_immunologique.json",
                        mime="application/json",
                        help="Téléchargez un rapport détaillé du diagnostic"
                    )
                
                # Confetti pour célébrer la fin de l'analyse
                # show_confetti()
                inject_js()
                
            else:
                st.error("Erreur lors de l'analyse des données")
        else:
            st.error(f"Erreur API: {response.text}")
            
    except Exception as e:
        # st.error(f"Erreur de connexion: {str(e)}")
        st.info("Merci de votre intérêt pour notre système de détection des maladies auto-immunes !")

# Pied de page professionnel
st.markdown("---")
st.markdown(""" 
<div style="text-align: center; color: var(--gray); margin-top: 3rem; font-size: 0.9rem;">
    <p>AIMMUNE DIAGNOSTIC - Système Expert d'Aide au Diagnostic Immunologique</p>
    <p>© 2025 Tous droits réservés | Conforme RGPD | Version 2.3.8</p>
</div>
""", unsafe_allow_html=True)

# Injection du JavaScript pour les effets interactifs
inject_js()