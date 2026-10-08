# 📍 Automação e Inteligência de Cercas VIRLOC

Ferramenta web desenvolvida em Python (Streamlit) para automatizar a extração, auditoria visual e roteirização de cercas eletrônicas para equipamentos de telemetria VIRLOC.

## 🚀 Principais Funcionalidades

*   **Conversão Automática:** Transforma arquivos KML (Google Earth/Maps) na sintaxe exata do equipamento VIRLOC instantaneamente.
*   **Auditoria Espacial:** Detecta automaticamente sobreposições e conflitos de limites de velocidade entre cercas.
*   **Mapa Interativo Híbrido:** Visualização de satélite e ruas para conferência do terreno.
*   **Roteirização Dinâmica:** Desenho de novos polígonos diretamente no mapa com geração de script em tempo real.
*   **Camadas Fantasmas:** Utilize polígonos antigos de KML como molde semi-transparente para desenhar correções por cima.

## 🛠️ Como Executar

1. Instale as dependências necessárias:
   ```bash
   pip install streamlit folium streamlit-folium pandas shapely geopy

Inicie a aplicação:
    python -m streamlit run VIRLOC.py


O painel será aberto automaticamente no seu navegador padrão (localhost:8501).
