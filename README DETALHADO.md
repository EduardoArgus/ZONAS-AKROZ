---

**README.md (Versão Detalhada)**

```markdown
# 📍 Automação e Inteligência de Cercas VIRLOC - Documentação Técnica

Este repositório contém o sistema completo de automação logística para rastreadores VIRLOC. O dashboard foi construído com Streamlit e elimina o trabalho manual de formatação de coordenadas, prevenindo falhas de roteirização através de cálculos de geometria espacial.

## 🏗️ Arquitetura e Bibliotecas

*   **Streamlit & Streamlit-Folium:** Estrutura da interface web e ponte bidirecional entre o mapa e os dados.
*   **Shapely:** Motor matemático em background para cálculos de intersecção e sobreposição de polígonos.
*   **Folium & Leaflet.Draw:** Renderização do mapa híbrido (Google Satélite) e ferramentas de edição de vértices.
*   **Geopy:** Motor de busca (geocodificação) para centralizar o mapa rapidamente em qualquer cidade ou região.
*   **Pandas:** Estruturação dos metadados para exportação de bases de dados (CSV).
*   **XML (Nativo):** Varredura de namespaces para extração direta das tags `<coordinates>` de arquivos KML.

## ⚙️ Fluxo de Trabalho (Funcionalidades Detalhadas)

### Aba 1: Auditoria Analítica (Upload de KML)
1. **Upload e Validação:** O usuário faz o upload de um KML bruto. O sistema extrai e converte todas as coordenadas geométricas para o padrão posicional VIRLOC (5 casas decimais, sem vírgula, invertendo Latitude/Longitude).
2. **Motor de Conflitos:** A biblioteca Shapely calcula a área de todos os polígonos. Se a Cerca A colidir com a Cerca B e ambas possuírem velocidades diferentes, o sistema dispara um alerta crítico de prioridade.
3. **Edição e Exportação:** Uma tabela interativa (DataFrame) permite a edição da Velocidade e Prioridade de cada cerca importada. O script `.txt` e o mapa reagem instantaneamente (alterando a cor do polígono na tela) e ficam prontos para download.

### Aba 2: Desenho Avançado (Roteiro Interativo)
1. **Ferramenta de Criação:** Um mapa híbrido em branco focado em uma região pesquisada pelo usuário. Permite o desenho livre de novos polígonos.
2. **Inputs Dinâmicos:** A cada nova área desenhada, o sistema gera campos exclusivos de "Nome" e "Prioridade" e renderiza o script VIRLOC na hora.
3. **Camadas Fantasmas (Ghost Layers):** Se um KML for carregado na Aba 1, ele aparecerá na Aba 2 como um molde amarelo e pontilhado. O analista pode desenhar uma versão corrigida da cerca por cima do traçado antigo usando o satélite como referência.
4. **Edição de Vértices:** O botão "Edit layers" permite arrastar os pontos das cercas recém-desenhadas. Ao salvar a edição no mapa, o código atualiza os índices (`VSRN`) e coordenadas de forma automática.

## 🚢 Recomendações de Hospedagem (Deployment)

Para disponibilizar a ferramenta para a equipe operacional de telemetria, recomenda-se:
*   **Docker:** Criar um `Dockerfile` expondo a porta `8501`.
*   **Servidor Local (VM):** Executar a aplicação via terminal e utilizar um proxy reverso (Nginx/IIS) para fornecer um domínio interno corporativo (ex: `roteirizador.intranet`).