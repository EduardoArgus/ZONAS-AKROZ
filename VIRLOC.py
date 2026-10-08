import streamlit as st
import xml.etree.ElementTree as ET
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium, folium_static
import re
import pandas as pd
from shapely.geometry import Polygon as ShapelyPolygon
from geopy.geocoders import Nominatim

# --- Inicialização de Memória (Session State) ---
if "cercas_kml" not in st.session_state:
    st.session_state.cercas_kml = []

# --- Funções Core ---
def formatar_coordenada(valor, is_longitude=False):
    valor_str = f"{float(valor):.5f}".replace(".", "")
    if is_longitude and len(valor_str) < 9:
        valor_str = valor_str[:1] + "0" + valor_str[1:]
    return valor_str

def extrair_velocidade(nome_cerca):
    match = re.search(r'(\d+)\s*km', nome_cerca, re.IGNORECASE)
    return match.group(1) if match else "50"

def obter_cor_prioridade(prio_str):
    try:
        p = int(prio_str)
        p = max(0, min(15, p))
        r = int(255 - (255 * (p / 15)))
        g = int(255 * (p / 15))
        return f"#{r:02x}{g:02x}00"
    except:
        return "#0052cc"

def gerar_script_virloc(nome_cerca, coordenadas, indice_inicial=1, prioridade="08", velocidade_override=None):
    velocidade = velocidade_override if velocidade_override else extrair_velocidade(nome_cerca)
    linhas_virloc = []
    
    for i, (lon, lat) in enumerate(coordenadas):
        lat_fmt = formatar_coordenada(lat)
        lon_fmt = formatar_coordenada(lon, True)
        tipo_ponto = "E" if i == len(coordenadas) - 1 else "P"
        # Ajustado para 2 dígitos (02d) no índice VSRN
        linhas_virloc.append(f"VSRN{indice_inicial+i:02d},{lat_fmt},{lon_fmt},0,0,{tipo_ponto},{velocidade},360,{prioridade}")
        
    return "\n".join(linhas_virloc)

def extrair_coordenadas_kml(kml_string):
    root = ET.fromstring(kml_string)
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    cercas = []
    
    for placemark in root.findall('.//kml:Placemark', ns):
        nome_elem = placemark.find('kml:name', ns)
        coord_elem = placemark.find('.//kml:coordinates', ns)
        if nome_elem is None or coord_elem is None:
            continue
            
        pontos = coord_elem.text.strip().split()
        coordenadas = [(float(p.split(',')[0]), float(p.split(',')[1])) for p in pontos]
        cercas.append({'nome': nome_elem.text, 'coordenadas': coordenadas})
    return cercas

def auditar_conflitos_espaciais(cercas):
    alertas = []
    poligonos = []
    
    for cerca in cercas:
        if len(cerca['coordenadas']) >= 3:
            poly = ShapelyPolygon(cerca['coordenadas'])
            vel = extrair_velocidade(cerca['nome'])
            poligonos.append({'nome': cerca['nome'], 'poly': poly, 'vel': vel})
            
    for i in range(len(poligonos)):
        for j in range(i + 1, len(poligonos)):
            p1, p2 = poligonos[i], poligonos[j]
            if p1['poly'].intersects(p2['poly']):
                if p1['vel'] != p2['vel']:
                    alertas.append(f"⚠️ **Conflito:** '{p1['nome']}' ({p1['vel']}km/h) sobrepõe '{p2['nome']}' ({p2['vel']}km/h).")
    return alertas

def renderizar_legenda():
    st.markdown("""
    <div style="margin-bottom: 15px;">
        <span style="font-size: 14px; font-weight: bold;">Legenda de Prioridade (0 a 15)</span>
        <div style="display: flex; width: 100%; height: 12px; background: linear-gradient(to right, #ff0000, #ffff00, #00ff00); border-radius: 3px; margin-top: 5px;"></div>
        <div style="display: flex; justify-content: space-between; width: 100%; font-size: 11px; color: #666; margin-top: 2px;">
            <span>0 (Máxima)</span>
            <span>7-8 (Média)</span>
            <span>15 (Mínima)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- Interface Streamlit ---
st.set_page_config(page_title="Roteirização VIRLOC", layout="wide")
st.title("Automação e Inteligência de Cercas")

aba1, aba2 = st.tabs(["Auditoria Analítica (KML)", "Desenho Avançado"])

# --- ABA 1: Auditoria e Exportação ---
with aba1:
    arquivo_kml = st.file_uploader("Upload do arquivo KML", type=["kml"])

    if arquivo_kml:
        dados_kml = arquivo_kml.getvalue().decode("utf-8")
        cercas = extrair_coordenadas_kml(dados_kml)
        st.session_state.cercas_kml = cercas  
        
        if cercas:
            alertas = auditar_conflitos_espaciais(cercas)
            if alertas:
                with st.expander("🚨 Alertas de Conflito Espacial Detectados", expanded=True):
                    for alerta in alertas:
                        st.markdown(alerta)
            
            dados_tabela = []
            indice_global = 1
            for cerca in cercas:
                dados_tabela.append({
                    "Nome da Cerca": cerca['nome'],
                    "Velocidade Limite": extrair_velocidade(cerca['nome']),
                    "Prioridade": "08",
                    "Total de Vértices": len(cerca['coordenadas']),
                    "Índice VIRLOC Inicial": f"VSRN{indice_global:02d}" # Ajustado para 2 dígitos
                })
                indice_global += len(cerca['coordenadas']) + 2 
            
            col_mapa, col_dados = st.columns(2)
            
            with col_dados:
                st.subheader("Edição de Metadados e Exportação")
                st.markdown("Edite as colunas **Velocidade Limite** ou **Prioridade**. As cores no mapa serão atualizadas.")
                
                df_export = pd.DataFrame(dados_tabela)
                df_editado = st.data_editor(df_export, use_container_width=True)
                
                scripts_finais = []
                indice_recalculo = 1
                
                for index, row in df_editado.iterrows():
                    cerca_atual = cercas[index]
                    prioridade_formatada = str(row["Prioridade"]).zfill(2)
                    velocidade_formatada = str(row["Velocidade Limite"])
                    
                    script = gerar_script_virloc(cerca_atual['nome'], cerca_atual['coordenadas'], indice_recalculo, prioridade_formatada, velocidade_formatada)
                    scripts_finais.append(f"// {cerca_atual['nome']}\n{script}")
                    indice_recalculo += len(cerca_atual['coordenadas']) + 2
                
                texto_final = "\n\n".join(scripts_finais)
                
                c1, c2 = st.columns(2)
                c1.download_button("📥 Baixar Script (.txt)", texto_final, file_name="cercas_virloc.txt")
                c2.download_button("📊 Baixar Base (.csv)", df_editado.to_csv(index=False), file_name="banco_cercas.csv", mime="text/csv")

            with col_mapa:
                st.subheader("Validação Geométrica")
                renderizar_legenda()
                
                mapa_auditoria = folium.Map(location=[cercas[0]['coordenadas'][0][1], cercas[0]['coordenadas'][0][0]], zoom_start=13)
                folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Google Híbrido', max_zoom=20).add_to(mapa_auditoria)
                folium.LayerControl().add_to(mapa_auditoria)
                
                for index, row in df_editado.iterrows():
                    cerca_atual = cercas[index]
                    pontos_folium = [(lat, lon) for lon, lat in cerca_atual['coordenadas']]
                    cor_poligono = obter_cor_prioridade(row["Prioridade"])
                    
                    folium.Polygon(
                        pontos_folium, 
                        tooltip=f"{cerca_atual['nome']} (Prio: {row['Prioridade']})", 
                        color=cor_poligono, 
                        fill_color=cor_poligono, 
                        fill_opacity=0.4
                    ).add_to(mapa_auditoria)
                    
                folium_static(mapa_auditoria)
    else:
        st.session_state.cercas_kml = [] 

# --- ABA 2: Ferramentas Avançadas de Desenho ---
with aba2:
    st.markdown("Busque a região de operação e desenhe polígonos livremente.")
    renderizar_legenda()
    
    # Criando colunas para agrupar a barra de pesquisa e o Toggle Button
    col_busca, col_toggle = st.columns([2, 1])
    
    with col_busca:
        cidade_busca = st.text_input("🔍 Pesquisar Região", "")
        
    with col_toggle:
        st.write("") # Espaçamento para alinhar com o campo de texto
        st.write("")
        mostrar_fantasma = st.toggle("👻 Ativar Camadas Fantasmas", value=True)
        
    lat_inicial, lon_inicial = -22.8407, -47.6496
    
    if st.session_state.cercas_kml:
        lat_inicial = st.session_state.cercas_kml[0]['coordenadas'][0][1]
        lon_inicial = st.session_state.cercas_kml[0]['coordenadas'][0][0]
    
    if cidade_busca:
        geolocator = Nominatim(user_agent="virloc_roteirizador")
        try:
            local = geolocator.geocode(cidade_busca)
            if local:
                lat_inicial, lon_inicial = local.latitude, local.longitude
        except:
            pass
    
    col_mapa2, col_script2 = st.columns(2)
    
    with col_mapa2:
        mapa_desenho = folium.Map(location=[lat_inicial, lon_inicial], zoom_start=13)
        folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Google Híbrido', max_zoom=20).add_to(mapa_desenho)
        folium.LayerControl().add_to(mapa_desenho)
        
        # INJEÇÃO DAS CAMADAS FANTASMAS COM BOTÃO DE CONTROLE
        if st.session_state.cercas_kml and mostrar_fantasma:
            st.info("Usando referências do KML como molde para desenho.")
            for cerca in st.session_state.cercas_kml:
                pontos_folium = [(lat, lon) for lon, lat in cerca['coordenadas']]
                folium.Polygon(
                    pontos_folium,
                    tooltip=f"REFERÊNCIA: {cerca['nome']}",
                    color="#ffff00",          
                    weight=2,                 
                    dash_array='5, 5',        
                    fill_color="#ffff00",
                    fill_opacity=0.15         
                ).add_to(mapa_desenho)
        
        Draw(
            export=False, 
            position='topleft', 
            draw_options={'polyline': False, 'rectangle': False, 'circle': False, 'marker': False, 'circlemarker': False},
            edit_options={'edit': True, 'remove': True}
        ).add_to(mapa_desenho)
        
        dados_mapa = st_folium(mapa_desenho, width=600, height=500)
        
    with col_script2:
        st.subheader("Roteiro Interativo")
        
        if dados_mapa and dados_mapa.get("all_drawings"):
            scripts_desenhados = []
            indice_desenho = 1
            
            for i, desenho in enumerate(dados_mapa["all_drawings"]):
                if desenho["geometry"]["type"] == "Polygon":
                    coordenadas_desenho = desenho["geometry"]["coordinates"][0]
                    
                    c1, c2 = st.columns([3, 1])
                    nome_cerca = c1.text_input(f"Nome da Cerca {i+1}", f"Cerca 50 km - Área {i+1}", key=f"nome_cerca_{i}")
                    prio_cerca = c2.text_input(f"Prioridade (0-15)", "08", key=f"prio_cerca_{i}")
                    
                    script = gerar_script_virloc(nome_cerca, coordenadas_desenho, indice_desenho, prio_cerca.zfill(2))
                    scripts_desenhados.append(f"// {nome_cerca}\n{script}")
                    indice_desenho += len(coordenadas_desenho) + 2
            
            texto_desenho = "\n\n".join(scripts_desenhados)
            st.download_button("📥 Baixar Script Desenhado", texto_desenho, file_name="novas_cercas_virloc.txt")
            st.code(texto_desenho, language="text")