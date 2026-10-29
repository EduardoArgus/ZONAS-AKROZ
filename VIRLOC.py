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

def gerar_script_virloc(nome_cerca, coordenadas, indice_inicial=160, prioridade="08", velocidade_override=None):
    velocidade = velocidade_override if velocidade_override else extrair_velocidade(nome_cerca)
    linhas_virloc = []
    
    for i, (lon, lat) in enumerate(coordenadas):
        lat_fmt = formatar_coordenada(lat)
        lon_fmt = formatar_coordenada(lon, True)
        tipo_ponto = "E" if i == len(coordenadas) - 1 else "P"
        linhas_virloc.append(f"VSRN{indice_inicial+i:03d},{lat_fmt},{lon_fmt},0,0,{tipo_ponto},{velocidade},360,{prioridade}")
        
    return "\n".join(linhas_virloc)

def gerar_rodape_regiao(primeiro_ponto, ultimo_ponto):
    return (
        f"Região 00 -\n"
        f">VSRM00,1,{primeiro_ponto},{ultimo_ponto},3D,MD50<\n"
        f">SUT38,VQRM00,82,3,0,0< //CAPTURA VELOCIDADE DA CERCA ATUAL\n"
        f">SED86 RS00++ +- SGN NN {{PFL,vel,0,9}}<\n"
        f">SED92 RR00++ +- SGN NN {{SCT06 VUT38}}<"
    )

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

def calcular_centroide(coordenadas):
    if len(coordenadas) >= 3:
        poly = ShapelyPolygon(coordenadas)
        return poly.centroid.y, poly.centroid.x
    return coordenadas[0][1], coordenadas[0][0]

def auditar_e_definir_prioridades(cercas, velocidades_custom=None):
    n = len(cercas)
    prioridades = ["08"] * n
    alertas = []
    poligonos = []
    
    for i, cerca in enumerate(cercas):
        vel_str = velocidades_custom[i] if velocidades_custom else extrair_velocidade(cerca['nome'])
        try:
            vel_num = int(vel_str)
        except:
            vel_num = 50
            
        poly = ShapelyPolygon(cercas[i]['coordenadas']) if len(cerca['coordenadas']) >= 3 else None
        poligonos.append({'idx': i, 'nome': cerca['nome'], 'poly': poly, 'vel': vel_num})
    
    adj = {i: set() for i in range(n)}
    pares_conflito = []
    
    for i in range(n):
        for j in range(i + 1, n):
            p1, p2 = poligonos[i], poligonos[j]
            if p1['poly'] and p2['poly'] and p1['poly'].intersects(p2['poly']):
                adj[i].add(j)
                adj[j].add(i)
                pares_conflito.append((i, j))
                
    visitados = set()
    for i in range(n):
        if i not in visitados and adj[i]:
            grupo = []
            fila = [i]
            visitados.add(i)
            while fila:
                atual = fila.pop(0)
                grupo.append(atual)
                for viz in adj[atual]:
                    if viz not in visitados:
                        visitados.add(viz)
                        fila.append(viz)
            
            vels_unicas = sorted(list(set(poligonos[idx]['vel'] for idx in grupo)), reverse=True)
            if len(vels_unicas) > 1:
                passo = max(1, 7 // (len(vels_unicas) - 1))
                for idx in grupo:
                    rank = vels_unicas.index(poligonos[idx]['vel'])
                    prio_calculada = max(0, 8 - (rank * passo))
                    prioridades[idx] = f"{prio_calculada:02d}"
                    
    for i, j in pares_conflito:
        p1, p2 = poligonos[i], poligonos[j]
        if p1['vel'] != p2['vel']:
            menor = p1 if p1['vel'] < p2['vel'] else p2
            maior = p2 if p1['vel'] < p2['vel'] else p1
            prio_menor = prioridades[menor['idx']]
            prio_maior = prioridades[maior['idx']]
            alertas.append(
                f"⚠️ **Conflito Resolvido:** '{menor['nome']}' ({menor['vel']}km/h) sobrepõe "
                f"'{maior['nome']}' ({maior['vel']}km/h). Maior prioridade na menor velocidade "
                f"(**Prio {prio_menor}** vs **Prio {prio_maior}**)."
            )
            
    return alertas, prioridades

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
            alertas_iniciais, prioridades_auto = auditar_e_definir_prioridades(cercas)
            
            dados_tabela = []
            indice_global = 160
            for idx, cerca in enumerate(cercas):
                dados_tabela.append({
                    "Índice Inicial": f"VSRN{indice_global:03d}",
                    "Nome da Cerca": cerca['nome'],
                    "Velocidade Limite": extrair_velocidade(cerca['nome']),
                    "Prioridade": prioridades_auto[idx],
                    "Vértices": len(cerca['coordenadas'])
                })
                indice_global += len(cerca['coordenadas']) + 1 
            
            col_mapa, col_dados = st.columns([1.2, 1])
            
            with col_dados:
                st.subheader("Edição de Metadados")
                st.markdown("Zonas sobrepostas recebem **maior prioridade automaticamente** na **menor velocidade**.")
                
                df_export = pd.DataFrame(dados_tabela)
                df_editado = st.data_editor(df_export, use_container_width=True, hide_index=True)
                
                velocidades_atuais = [str(row["Velocidade Limite"]) for _, row in df_editado.iterrows()]
                alertas_atuais, prioridades_recalculadas = auditar_e_definir_prioridades(cercas, velocidades_atuais)
                
                scripts_finais = []
                primeiro_ponto = 160
                indice_recalculo = primeiro_ponto
                ultimo_ponto = primeiro_ponto
                
                for index, row in df_editado.iterrows():
                    cerca_atual = cercas[index]
                    velocidade_formatada = str(row["Velocidade Limite"])
                    
                    prio_tabela = str(row["Prioridade"]).zfill(2)
                    if prio_tabela != prioridades_auto[index]:
                        prioridade_formatada = prio_tabela
                    else:
                        prioridade_formatada = prioridades_recalculadas[index]
                    
                    script = gerar_script_virloc(
                        cerca_atual['nome'], 
                        cerca_atual['coordenadas'], 
                        indice_recalculo, 
                        prioridade_formatada, 
                        velocidade_formatada
                    )
                    scripts_finais.append(f"// {cerca_atual['nome']}\n{script}")
                    
                    ultimo_ponto = indice_recalculo + len(cerca_atual['coordenadas']) - 1
                    indice_recalculo += len(cerca_atual['coordenadas']) + 1
                
                scripts_finais.append(gerar_rodape_regiao(primeiro_ponto, ultimo_ponto))
                texto_final = "\n\n".join(scripts_finais)
                
                c1, c2 = st.columns(2)
                c1.download_button("📥 Baixar Script (.txt)", texto_final, file_name="cercas_virloc.txt")
                c2.download_button("📊 Baixar Base (.csv)", df_editado.to_csv(index=False), file_name="banco_cercas.csv", mime="text/csv")
                
                with st.expander("Ver Script Completo"):
                    st.code(texto_final, language="text")

            with col_mapa:
                # Sistema de Foco no Mapa
                lista_nomes_cercas = [c['nome'] for c in cercas]
                cerca_foco = st.selectbox("🎯 Centralizar mapa na cerca:", ["Visão Geral de Todas as Cercas"] + lista_nomes_cercas)
                
                if cerca_foco == "Visão Geral de Todas as Cercas":
                    lat_foco, lon_foco = cercas[0]['coordenadas'][0][1], cercas[0]['coordenadas'][0][0]
                    zoom_foco = 13
                else:
                    idx_foco = lista_nomes_cercas.index(cerca_foco)
                    lat_foco, lon_foco = calcular_centroide(cercas[idx_foco]['coordenadas'])
                    zoom_foco = 16 # Zoom aproximado para focar na cerca

                st.subheader("Validação Geométrica")
                renderizar_legenda()
                
                mapa_auditoria = folium.Map(location=[lat_foco, lon_foco], zoom_start=zoom_foco)
                folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Google Híbrido', max_zoom=20).add_to(mapa_auditoria)
                folium.LayerControl().add_to(mapa_auditoria)
                
                # Sistema de Renderização por Área (As maiores por baixo, as menores por cima)
                cercas_ordenadas = []
                for index, row in df_editado.iterrows():
                    cerca_atual = cercas[index]
                    area_poligono = ShapelyPolygon(cerca_atual['coordenadas']).area if len(cerca_atual['coordenadas']) >= 3 else 0
                    cercas_ordenadas.append((area_poligono, index, row, cerca_atual))
                
                # Ordena a lista de forma decrescente (Maior área -> Menor área)
                cercas_ordenadas.sort(key=lambda x: x[0], reverse=True)
                
                for area, index, row, cerca_atual in cercas_ordenadas:
                    pontos_folium = [(lat, lon) for lon, lat in cerca_atual['coordenadas']]
                    
                    prio_tabela = str(row["Prioridade"]).zfill(2)
                    prio_final = prio_tabela if prio_tabela != prioridades_auto[index] else prioridades_recalculadas[index]
                    cor_poligono = obter_cor_prioridade(prio_final)
                    
                    folium.Polygon(
                        pontos_folium, 
                        tooltip=f"{cerca_atual['nome']} (Vel: {row['Velocidade Limite']}km/h | Prio: {prio_final})", 
                        color=cor_poligono, 
                        fill_color=cor_poligono, 
                        fill_opacity=0.5
                    ).add_to(mapa_auditoria)
                    
                folium_static(mapa_auditoria)
                
            if alertas_atuais:
                with st.expander("🚨 Alertas de Conflito Espacial e Prioridades", expanded=True):
                    for alerta in alertas_atuais:
                        st.markdown(alerta)
    else:
        st.session_state.cercas_kml = [] 

# --- ABA 2: Ferramentas Avançadas de Desenho ---
with aba2:
    st.markdown("Busque a região de operação e desenhe polígonos livremente.")
    renderizar_legenda()
    
    col_busca, col_toggle = st.columns([2, 1])
    
    with col_busca:
        cidade_busca = st.text_input("🔍 Pesquisar Região", "")
        
    with col_toggle:
        st.write("") 
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
    
    col_mapa2, col_script2 = st.columns([1.2, 1])
    
    with col_mapa2:
        mapa_desenho = folium.Map(location=[lat_inicial, lon_inicial], zoom_start=13)
        folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Google Híbrido', max_zoom=20).add_to(mapa_desenho)
        folium.LayerControl().add_to(mapa_desenho)
        
        if st.session_state.cercas_kml and mostrar_fantasma:
            st.info("Usando referências do KML como molde para desenho.")
            
            # Aplica a mesma ordenação por área para as camadas fantasmas
            fantasmas_ordenadas = []
            for cerca in st.session_state.cercas_kml:
                area = ShapelyPolygon(cerca['coordenadas']).area if len(cerca['coordenadas']) >= 3 else 0
                fantasmas_ordenadas.append((area, cerca))
            
            fantasmas_ordenadas.sort(key=lambda x: x[0], reverse=True)
            
            for area, cerca in fantasmas_ordenadas:
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
        
        dados_mapa = st_folium(mapa_desenho, width=700, height=600)
        
    with col_script2:
        st.subheader("Roteiro Interativo")
        
        if dados_mapa and dados_mapa.get("all_drawings"):
            poligonos_desenhados = [
                d["geometry"]["coordinates"][0]
                for d in dados_mapa["all_drawings"]
                if d["geometry"]["type"] == "Polygon"
            ]
            
            if poligonos_desenhados:
                nomes_desenhados = []
                for i in range(len(poligonos_desenhados)):
                    nome_cerca = st.text_input(f"Nome da Cerca {i+1}", f"Cerca 50 km - Área {i+1}", key=f"nome_cerca_{i}")
                    nomes_desenhados.append(nome_cerca)
                
                cercas_temp = [{'nome': nomes_desenhados[i], 'coordenadas': poligonos_desenhados[i]} for i in range(len(poligonos_desenhados))]
                alertas_desenho, prios_desenho = auditar_e_definir_prioridades(cercas_temp)
                
                if alertas_desenho:
                    for alerta in alertas_desenho:
                        st.markdown(alerta)
                
                scripts_desenhados = []
                primeiro_ponto_des = 160
                indice_desenho = primeiro_ponto_des
                ultimo_ponto_des = primeiro_ponto_des
                
                for i, coords in enumerate(poligonos_desenhados):
                    script = gerar_script_virloc(nomes_desenhados[i], coords, indice_desenho, prios_desenho[i])
                    scripts_desenhados.append(f"// {nomes_desenhados[i]} (Prioridade Aplicada: {prios_desenho[i]})\n{script}")
                    
                    ultimo_ponto_des = indice_desenho + len(coords) - 1
                    indice_desenho += len(coords) + 1
                
                scripts_desenhados.append(gerar_rodape_regiao(primeiro_ponto_des, ultimo_ponto_des))
                texto_desenho = "\n\n".join(scripts_desenhados)
                
                st.download_button("📥 Baixar Script Desenhado", texto_desenho, file_name="novas_cercas_virloc.txt")
                st.code(texto_desenho, language="text")
        else:
            st.info("Aguardando interação no mapa. Use a ferramenta de polígono à esquerda para começar.")
            