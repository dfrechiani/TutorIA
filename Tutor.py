import os
import streamlit as st
import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Tuple
import plotly.graph_objects as go
from collections import Counter
import openai
from elevenlabs import generate, set_api_key
import re

# No início do arquivo, após as importações
def initialize_openai_client():
    try:
        # Configurar cliente OpenAI usando a chave correta
        openai.api_key = st.secrets["openai"]["api_key"]
        # Verificar se a chave começa com "sk-" para garantir formato correto
        if not openai.api_key.startswith("sk-"):
            raise ValueError("Formato de API key inválido")
            
        return openai.Client(api_key=openai.api_key)
    except Exception as e:
        logger.error(f"Erro ao inicializar cliente OpenAI: {e}")
        st.error("Erro ao inicializar conexão com OpenAI. Verifique a chave da API.")
        return None
# Configuração inicial do Streamlit
st.set_page_config(
    page_title="Sistema de Análise de Redação ENEM",
    page_icon="📝",
    layout="wide"
)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicialização dos clientes
try:
    # OpenAI (GPT-4)
    openai.api_key = st.secrets["openai"]["api_key"]
    
    # ElevenLabs
    set_api_key(st.secrets["elevenlabs"]["api_key"])
except Exception as e:
    logger.error(f"Erro na inicialização dos clientes: {e}")
    st.error("Erro ao inicializar conexões. Por favor, tente novamente mais tarde.")

# Constantes Globais
COMPETENCIES = {
    "competency1": "Domínio da Norma Culta",
    "competency2": "Compreensão do Tema",
    "competency3": "Seleção e Organização das Informações",
    "competency4": "Conhecimento dos Mecanismos Linguísticos",
    "competency5": "Proposta de Intervenção"
}

COMPETENCY_COLORS = {
    "competency1": "#FF6B6B",
    "competency2": "#4ECDC4",
    "competency3": "#45B7D1",
    "competency4": "#FFA07A",
    "competency5": "#98D8C8"
}

# Modelos fine-tuned para cada competência
MODELOS_COMPETENCIAS = {
    "competency1": "ft:gpt-4o-2024-08-06:personal:competencia-1:AHDQQucG",
    "competency2": "ft:gpt-4o-2024-08-06:personal:competencia-2:AHDT84HO",
    "competency3": "ft:gpt-4o-2024-08-06:personal:competencia-3:AHDUfZRb",
    "competency4": "ft:gpt-4o-2024-08-06:personal:competencia-4:AHDXewU3",
    "competency5": "ft:gpt-4o-2024-08-06:personal:competencia-5:AHGVPnJG"
}


def pagina_envio_redacao():
    """Página de envio de redação com processamento real"""
    st.title("Envio de Redação ENEM")

    nome_aluno = st.text_input("Nome do aluno:")
    tema_redacao = st.text_input("Tema da redação:")

    if 'texto_redacao' not in st.session_state:
        st.session_state.texto_redacao = ""

    texto_redacao = st.text_area(
        "Digite sua redação aqui:", 
        value=st.session_state.texto_redacao,
        height=400
    )

    # Upload de arquivo txt
    uploaded_file = st.file_uploader("Ou faça upload de um arquivo .txt", type=['txt'])
    if uploaded_file:
        texto_redacao = uploaded_file.getvalue().decode("utf-8")
        st.session_state.texto_redacao = texto_redacao

    if tema_redacao and texto_redacao:
        if st.button("Processar Redação"):
            with st.spinner("Analisando redação..."):
                try:
                    # Validar entrada
                    valido, msg = validar_redacao(texto_redacao, tema_redacao)
                    if not valido:
                        st.error(msg)
                        return

                    # Processar redação usando as APIs
                    resultados = processar_redacao_completa(texto_redacao, tema_redacao)
                    
                    # Salvar resultados no session_state
                    st.session_state.update({
                        'resultados': resultados,
                        'nome_aluno': nome_aluno,
                        'tema_redacao': tema_redacao,
                        'redacao_texto': texto_redacao
                    })

                    st.success("Redação processada com sucesso!")
                    
                    # Exibir resumo das notas
                    st.write("Notas por competência:")
                    for comp, nota in resultados['notas'].items():
                        st.write(f"{COMPETENCIES[comp]}: {nota}")

                except Exception as e:
                    st.error("Erro ao processar a redação.")
                    logger.error(f"Erro ao processar redação: {str(e)}", exc_info=True)
    else:
        st.button("Processar Redação", disabled=True)
        st.warning("Por favor, insira o tema e o texto da redação antes de processar.")


def processar_redacao_completa(redacao_texto: str, tema_redacao: str) -> Dict[str, Any]:
    """
    Processa a redação completa usando as APIs para análise real.
    """
    logger.info("Iniciando processamento da redação")

    resultados = {
        'analises_detalhadas': {},
        'notas': {},
        'erros_especificos': {},
        'justificativas': {},
        'texto_original': redacao_texto
    }
    
    # Processar cada competência
    for comp, modelo in MODELOS_COMPETENCIAS.items():
        try:
            # Realizar análise da competência usando o modelo específico
            if comp == "competency1":
                resultado_analise = analisar_competency1(redacao_texto, tema_redacao)
            elif comp == "competency2":
                resultado_analise = analisar_competency2(redacao_texto, tema_redacao)
            elif comp == "competency3":
                resultado_analise = analisar_competency3(redacao_texto, tema_redacao)
            elif comp == "competency4":
                resultado_analise = analisar_competency4(redacao_texto, tema_redacao)
            else:  # competency5
                resultado_analise = analisar_competency5(redacao_texto, tema_redacao)
            
            # Processar erros identificados
            erros_revisados = resultado_analise.get('erros', [])
            
            # Atribuir nota baseado na análise completa
            if comp == "competency1":
                resultado_nota = atribuir_nota_competency1(resultado_analise['analise'], erros_revisados)
            elif comp == "competency2":
                resultado_nota = atribuir_nota_competency2(resultado_analise['analise'], erros_revisados)
            elif comp == "competency3":
                resultado_nota = atribuir_nota_competency3(resultado_analise['analise'], erros_revisados)
            elif comp == "competency4":
                resultado_nota = atribuir_nota_competency4(resultado_analise['analise'], erros_revisados)
            else:  # competency5
                resultado_nota = atribuir_nota_competency5(resultado_analise['analise'], erros_revisados)
            
            # Preencher resultados
            resultados['analises_detalhadas'][comp] = resultado_analise['analise']
            resultados['notas'][comp] = resultado_nota['nota']
            resultados['justificativas'][comp] = resultado_nota['justificativa']
            resultados['erros_especificos'][comp] = erros_revisados

        except Exception as e:
            logger.error(f"Erro ao processar competência {comp}: {str(e)}")
            resultados['analises_detalhadas'][comp] = "Erro na análise"
            resultados['notas'][comp] = 0
            resultados['justificativas'][comp] = "Não foi possível realizar a análise"
            resultados['erros_especificos'][comp] = []

    return resultados

def pagina_resultado_analise():
    st.title("Resultado da Análise")
    
    if 'resultados' not in st.session_state:
        st.warning("Nenhuma análise disponível")
        return
        
    # Exibir gráfico radar
    criar_grafico_radar(st.session_state.resultados['notas'])
    
    # Exibir análises detalhadas
    for comp, analise in st.session_state.resultados['analises_detalhadas'].items():
        with st.expander(f"{COMPETENCIES[comp]} - Nota: {st.session_state.resultados['notas'][comp]}"):
            st.write(analise)
            
            if comp in st.session_state.resultados['erros_especificos']:
                st.write("**Erros identificados:**")
                for erro in st.session_state.resultados['erros_especificos'][comp]:
                    st.write(formatar_erro(erro))
    
    # Botão para iniciar tutoria
    if st.button("Iniciar Tutoria Personalizada"):
        st.session_state.page = 'tutoria'
        st.rerun()

def validar_redacao(texto: str, tema: str) -> Tuple[bool, str]:
    """
    Valida o texto da redação e o tema.
    
    Args:
        texto: Texto da redação
        tema: Tema da redação
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    if not texto or not texto.strip():
        return False, "O texto da redação não pode estar vazio."
        
    if not tema or not tema.strip():
        return False, "O tema da redação não pode estar vazio."
        
    palavras = len(texto.split())
    if palavras < 50:
        return False, f"Texto muito curto ({palavras} palavras). Mínimo recomendado: 400 palavras."
        
    if palavras > 3000:
        return False, f"Texto muito longo ({palavras} palavras). Máximo recomendado: 3000 palavras."
        
    return True, ""

def extrair_erros_do_resultado(resultado: str) -> List[Dict[str, str]]:
    """
    Extrai erros do texto de resultado da análise.
    
    Args:
        resultado: String contendo o resultado da análise
        
    Returns:
        Lista de dicionários contendo os erros identificados
    """
    erros = []
    padrao_erro = re.compile(r'ERRO\n(.*?)\nFIM_ERRO', re.DOTALL)
    matches = padrao_erro.findall(resultado)
    
    for match in matches:
        erro = {}
        for linha in match.split('\n'):
            if ':' in linha:
                chave, valor = linha.split(':', 1)
                chave = chave.strip().lower()
                valor = valor.strip()
                if chave == 'trecho':
                    valor = valor.strip('"')
                erro[chave] = valor
        if 'descrição' in erro and 'trecho' in erro:
            erros.append(erro)
    
    return erros

# Continuação da função analisar_competency1
    erros_por_criterio = {}
    for criterio, prompt in criterios.items():
        prompt_formatado = prompt.format(redacao_texto=redacao_texto)
        resposta = client.messages.create(
            model=MODELO_COMP1,
            messages=[{"role": "user", "content": prompt_formatado}],
            temperature=0.3
        )
        erros_por_criterio[criterio] = extrair_erros_do_resultado(resposta.content)
    
    # Reunir todos os erros
    todos_erros = []
    for erros in erros_por_criterio.values():
        todos_erros.extend(erros)
   
    # Separar erros reais de sugestões estilísticas
    erros_reais = []
    sugestoes_estilo = []
    
    palavras_chave_sugestao = [
        "pode ser melhorada",
        "poderia ser",
        "considerar",
        "sugerimos",
        "recomendamos",
        "ficaria melhor",
        "seria preferível",
        "opcionalmente",
        "para aprimorar",
        "para enriquecer",
        "estilo",
        "clareza",
        "mais elegante",
        "sugestão de melhoria",
        "alternativa",
        "opcional"
    ]
    
    for erro in todos_erros:
        eh_sugestao = False
        explicacao = erro.get('explicação', '').lower()
        sugestao = erro.get('sugestão', '').lower()
        
        # Verificar se é uma sugestão
        if any(palavra in explicacao or palavra in sugestao for palavra in palavras_chave_sugestao):
            sugestoes_estilo.append(erro)
        else:
            # Validação adicional para erros de crase
            if "crase" in erro.get('descrição', '').lower():
                explicacao = erro.get('explicação', '').lower()
                if (any(termo in explicacao for termo in ['artigo definido', 'sentido definido', 'locução']) and 
                    any(termo in explicacao for termo in ['regência', 'preposição', 'artigo feminino'])):
                    erros_reais.append(erro)
            else:
                erros_reais.append(erro)

    # Revisão final dos erros reais
    erros_revisados = revisar_erros_competency1(erros_reais, redacao_texto)
    
    # Gerar análise final
    prompt_analise = f"""
    Com base nos seguintes ERROS CONFIRMADOS no texto (excluindo sugestões de melhoria estilística),
    gere uma análise detalhada da Competência 1 (Domínio da Norma Culta):
    
    Total de erros confirmados: {len(erros_revisados)}
    
    Detalhamento dos erros confirmados:
    {json.dumps(erros_revisados, indent=2)}
    
    Observação: Analisar apenas os erros reais que prejudicam a nota, ignorando sugestões de melhoria.
    
    Forneça uma análise que:
    1. Avalie o domínio geral da norma culta considerando apenas erros confirmados
    2. Destaque os tipos de erros mais frequentes e sua gravidade
    3. Analise o impacto dos erros na compreensão do texto
    4. Avalie a consistência no uso da norma culta
    5. Forneça uma visão geral da qualidade técnica do texto
    
    Formato da resposta:
    Análise Geral: [Sua análise aqui]
    Erros Principais: [Lista dos erros mais relevantes]
    Impacto na Compreensão: [Análise do impacto dos erros]
    Consistência: [Avaliação da consistência no uso da norma]
    Conclusão: [Visão geral da qualidade técnica]
    """
    
    resposta_analise = client.messages.create(
        model=MODELO_COMP1,
        messages=[{"role": "user", "content": prompt_analise}],
        temperature=0.3
    )
    
    return {
        'analise': resposta_analise.content,
        'erros': erros_revisados,
        'sugestoes_estilo': sugestoes_estilo,
        'total_erros': len(erros_revisados)
    }

def analisar_competency1(redacao_texto: str, tema_redacao: str) -> Dict[str, Any]:
    """Análise da Competência 1 usando o modelo fine-tuned"""
    try:
        if 'openai_client' not in st.session_state:
            raise ValueError("Cliente OpenAI não inicializado")
            
        client = st.session_state.openai_client
        
        prompt = f"""
        Analise o domínio da norma culta na seguinte redação:
        
        Tema: {tema_redacao}
        
        Texto:
        {redacao_texto}
        
        Forneça uma análise detalhada considerando:
        1. Uso correto da norma culta
        2. Desvios gramaticais
        3. Adequação da linguagem
        4. Clareza e precisão
        
        Para cada erro identificado, use o formato:
        ERRO
        Trecho: "[trecho exato do texto]"
        Explicação: [explicação detalhada]
        Sugestão: [sugestão de correção]
        FIM_ERRO
        """
        
        response = client.chat.completions.create(
            model="ft:gpt-4-0125-preview:personal::8TYkJb4B",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        analise = response.choices[0].message.content
        erros = extrair_erros_do_resultado(analise)
        
        return {
            'analise': analise,
            'erros': erros
        }
    except Exception as e:
        logger.error(f"Erro na análise da Competência 1: {str(e)}")
        raise

def analisar_competency2(redacao_texto: str, tema_redacao: str) -> Dict[str, Any]:
    """Análise da Competência 2 usando o modelo fine-tuned"""
    try:
        if 'openai_client' not in st.session_state:
            raise ValueError("Cliente OpenAI não inicializado")
            
        client = st.session_state.openai_client
        
        prompt = f"""
        Analise a compreensão do tema na seguinte redação:
        
        Tema: {tema_redacao}
        
        Texto:
        {redacao_texto}
        
        Forneça uma análise detalhada considerando:
        1. Compreensão da proposta de redação e do tema
        2. Presença das palavras-chave do tema em cada parágrafo
        3. Desenvolvimento do tema de forma adequada
        4. Uso e pertinência do repertório sociocultural
        5. Clareza no ponto de vista defendido
        6. Vínculo entre o repertório e a discussão proposta
        
        Para cada problema identificado, use o formato:
        ERRO
        Trecho: "[trecho exato do texto]"
        Explicação: [explicação detalhada]
        Sugestão: [sugestão de melhoria]
        FIM_ERRO
        """
        
        response = client.chat.completions.create(
            model="ft:gpt-4-0125-preview:personal::8TYmNb5C",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        analise = response.choices[0].message.content
        erros = extrair_erros_do_resultado(analise)
        
        return {
            'analise': analise,
            'erros': erros
        }
    except Exception as e:
        logger.error(f"Erro na análise da Competência 2: {str(e)}")
        raise

def analisar_competency3(redacao_texto: str, tema_redacao: str) -> Dict[str, Any]:
    """Análise da Competência 3 usando o modelo fine-tuned"""
    try:
        if 'openai_client' not in st.session_state:
            raise ValueError("Cliente OpenAI não inicializado")
            
        client = st.session_state.openai_client
        
        prompt = f"""
        Analise a seleção e organização das informações na seguinte redação:
        
        Tema: {tema_redacao}
        
        Texto:
        {redacao_texto}
        
        Forneça uma análise detalhada considerando:
        1. Progressão textual (desenvolvimento das ideias)
        2. Organização dos parágrafos e períodos
        3. Encadeamento de ideias entre parágrafos
        4. Uso de argumentos e contra-argumentos
        5. Coerência na apresentação das informações
        6. Autoria no desenvolvimento do texto
        
        Para cada problema identificado, use o formato:
        ERRO
        Trecho: "[trecho exato do texto]"
        Explicação: [explicação detalhada]
        Sugestão: [sugestão de melhoria]
        FIM_ERRO
        """
        
        response = client.chat.completions.create(
            model="ft:gpt-4-0125-preview:personal::8TYpKc6D",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        analise = response.choices[0].message.content
        erros = extrair_erros_do_resultado(analise)
        
        return {
            'analise': analise,
            'erros': erros
        }
    except Exception as e:
        logger.error(f"Erro na análise da Competência 3: {str(e)}")
        raise

def analisar_competency4(redacao_texto: str, tema_redacao: str) -> Dict[str, Any]:
    """Análise da Competência 4 usando o modelo fine-tuned"""
    try:
        if 'openai_client' not in st.session_state:
            raise ValueError("Cliente OpenAI não inicializado")
            
        client = st.session_state.openai_client
        
        prompt = f"""
        Analise os mecanismos linguísticos na seguinte redação:
        
        Tema: {tema_redacao}
        
        Texto:
        {redacao_texto}
        
        Forneça uma análise detalhada considerando:
        1. Uso de conectivos entre parágrafos e períodos
        2. Articulação entre as partes do texto
        3. Recursos de coesão textual
        4. Uso de referenciação (pronomes, sinônimos, etc.)
        5. Estruturação dos períodos
        6. Transições entre ideias
        
        Para cada problema identificado, use o formato:
        ERRO
        Trecho: "[trecho exato do texto]"
        Explicação: [explicação detalhada]
        Sugestão: [sugestão de melhoria]
        FIM_ERRO
        """
        
        response = client.chat.completions.create(
            model="ft:gpt-4-0125-preview:personal::8TYrLd7E",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        analise = response.choices[0].message.content
        erros = extrair_erros_do_resultado(analise)
        
        return {
            'analise': analise,
            'erros': erros
        }
    except Exception as e:
        logger.error(f"Erro na análise da Competência 4: {str(e)}")
        raise

def analisar_competency5(redacao_texto: str, tema_redacao: str) -> Dict[str, Any]:
    """Análise da Competência 5 usando o modelo fine-tuned"""
    try:
        if 'openai_client' not in st.session_state:
            raise ValueError("Cliente OpenAI não inicializado")
            
        client = st.session_state.openai_client
        
        prompt = f"""
        Analise a proposta de intervenção na seguinte redação:
        
        Tema: {tema_redacao}
        
        Texto:
        {redacao_texto}
        
        Forneça uma análise detalhada considerando:
        1. Presença dos elementos obrigatórios:
           - Agente(s) que executará(ão) a ação
           - Ação(ões) para resolver o problema
           - Modo/meio de execução da ação
           - Detalhamento da execução e/ou dos efeitos esperados
           - Finalidade/objetivo da proposta
        2. Detalhamento e articulação da proposta
        3. Viabilidade da proposta
        4. Respeito aos direitos humanos
        5. Relação com o problema discutido
        6. Nível de detalhamento das ações sugeridas
        
        Para cada problema identificado, use o formato:
        ERRO
        Trecho: "[trecho exato do texto]"
        Explicação: [explicação detalhada]
        Sugestão: [sugestão de melhoria]
        FIM_ERRO
        """
        
        response = client.chat.completions.create(
            model="ft:gpt-4-0125-preview:personal::8TYtMe8F",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        analise = response.choices[0].message.content
        erros = extrair_erros_do_resultado(analise)
        
        return {
            'analise': analise,
            'erros': erros
        }
    except Exception as e:
        logger.error(f"Erro na análise da Competência 5: {str(e)}")
        raise

def revisar_erros_competency1(erros_identificados: List[Dict], redacao_texto: str) -> List[Dict]:
    """
    Revisa os erros identificados na Competência 1 usando análise contextual aprofundada.
    
    Args:
        erros_identificados: Lista de erros identificados inicialmente
        redacao_texto: Texto completo da redação para análise contextual
        
    Returns:
        Lista de erros validados e revisados
    """
    MODELO_REVISAO_COMP1 = "ft:gpt-4o-2024-08-06:personal:competencia-1:AHDQQucG"
    erros_revisados = []
    
    for erro in erros_identificados:
        # Extrair contexto expandido do erro
        trecho = erro.get('trecho', '')
        inicio_trecho = redacao_texto.find(trecho)
        if inicio_trecho != -1:
            # Pegar até 100 caracteres antes e depois para contexto
            inicio_contexto = max(0, inicio_trecho - 100)
            fim_contexto = min(len(redacao_texto), inicio_trecho + len(trecho) + 100)
            contexto_expandido = redacao_texto[inicio_contexto:fim_contexto]
        else:
            contexto_expandido = trecho
            
        prompt_revisao = f"""
        Revise rigorosamente o seguinte erro identificado na Competência 1 (Domínio da Norma Culta).
        
        Erro original:
        {json.dumps(erro, indent=2)}

        Contexto expandido do erro:
        "{contexto_expandido}"

        Texto completo para referência:
        {redacao_texto}

        Analise cuidadosamente:
        1. CONTEXTO SINTÁTICO:
           - Estrutura completa da frase
           - Função sintática das palavras
           - Relações de dependência
           
        2. REGRAS GRAMATICAIS:
           - Regras específicas aplicáveis
           - Exceções relevantes
           - Casos especiais
           
        3. IMPACTO NO SENTIDO:
           - Se o suposto erro realmente compromete a compreensão
           - Se há ambiguidade ou prejuízo ao sentido
           - Se é um desvio real ou variação aceitável
           
        4. ADEQUAÇÃO AO ENEM:
           - Critérios específicos da prova
           - Impacto na avaliação
           - Relevância do erro

        Para casos de crase, VERIFIQUE ESPECIFICAMENTE:
        - Se há realmente junção de preposição 'a' com artigo definido feminino
        - Se a palavra está sendo usada em sentido definido
        - Se há regência verbal/nominal exigindo preposição
        - O contexto completo da construção

        Formato da resposta:
        REVISAO
        Erro Confirmado: [Sim/Não]
        Análise Sintática: [Análise detalhada da estrutura sintática]
        Regra Aplicável: [Citação da regra gramatical específica]
        Explicação Revisada: [Explicação técnica detalhada]
        Sugestão Revisada: [Correção com justificativa]
        Considerações ENEM: [Relevância para a avaliação]
        FIM_REVISAO
        """
        
        try:
            resposta_revisao = client.messages.create(
                model=MODELO_REVISAO_COMP1,
                messages=[{"role": "user", "content": prompt_revisao}],
                temperature=0.2
            )
            
            revisao = extrair_revisao_do_resultado(resposta_revisao.content)
            
            # Validação rigorosa da revisão
            if (revisao['Erro Confirmado'] == 'Sim' and
                'Análise Sintática' in revisao and
                'Regra Aplicável' in revisao and
                len(revisao.get('Explicação Revisada', '')) > 50):
                
                erro_revisado = erro.copy()
                erro_revisado.update({
                    'análise_sintática': revisao['Análise Sintática'],
                    'regra_aplicável': revisao['Regra Aplicável'],
                    'explicação': revisao['Explicação Revisada'],
                    'sugestão': revisao['Sugestão Revisada'],
                    'considerações_enem': revisao['Considerações ENEM'],
                    'contexto_expandido': contexto_expandido
                })
                
                # Validação adicional para erros de crase
                if "crase" in erro.get('descrição', '').lower():
                    explicacao = revisao['Explicação Revisada'].lower()
                    analise = revisao['Análise Sintática'].lower()
                    
                    if ('artigo definido' in explicacao and
                        'preposição' in explicacao and
                        any(termo in analise for termo in ['função sintática', 'regência', 'complemento'])):
                        erros_revisados.append(erro_revisado)
                else:
                    erros_revisados.append(erro_revisado)
                    
        except Exception as e:
            logger.error(f"Erro ao revisar: {str(e)}")
            continue
    
    return erros_revisados

def revisar_erros_competency2(erros_identificados: List[Dict], redacao_texto: str) -> List[Dict]:
    """
    Revisa os erros identificados na Competência 2.
    
    Args:
        erros_identificados: Lista de erros identificados
        redacao_texto: Texto completo da redação
        
    Returns:
        Lista de erros validados
    """
    MODELO_REVISAO_COMP2 = "ft:gpt-4o-2024-08-06:personal:competencia-2:AHDT84HO"
    erros_revisados = []
    
    for erro in erros_identificados:
        prompt_revisao = f"""
        Revise o seguinte erro identificado na Competência 2 (Compreensão do Tema) 
        de acordo com os critérios específicos do ENEM:

        Erro original:
        {json.dumps(erro, indent=2)}

        Texto da redação:
        {redacao_texto}

        Determine:
        1. Se o erro está corretamente identificado
        2. Se a explicação e sugestão estão adequadas aos padrões do ENEM
        3. Se há considerações adicionais relevantes

        Formato da resposta:
        REVISAO
        Erro Confirmado: [Sim/Não]
        Explicação Revisada: [Nova explicação, se necessário]
        Sugestão Revisada: [Nova sugestão, se necessário]
        Considerações ENEM: [Observações específicas sobre o erro no contexto do ENEM]
        FIM_REVISAO
        """
        
        try:
            resposta_revisao = client.messages.create(
                model=MODELO_REVISAO_COMP2,
                messages=[{"role": "user", "content": prompt_revisao}],
                temperature=0.2
            )
            
            revisao = extrair_revisao_do_resultado(resposta_revisao.content)
            
            if revisao.get('Erro Confirmado') == 'Sim':
                erro_revisado = erro.copy()
                if 'Explicação Revisada' in revisao:
                    erro_revisado['explicação'] = revisao['Explicação Revisada']
                if 'Sugestão Revisada' in revisao:
                    erro_revisado['sugestão'] = revisao['Sugestão Revisada']
                erro_revisado['considerações_enem'] = revisao['Considerações ENEM']
                erros_revisados.append(erro_revisado)
                
        except Exception as e:
            logger.error(f"Erro ao revisar: {str(e)}")
            continue
    
    return erros_revisados

def revisar_erros_competency3(erros_identificados: List[Dict], redacao_texto: str) -> List[Dict]:
    """
    Revisa os erros identificados na Competência 3.
    
    Args:
        erros_identificados: Lista de erros identificados
        redacao_texto: Texto completo da redação
        
    Returns:
        Lista de erros validados
    """
    MODELO_REVISAO_COMP3 = "ft:gpt-4o-2024-08-06:personal:competencia-3:AHDUfZRb"
    erros_revisados = []
    
    for erro in erros_identificados:
        prompt_revisao = f"""
        Revise o seguinte erro identificado na Competência 3 (Seleção e Organização das Informações) 
        de acordo com os critérios específicos do ENEM:

        Erro original:
        {json.dumps(erro, indent=2)}

        Texto da redação:
        {redacao_texto}

        Determine:
        1. Se o erro está corretamente identificado
        2. Se a explicação e sugestão estão adequadas aos padrões do ENEM
        3. Se o erro impacta significativamente a organização e seleção de informações
        4. Se há considerações adicionais relevantes para a avaliação

        Formato da resposta:
        REVISAO
        Erro Confirmado: [Sim/Não]
        Explicação Revisada: [Nova explicação, se necessário]
        Sugestão Revisada: [Nova sugestão, se necessário]
        Considerações ENEM: [Observações específicas sobre o erro no contexto do ENEM]
        FIM_REVISAO
        """
        
        try:
            resposta_revisao = client.messages.create(
                model=MODELO_REVISAO_COMP3,
                messages=[{"role": "user", "content": prompt_revisao}],
                temperature=0.2
            )
            
            revisao = extrair_revisao_do_resultado(resposta_revisao.content)
            
            if revisao.get('Erro Confirmado') == 'Sim':
                erro_revisado = erro.copy()
                if 'Explicação Revisada' in revisao:
                    erro_revisado['explicação'] = revisao['Explicação Revisada']
                if 'Sugestão Revisada' in revisao:
                    erro_revisado['sugestão'] = revisao['Sugestão Revisada']
                erro_revisado['considerações_enem'] = revisao['Considerações ENEM']
                erros_revisados.append(erro_revisado)
                
        except Exception as e:
            logger.error(f"Erro ao revisar: {str(e)}")
            continue
    
    return erros_revisados

def revisar_erros_competency4(erros_identificados: List[Dict], redacao_texto: str) -> List[Dict]:
    """
    Revisa os erros identificados na Competência 4.
    
    Args:
        erros_identificados: Lista de erros identificados
        redacao_texto: Texto completo da redação
        
    Returns:
        Lista de erros validados
    """
    MODELO_REVISAO_COMP4 = "ft:gpt-4o-2024-08-06:personal:competencia-4:AHDXewU3"
    erros_revisados = []
    
    for erro in erros_identificados:
        prompt_revisao = f"""
        Revise o seguinte erro identificado na Competência 4 (Conhecimento dos Mecanismos Linguísticos) 
        de acordo com os critérios específicos do ENEM:

        Erro original:
        {json.dumps(erro, indent=2)}

        Texto da redação:
        {redacao_texto}

        Determine:
        1. Se o erro está corretamente identificado
        2. Se a explicação e sugestão estão adequadas aos padrões do ENEM
        3. Se o erro impacta significativamente a coesão textual
        4. Se há considerações adicionais relevantes para a avaliação

        Formato da resposta:
        REVISAO
        Erro Confirmado: [Sim/Não]
        Explicação Revisada: [Nova explicação, se necessário]
        Sugestão Revisada: [Nova sugestão, se necessário]
        Considerações ENEM: [Observações específicas sobre o erro no contexto do ENEM]
        FIM_REVISAO
        """
        
        try:
            resposta_revisao = client.messages.create(
                model=MODELO_REVISAO_COMP4,
                messages=[{"role": "user", "content": prompt_revisao}],
                temperature=0.2
            )
            
            revisao = extrair_revisao_do_resultado(resposta_revisao.content)
            
            if revisao.get('Erro Confirmado') == 'Sim':
                erro_revisado = erro.copy()
                if 'Explicação Revisada' in revisao:
                    erro_revisado['explicação'] = revisao['Explicação Revisada']
                if 'Sugestão Revisada' in revisao:
                    erro_revisado['sugestão'] = revisao['Sugestão Revisada']
                erro_revisado['considerações_enem'] = revisao['Considerações ENEM']
                erros_revisados.append(erro_revisado)
                
        except Exception as e:
            logger.error(f"Erro ao revisar: {str(e)}")
            continue
    
    return erros_revisados

def revisar_erros_competency5(erros_identificados: List[Dict], redacao_texto: str) -> List[Dict]:
    """
    Revisa os erros identificados na Competência 5.
    
    Args:
        erros_identificados: Lista de erros identificados
        redacao_texto: Texto completo da redação
        
    Returns:
        Lista de erros validados
    """
    MODELO_REVISAO_COMP5 = "ft:gpt-4o-2024-08-06:personal:competencia-5:AHGVPnJG"
    erros_revisados = []
    
    for erro in erros_identificados:
        prompt_revisao = f"""
        Revise o seguinte erro identificado na Competência 5 (Proposta de Intervenção) 
        de acordo com os critérios específicos do ENEM:

        Erro original:
        {json.dumps(erro, indent=2)}

        Texto da redação:
        {redacao_texto}

        Determine:
        1. Se o erro está corretamente identificado
        2. Se a explicação e sugestão estão adequadas aos padrões do ENEM
        3. Se o erro impacta significativamente a qualidade da proposta de intervenção
        4. Se há considerações adicionais relevantes para a avaliação

        Formato da resposta:
        REVISAO
        Erro Confirmado: [Sim/Não]
        Explicação Revisada: [Nova explicação, se necessário]
        Sugestão Revisada: [Nova sugestão, se necessário]
        Considerações ENEM: [Observações específicas sobre o erro no contexto do ENEM]
        FIM_REVISAO
        """
        
        try:
            resposta_revisao = client.messages.create(
                model=MODELO_REVISAO_COMP5,
                messages=[{"role": "user", "content": prompt_revisao}],
                temperature=0.2
            )
            
            revisao = extrair_revisao_do_resultado(resposta_revisao.content)
            
            if revisao.get('Erro Confirmado') == 'Sim':
                erro_revisado = erro.copy()
                if 'Explicação Revisada' in revisao:
                    erro_revisado['explicação'] = revisao['Explicação Revisada']
                if 'Sugestão Revisada' in revisao:
                    erro_revisado['sugestão'] = revisao['Sugestão Revisada']
                erro_revisado['considerações_enem'] = revisao['Considerações ENEM']
                erros_revisados.append(erro_revisado)
                
        except Exception as e:
            logger.error(f"Erro ao revisar: {str(e)}")
            continue
    
    return erros_revisados

def atribuir_nota_competency1(analise: str, erros: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Atribui nota à Competência 1 com base na análise detalhada e erros identificados.
    
    Args:
        analise: String contendo a análise detalhada do texto
        erros: Lista de dicionários contendo os erros identificados
        
    Returns:
        Dict contendo a nota atribuída (0-200) e sua justificativa
    """
    # Contar erros por categoria
    contagem_erros = {
        'sintaxe': 0,
        'ortografia': 0, 
        'concordancia': 0,
        'pontuacao': 0,
        'crase': 0,
        'registro': 0
    }
    
    for erro in erros:
        desc = erro.get('explicacao', '').lower()
        if 'sintax' in desc or 'estrutura' in desc:
            contagem_erros['sintaxe'] += 1
        if 'ortograf' in desc or 'accent' in desc or 'escrita' in desc:
            contagem_erros['ortografia'] += 1
        if 'concord' in desc or 'verbal' in desc or 'nominal' in desc:
            contagem_erros['concordancia'] += 1
        if 'pontu' in desc:
            contagem_erros['pontuacao'] += 1
        if 'crase' in desc:
            contagem_erros['crase'] += 1
        if 'coloquial' in desc or 'registro' in desc or 'informal' in desc:
            contagem_erros['registro'] += 1

    # Formatar erros para apresentação
    erros_formatados = ""
    for erro in erros:
        erros_formatados += f"""
        Erro encontrado:
        Trecho: "{erro.get('trecho', '')}"
        Explicação: {erro.get('explicacao', '')}"
        Sugestão: {erro.get('sugestao', '')}
        """

    # Determinar nota base pelos critérios objetivos
    total_erros = sum(contagem_erros.values())
    if (total_erros <= 3 and 
        contagem_erros['sintaxe'] <= 1 and
        contagem_erros['registro'] == 0 and
        contagem_erros['ortografia'] <= 1):
        nota_base = 200
    elif (total_erros <= 5 and 
          contagem_erros['sintaxe'] <= 2 and
          contagem_erros['registro'] <= 1):
        nota_base = 160
    elif (total_erros <= 8 and 
          contagem_erros['sintaxe'] <= 3):
        nota_base = 120
    elif total_erros <= 12:
        nota_base = 80
    elif total_erros <= 15:
        nota_base = 40
    else:
        nota_base = 0

    # Construir prompt para validação da nota
    prompt_nota = f"""
    Com base na seguinte análise da Competência 1 (Domínio da Norma Culta) e na contagem de erros identificados,
    confirme se a nota {nota_base} está adequada.
    
    ANÁLISE DETALHADA:
    {analise}
    
    CONTAGEM DE ERROS:
    - Erros de sintaxe/estrutura: {contagem_erros['sintaxe']}
    - Erros de ortografia/acentuação: {contagem_erros['ortografia']}
    - Erros de concordância: {contagem_erros['concordancia']}
    - Erros de pontuação: {contagem_erros['pontuacao']}
    - Erros de crase: {contagem_erros['crase']}
    - Desvios de registro formal: {contagem_erros['registro']}
    Total de erros: {total_erros}
    
    ERROS ESPECÍFICOS:
    {erros_formatados}
    """

    # Adicionar critérios de avaliação ao prompt
    prompt_nota += """
    Critérios para cada nota:
    
    200 pontos:
    - No máximo uma falha de estrutura sintática
    - No máximo dois desvios gramaticais
    - Nenhum uso de linguagem informal/coloquial
    - No máximo um erro ortográfico
    - Coerência e coesão impecáveis
    - Sem repetição de erros
    
    160 pontos:
    - Até três desvios gramaticais que não comprometem a compreensão
    - Poucos erros de pontuação/acentuação
    - No máximo três erros ortográficos
    - Bom domínio geral da norma culta
    
    120 pontos:
    - Até cinco desvios gramaticais
    - Domínio mediano da norma culta
    - Alguns problemas de coesão pontuais
    - Erros não sistemáticos
    
    80 pontos:
    - Estrutura sintática deficitária
    - Erros frequentes de concordância
    - Uso ocasional de registro inadequado
    - Muitos erros de pontuação/ortografia
    
    40 pontos:
    - Domínio precário da norma culta
    - Diversos desvios gramaticais frequentes
    - Problemas graves de coesão
    - Registro frequentemente inadequado
    
    0 pontos:
    - Desconhecimento total da norma culta
    - Erros graves e sistemáticos
    - Texto incompreensível
    
    Com base nesses critérios e na análise apresentada, forneça:
    1. Confirmação ou ajuste da nota base {nota_base}
    2. Justificativa detalhada relacionando os erros encontrados com os critérios
    
    Formato da resposta:
    Nota: [NOTA FINAL]
    Justificativa: [Justificativa detalhada da nota, explicando como os erros e acertos se relacionam com os critérios]
    """
    
    try:
        # Gerar resposta usando o modelo
        resposta_nota = client.messages.create(
            model="ft:gpt-4o-2024-08-06:personal:competencia-1:AHDQQucG",
            messages=[{"role": "user", "content": prompt_nota}],
            temperature=0.3
        )
        
        # Extrair nota e justificativa
        resultado = extrair_nota_e_justificativa(resposta_nota.content)
        
        # Validar se a nota está nos valores permitidos
        if resultado['nota'] not in [0, 40, 80, 120, 160, 200]:
            resultado['nota'] = nota_base
            resultado['justificativa'] += "\nNota ajustada para o valor válido mais próximo."
        
        # Validar discrepância com nota base
        if abs(resultado['nota'] - nota_base) > 40:
            resultado['nota'] = min(nota_base, resultado['nota'])
            resultado['justificativa'] += "\nNota ajustada devido à quantidade e gravidade dos erros identificados."
        
        return resultado
        
    except Exception as e:
        logger.error(f"Erro ao atribuir nota: {str(e)}")
        return {
            'nota': nota_base,
            'justificativa': "Erro ao gerar justificativa. Nota atribuída com base nos critérios objetivos."
        }

def atribuir_nota_competency2(analise: str, erros: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Atribui nota à Competência 2 com base na análise e erros identificados.
    
    Args:
        analise: String contendo a análise detalhada do texto
        erros: Lista de dicionários contendo os erros identificados
        
    Returns:
        Dict contendo a nota atribuída (0-200) e sua justificativa
    """
    prompt_nota = f"""
    Com base na seguinte análise da Competência 2 (Compreensão do Tema) do ENEM, atribua uma nota de 0 a 200 em intervalos de 40 pontos (0, 40, 80, 120, 160 ou 200).

    Análise:
    {analise}

    Erros identificados:
    {json.dumps(erros, indent=2)}

    Considere cuidadosamente os seguintes critérios para atribuir a nota:

    Nota 200:
    - Excelente domínio do tema proposto.
    - Citação das palavras principais do tema ou sinônimos em cada parágrafo.
    - Argumentação consistente com repertório sociocultural produtivo.
    - Uso de exemplos históricos, frases, músicas, textos, autores famosos, filósofos, estudos, artigos ou publicações como repertório.
    - Excelente domínio do texto dissertativo-argumentativo, incluindo proposição, argumentação e conclusão.
    - Não copia trechos dos textos motivadores e demonstra clareza no ponto de vista adotado.
    - Estabelece vínculo de ideias entre a referência ao repertório e a discussão proposta.
    - Cita a fonte do repertório (autor, obra, data de criação, etc.).
    - Inclui pelo menos um repertório no segundo e terceiro parágrafo.

    Nota 160:
    - Bom desenvolvimento do tema com argumentação consistente, mas sem repertório sociocultural tão produtivo.
    - Completa as 3 partes do texto dissertativo-argumentativo (nenhuma delas é embrionária).
    - Bom domínio do texto dissertativo-argumentativo, com proposição, argumentação e conclusão claras, mas sem aprofundamento.
    - Utiliza informações pertinentes, mas sem extrapolar significativamente sua justificativa.

    Nota 120:
    - Abordagem completa do tema, com as 3 partes do texto dissertativo-argumentativo (podendo 1 delas ser embrionária).
    - Repertório baseado nos textos motivadores e/ou repertório não legitimado e/ou repertório legitimado, mas não pertinente ao tema.
    - Desenvolvimento do tema de forma previsível, com argumentação mediana, sem grandes inovações.
    - Domínio mediano do texto dissertativo-argumentativo, com proposição, argumentação e conclusão, mas de forma superficial.

    Nota 80:
    - Abordagem completa do tema, mas com problemas relacionados ao tipo textual e presença de muitos trechos de cópia sem aspas.
    - Domínio insuficiente do texto dissertativo-argumentativo, faltando a estrutura completa de proposição, argumentação e conclusão.
    - Não desenvolve um ponto de vista claro e não consegue conectar as ideias argumentativas adequadamente.
    - Duas partes embrionárias ou com conclusão finalizada por frase incompleta.

    Nota 40:
    - Tangencia o tema, sem abordar diretamente o ponto central proposto.
    - Domínio precário do texto dissertativo-argumentativo, com traços de outros tipos textuais.
    - Não constrói uma argumentação clara e objetiva, resultando em confusão ou desvio do gênero textual.

    Nota 0:
    - Fuga completa do tema proposto, abordando um assunto irrelevante ou não relacionado.
    - Não atende à estrutura dissertativo-argumentativa, sendo classificado como outro gênero textual.
    - Não apresenta proposição, argumentação e conclusão, ou o texto é anulado por não atender aos critérios básicos de desenvolvimento textual.

    Forneça a nota e uma justificativa detalhada, relacionando diretamente com a análise fornecida e com os critérios específicos.

    Formato da resposta:
    Nota: [NOTA ATRIBUÍDA]
    Justificativa: [Justificativa detalhada da nota, explicando como cada aspecto da análise se relaciona com os critérios de pontuação]
    """

    try:
        # Gerar resposta usando o modelo
        resposta_nota = client.messages.create(
            model="ft:gpt-4o-2024-08-06:personal:competencia-2:AHDT84HO",
            messages=[{"role": "user", "content": prompt_nota}],
            temperature=0.3
        )
        
        # Extrair nota e justificativa
        resultado = extrair_nota_e_justificativa(resposta_nota.content)
        
        # Validar se a nota está nos valores permitidos
        if resultado['nota'] not in [0, 40, 80, 120, 160, 200]:
            nota_ajustada = 40 * round(resultado['nota'] / 40)
            resultado['nota'] = max(0, min(200, nota_ajustada))
            resultado['justificativa'] += "\nNota ajustada para o valor válido mais próximo."
        
        return resultado
        
    except Exception as e:
        logger.error(f"Erro ao atribuir nota: {str(e)}")
        return {
            'nota': 0,
            'justificativa': "Erro ao gerar nota e justificativa."
        }

def atribuir_nota_competency3(analise: str, erros: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Atribui nota à Competência 3 com base na análise e erros identificados.
    
    Args:
        analise: String contendo a análise detalhada do texto
        erros: Lista de dicionários contendo os erros identificados
        
    Returns:
        Dict contendo a nota atribuída (0-200) e sua justificativa
    """
    prompt_nota = f"""
    Com base na seguinte análise da Competência 3 (Seleção e Organização das Informações) do ENEM, atribua uma nota de 0 a 200 em intervalos de 40 pontos (0, 40, 80, 120, 160 ou 200).

    Análise:
    {analise}

    Erros identificados:
    {json.dumps(erros, indent=2)}

    Considere cuidadosamente os seguintes critérios para atribuir a nota:

    Nota 200:
    - Ideias progressivas e argumentos bem selecionados, revelando um planejamento claro do texto.
    - Apresenta informações, fatos e opiniões relacionados ao tema proposto e aos seus argumentos, de forma consistente e organizada, em defesa de um ponto de vista.
    - Demonstra autoria, com informações e argumentos originais que reforçam o ponto de vista do aluno.
    - Mantém o encadeamento das ideias, com cada parágrafo apresentando informações coerentes com o anterior, sem repetições desnecessárias ou saltos temáticos.
    - Apresenta poucas falhas, e essas falhas não prejudicam a progressão do texto.

    Nota 160:
    - Apresenta informações, fatos e opiniões relacionados ao tema, de forma organizada, com indícios de autoria em defesa de um ponto de vista.
    - Ideias claramente organizadas, mas não tão consistentes quanto o esperado para uma argumentação mais sólida.
    - Organização geral das ideias é boa, mas algumas informações e opiniões não estão bem desenvolvidas.

    Nota 120:
    - Apresenta informações, fatos e opiniões relacionados ao tema, mas limitados aos argumentos dos textos motivadores e pouco organizados, em defesa de um ponto de vista.
    - Ideias previsíveis, sem desenvolvimento profundo ou originalidade, com pouca evidência de autoria.
    - Argumentos simples, sem clara progressão de ideias, e baseado principalmente nas sugestões dos textos motivadores.

    Nota 80:
    - Apresenta informações, fatos e opiniões relacionados ao tema, mas de forma desorganizada ou contraditória, e limitados aos argumentos dos textos motivadores.
    - Ideias não estão bem conectadas, demonstrando falta de coerência e organização no desenvolvimento do texto.
    - Argumentos inconsistentes ou contraditórios, prejudicando a defesa do ponto de vista.
    - Perde linhas com informações irrelevantes, repetidas ou excessivas.

    Nota 40:
    - Apresenta informações, fatos e opiniões pouco relacionados ao tema, com incoerências, e sem defesa clara de um ponto de vista.
    - Falta de organização e ideias dispersas, sem desenvolvimento coerente.
    - Não apresenta um ponto de vista claro, e os argumentos são fracos ou desconexos.

    Nota 0:
    - Apresenta informações, fatos e opiniões não relacionados ao tema, sem coerência, e sem defesa de um ponto de vista.
    - Ideias totalmente desconexas, sem organização ou relação com o tema proposto.
    - Não desenvolve qualquer argumento relevante ou coerente, demonstrando falta de planejamento.

    Forneça a nota e uma justificativa detalhada, relacionando diretamente com a análise fornecida e com os critérios específicos.

    Formato da resposta:
    Nota: [NOTA ATRIBUÍDA]
    Justificativa: [Justificativa detalhada da nota, explicando como cada aspecto da análise se relaciona com os critérios de pontuação]
    """

    try:
        # Gerar resposta usando o modelo
        resposta_nota = client.messages.create(
            model="ft:gpt-4o-2024-08-06:personal:competencia-3:AHDUfZRb",
            messages=[{"role": "user", "content": prompt_nota}],
            temperature=0.3
        )
        
        # Extrair nota e justificativa
        resultado = extrair_nota_e_justificativa(resposta_nota.content)
        
        # Validar se a nota está nos valores permitidos
        if resultado['nota'] not in [0, 40, 80, 120, 160, 200]:
            nota_ajustada = 40 * round(resultado['nota'] / 40)
            resultado['nota'] = max(0, min(200, nota_ajustada))
            resultado['justificativa'] += "\nNota ajustada para o valor válido mais próximo."
        
        return resultado
        
    except Exception as e:
        logger.error(f"Erro ao atribuir nota: {str(e)}")
        return {
            'nota': 0,
            'justificativa': "Erro ao gerar nota e justificativa."
        }

def atribuir_nota_competency4(analise: str, erros: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Atribui nota à Competência 4 com base na análise e erros identificados.
    
    Args:
        analise: String contendo a análise detalhada do texto
        erros: Lista de dicionários contendo os erros identificados
        
    Returns:
        Dict contendo a nota atribuída (0-200) e sua justificativa
    """
    prompt_nota = f"""
    Com base na seguinte análise da Competência 4 (Conhecimento dos Mecanismos Linguísticos) do ENEM, atribua uma nota de 0 a 200 em intervalos de 40 pontos (0, 40, 80, 120, 160 ou 200).

    Análise:
    {analise}

    Erros identificados:
    {json.dumps(erros, indent=2)}

    Considere cuidadosamente os seguintes critérios para atribuir a nota:

    Nota 200:
    - Utiliza conectivos em todo início de período.
    - Articula bem as partes do texto e apresenta um repertório diversificado de recursos coesivos, conectando parágrafos e períodos de forma fluida.
    - Utiliza referenciação adequada, com pronomes, sinônimos e advérbios, garantindo coesão e clareza.
    - Apresenta transições claras e bem estruturadas entre as ideias de causa/consequência, comparação e conclusão, sem falhas.
    - Demonstra excelente organização de períodos complexos, com uma articulação eficiente entre orações.
    - Não repete muitos conectivos ao longo do texto.

    Nota 160:
    - Deixa de usar uma ou duas vezes conectivos ao longo do texto.
    - Articula as partes do texto, mas com poucas inadequações ou problemas pontuais na conexão de ideias.
    - Apresenta um repertório diversificado de recursos coesivos, mas com algumas falhas no uso de pronomes, advérbios ou sinônimos.
    - As transições entre parágrafos e ideias são adequadas, mas com pequenos deslizes na estruturação dos períodos complexos.
    - Mantém boa coesão e coerência, mas com algumas falhas na articulação entre causas, consequências e exemplos.

    Nota 120:
    - Não usa muitos conectivos ao longo dos parágrafos.
    - Repete várias vezes o mesmo conectivo ao longo do parágrafo.
    - Articula as partes do texto de forma mediana, apresentando inadequações frequentes na conexão de ideias.
    - O repertório de recursos coesivos é pouco diversificado, com uso repetitivo de pronomes.
    - Apresenta transições previsíveis e pouco elaboradas, prejudicando o encadeamento lógico das ideias.
    - A organização dos períodos é mediana, com algumas orações mal articuladas, comprometendo a fluidez do texto.

    Nota 80:
    - Articula as partes do texto de forma insuficiente, com muitas inadequações no uso de conectivos e outros recursos coesivos.
    - O repertório de recursos coesivos é limitado, resultando em repetição excessiva ou uso inadequado de pronomes e advérbios.
    - Apresenta conexões falhas entre os parágrafos, com transições abruptas e pouco claras entre as ideias.
    - Os períodos complexos estão mal estruturados, com orações desconectadas ou confusas.

    Nota 40:
    - Articula as partes do texto de forma precária, com sérias falhas na conexão de ideias.
    - O repertório de recursos coesivos é praticamente inexistente, sem o uso adequado de pronomes, conectivos ou advérbios.
    - Apresenta parágrafos desarticulados, sem relação clara entre as ideias.
    - Os períodos são curtos e desconectados, sem estruturação adequada ou progressão de ideias.

    Nota 0:
    - Não articula as informações e as ideias parecem desconexas e sem coesão.
    - O texto não apresenta recursos coesivos, resultando em total falta de conexão entre as partes.
    - Os parágrafos e períodos são desorganizados, sem qualquer lógica na apresentação das ideias.
    - O texto não utiliza mecanismos de coesão (pronomes, conectivos, advérbios), tornando-o incompreensível.

    Forneça a nota e uma justificativa detalhada, relacionando diretamente com a análise fornecida e com os critérios específicos.

    Formato da resposta:
    Nota: [NOTA ATRIBUÍDA]
    Justificativa: [Justificativa detalhada da nota, explicando como cada aspecto da análise se relaciona com os critérios de pontuação]
    """

    try:
        # Gerar resposta usando o modelo
        resposta_nota = client.messages.create(
            model="ft:gpt-4o-2024-08-06:personal:competencia-4:AHDXewU3",
            messages=[{"role": "user", "content": prompt_nota}],
            temperature=0.3
        )
        
        # Extrair nota e justificativa
        resultado = extrair_nota_e_justificativa(resposta_nota.content)
        
        # Validar se a nota está nos valores permitidos
        if resultado['nota'] not in [0, 40, 80, 120, 160, 200]:
            nota_ajustada = 40 * round(resultado['nota'] / 40)
            resultado['nota'] = max(0, min(200, nota_ajustada))
            resultado['justificativa'] += "\nNota ajustada para o valor válido mais próximo."
        
        return resultado
        
    except Exception as e:
        logger.error(f"Erro ao atribuir nota: {str(e)}")
        return {
            'nota': 0,
            'justificativa': "Erro ao gerar nota e justificativa."
        }

def atribuir_nota_competency5(analise: str, erros: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Atribui nota à Competência 5 com base na análise e erros identificados.
    
    Args:
        analise: String contendo a análise detalhada do texto
        erros: Lista de dicionários contendo os erros identificados
        
    Returns:
        Dict contendo a nota atribuída (0-200) e sua justificativa
    """
    prompt_nota = f"""
    Com base na seguinte análise da Competência 5 (Proposta de Intervenção) do ENEM, atribua uma nota de 0 a 200 em intervalos de 40 pontos (0, 40, 80, 120, 160 ou 200).

    Análise:
    {analise}

    Erros identificados:
    {json.dumps(erros, indent=2)}

    Considere cuidadosamente os seguintes critérios para atribuir a nota:

    Nota 200:
    - Elabora proposta de intervenção completa, detalhada e relacionada ao tema.
    - Apresenta os 5 elementos obrigatórios:
      * Agente(s) que executará(ão) a ação
      * Ação(ões) para resolver o problema
      * Modo/meio de execução da ação
      * Detalhamento da execução e/ou dos efeitos esperados
      * Finalidade/objetivo da proposta
    - Proposta é completamente pertinente ao tema e bem articulada à discussão desenvolvida no texto.
    - Demonstra respeito aos direitos humanos.
    - Apresenta detalhamento dos meios, modos e/ou instrumentos para cada ação sugerida.
    - Proposta é viável e bem desenvolvida.

    Nota 160:
    - Elabora proposta de intervenção relacionada ao tema.
    - Apresenta 4 dos elementos obrigatórios.
    - Proposta é pertinente ao tema e articulada à discussão desenvolvida no texto.
    - Demonstra respeito aos direitos humanos.
    - Apresenta detalhamento, mas com algumas falhas ou omissões.
    - Proposta é viável mas precisa de alguns ajustes.

    Nota 120:
    - Elabora proposta de intervenção relacionada ao tema.
    - Apresenta 3 dos elementos obrigatórios.
    - Proposta é pertinente ao tema mas pouco articulada à discussão.
    - Demonstra respeito aos direitos humanos.
    - Apresenta detalhamento insuficiente.
    - Proposta é parcialmente viável.

    Nota 80:
    - Elabora proposta de intervenção tangencial ao tema.
    - Apresenta apenas 2 dos elementos obrigatórios.
    - Proposta tem articulação fraca com a discussão.
    - Demonstra respeito aos direitos humanos.
    - Praticamente não há detalhamento.
    - Proposta tem viabilidade questionável.

    Nota 40:
    - Elabora proposta de intervenção tangencial ao tema.
    - Apresenta apenas 1 dos elementos obrigatórios.
    - Proposta não se articula com a discussão.
    - Demonstra respeito aos direitos humanos.
    - Não há detalhamento.
    - Proposta não demonstra viabilidade.

    Nota 0:
    - Não elabora proposta de intervenção.
    - Ou: elabora proposta não relacionada ao tema.
    - Ou: elabora proposta que desrespeita os direitos humanos.

    Forneça a nota e uma justificativa detalhada, relacionando diretamente com a análise fornecida e com os critérios específicos.

    Formato da resposta:
    Nota: [NOTA ATRIBUÍDA]
    Justificativa: [Justificativa detalhada da nota, explicando como cada aspecto da análise se relaciona com os critérios de pontuação]
    """

    try:
        # Gerar resposta usando o modelo
        resposta_nota = client.messages.create(
            model="ft:gpt-4o-2024-08-06:personal:competencia-5:AHGVPnJG",
            messages=[{"role": "user", "content": prompt_nota}],
            temperature=0.3
        )
        
        # Extrair nota e justificativa
        resultado = extrair_nota_e_justificativa(resposta_nota.content)
        
        # Validar se a nota está nos valores permitidos
        if resultado['nota'] not in [0, 40, 80, 120, 160, 200]:
            nota_ajustada = 40 * round(resultado['nota'] / 40)
            resultado['nota'] = max(0, min(200, nota_ajustada))
            resultado['justificativa'] += "\nNota ajustada para o valor válido mais próximo."
        
        return resultado
        
    except Exception as e:
        logger.error(f"Erro ao atribuir nota: {str(e)}")
        return {
            'nota': 0,
            'justificativa': "Erro ao gerar nota e justificativa."
        }

import json
import logging
from elevenlabs import generate, set_api_key
import openai

logger = logging.getLogger(__name__)

class RedacaoTutor:
    """Sistema de tutoria inteligente para redações do ENEM"""
    def __init__(self, openai_api_key: str, elevenlabs_api_key: str, competencies: dict):
        # Configuração das APIs
        openai.api_key = openai_api_key
        set_api_key(elevenlabs_api_key)
        self.competencies = competencies

    def iniciar_tutoria(self, resultados_analise: dict) -> dict:
        """
        Inicia uma sessão de tutoria baseada nos resultados da análise.
        """
        try:
            erros_por_competencia = resultados_analise['erros_especificos']
            notas = resultados_analise['notas']
            analises = resultados_analise['analises_detalhadas']
            competencia_foco = min(notas.items(), key=lambda x: x[1])[0]
            return self.criar_plano_tutoria(
                competencia_foco,
                erros_por_competencia.get(competencia_foco, []),
                notas.get(competencia_foco, 0),
                analises.get(competencia_foco, "")
            )
        except Exception as e:
            logger.error(f"Erro ao iniciar tutoria: {e}")
            return {}

    def criar_plano_tutoria(self, competencia: str, erros: list, nota: int, analise: str) -> dict:
        """
        Cria um plano de tutoria personalizado.
        """
        prompt = f"""
        Com base na análise desta redação na competência {self.competencies.get(competencia, "Desconhecida")}:
        Nota: {nota}/200
        Análise: {analise}
        Erros identificados: {json.dumps(erros, indent=2)}

        Crie um plano de tutoria que inclua:
        1. Diagnóstico detalhado
        2. Sequência de exercícios
        3. Pontos de checagem
        4. Recomendações de estudo
        5. Critérios de avanço

        Responda em formato JSON:
        {{
            "diagnostico": {{}},
            "plano_estudo": {{}},
            "recomendacoes": []
        }}
        """
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Você é um tutor especializado em redação para o ENEM."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            return json.loads(response['choices'][0]['message']['content'])
        except Exception as e:
            logger.error(f"Erro ao criar plano de tutoria: {e}")
            return {}

    def gerar_audio_feedback(self, texto: str) -> bytes:
        """
        Gera áudio do feedback usando ElevenLabs em Português do Brasil.
        """
        try:
            audio = generate(
                text=texto,
                voice="Ana",  # Use uma voz compatível com PT-BR, ex.: "Ana"
                model="eleven_monolingual_v1"
            )
            return audio
        except Exception as e:
            logger.error(f"Erro ao gerar áudio: {e}")
            return b""

    def avaliar_resposta(self, exercicio: dict, resposta: str, competencia: str) -> dict:
        """
        Avalia resposta do aluno para um exercício.
        """
        prompt = f"""
        Avalie a seguinte resposta para um exercício da competência {self.competencies.get(competencia, "Desconhecida")}:
        Exercício: {json.dumps(exercicio, indent=2)}
        Resposta do aluno: {resposta}

        Critérios de avaliação: {json.dumps(exercicio.get("criterios_avaliacao", []), indent=2)}

        Responda em JSON:
        {{
            "feedback_geral": "",
            "pontos_positivos": [],
            "areas_melhoria": [],
            "proximos_passos": [],
            "pontuacao": 0
        }}
        """
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Você é um avaliador especializado em redação para o ENEM."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            return json.loads(response['choices'][0]['message']['content'])
        except Exception as e:
            logger.error(f"Erro ao avaliar resposta: {e}")
            return {
                "feedback_geral": "Não foi possível avaliar a resposta.",
                "pontos_positivos": [],
                "areas_melhoria": [],
                "proximos_passos": [],
                "pontuacao": 0
            }

    def gerar_feedback_final(self, competencia: str, historico_exercicios: list) -> dict:
        """
        Gera feedback final da sessão de tutoria.
        """
        prompt = f"""
        Gere um feedback final para a sessão de tutoria em {self.competencies.get(competencia, "Desconhecida")}.
        Histórico de exercícios:
        {json.dumps(historico_exercicios, indent=2)}

        Forneça:
        1. Análise do progresso
        2. Principais conquistas
        3. Áreas que ainda precisam de atenção
        4. Recomendações para estudo contínuo
        5. Próximos objetivos sugeridos

        Responda em formato JSON:
        {{
            "analise_progresso": "",
            "conquistas": [],
            "areas_atencao": [],
            "recomendacoes": [],
            "proximos_objetivos": [],
            "mensagem_motivacional": ""
        }}
        """
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Você é um tutor especializado em redação para o ENEM."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            feedback = json.loads(response['choices'][0]['message']['content'])
            
            if "mensagem_motivacional" in feedback:
                feedback['audio'] = self.gerar_audio_feedback(feedback["mensagem_motivacional"])
            return feedback
        except Exception as e:
            logger.error(f"Erro ao gerar feedback final: {e}")
            return {}


def pagina_tutoria():
    """Página principal do sistema de tutoria"""
    st.title("Sistema de Tutoria Personalizada")

    # Verificar se há análise disponível
    if 'resultados' not in st.session_state:
        st.warning("É necessário analisar uma redação primeiro para iniciar a tutoria.")
        if st.button("Enviar Redação"):
            st.session_state.page = 'envio'
            st.rerun()
        return

    # Inicializar o tutor se necessário
    if 'tutor' not in st.session_state:
        st.session_state.tutor = RedacaoTutor(client, generate)

    # Inicializar estados da tutoria se necessário
    if 'tutoria_estado' not in st.session_state:
        st.session_state.tutoria_estado = {
            'etapa': 'diagnostico',
            'competencia_foco': None,
            'exercicios_completos': set(),
            'pontuacao': 0,
            'historico': []
        }

    # Barra lateral com progresso e informações
    with st.sidebar:
        st.subheader("Seu Progresso")
        progresso = calcular_progresso_tutoria(st.session_state.tutoria_estado['etapa'])
        st.progress(progresso)
        st.metric("Pontuação", st.session_state.tutoria_estado['pontuacao'])
        
        if st.session_state.tutoria_estado['competencia_foco']:
            st.write(f"Foco atual: {COMPETENCIES[st.session_state.tutoria_estado['competencia_foco']]}")

    # Lógica principal baseada na etapa atual
    etapa = st.session_state.tutoria_estado['etapa']
    
    if etapa == 'diagnostico':
        mostrar_diagnostico_inicial()
    elif etapa == 'plano_estudo':
        mostrar_plano_estudo()
    elif etapa == 'exercicios':
        mostrar_exercicios()
    elif etapa == 'feedback':
        mostrar_feedback_final()

def mostrar_diagnostico_inicial():
    """Mostra diagnóstico inicial e permite escolha de competência foco"""
    st.subheader("Diagnóstico Inicial")

    resultados = st.session_state.resultados
    notas = resultados['notas']
    
    # Mostrar gráfico de competências
    criar_grafico_radar(notas)
    
    # Identificar competência mais fraca
    competencia_mais_fraca = min(notas.items(), key=lambda x: x[1])[0]
    
    # Permitir escolha da competência
    st.info(f"Competência recomendada: {COMPETENCIES[competencia_mais_fraca]}")
    
    competencia_escolhida = st.selectbox(
        "Escolha a competência para trabalhar:",
        list(COMPETENCIES.keys()),
        format_func=lambda x: f"{COMPETENCIES[x]} (Nota: {notas[x]}/200)",
        index=list(COMPETENCIES.keys()).index(competencia_mais_fraca)
    )
    
    if st.button("Iniciar Plano de Estudos"):
        # Gerar plano de tutoria
        plano = st.session_state.tutor.criar_plano_tutoria(
            competencia_escolhida,
            resultados['erros_especificos'][competencia_escolhida],
            notas[competencia_escolhida],
            resultados['analises_detalhadas'][competencia_escolhida]
        )
        
        # Atualizar estado
        st.session_state.tutoria_estado.update({
            'etapa': 'plano_estudo',
            'competencia_foco': competencia_escolhida,
            'plano_atual': plano
        })
        st.rerun()

def mostrar_plano_estudo():
    """Mostra e gerencia o plano de estudos personalizado"""
    st.subheader("Seu Plano de Estudos")
    
    plano = st.session_state.tutoria_estado['plano_atual']
    
    # Mostrar diagnóstico
    with st.expander("Diagnóstico", expanded=True):
        st.write("**Principais Dificuldades:**")
        for dif in plano['diagnostico']['dificuldades_principais']:
            st.write(f"- {dif}")
            
        st.write("**Pontos Fortes:**")
        for ponto in plano['diagnostico']['pontos_fortes']:
            st.write(f"- {ponto}")
    
    # Mostrar módulos de estudo
    st.subheader("Módulos de Estudo")
    for i, modulo in enumerate(plano['plano_estudo']['modulos']):
        with st.expander(f"📚 Módulo {i+1}: {modulo['titulo']}", expanded=i==0):
            st.write(f"**Objetivo:** {modulo['objetivo']}")
            
            st.write("**Exercícios:**")
            for ex in modulo['exercicios']:
                st.write(f"- {ex}")
                
            st.write("**Recursos:**")
            for rec in modulo['recursos']:
                st.write(f"- {rec}")
    
    # Mostrar recomendações
    with st.expander("📝 Recomendações"):
        for rec in plano['recomendacoes']:
            st.write(f"- {rec}")
    
    if st.button("Começar Exercícios"):
        st.session_state.tutoria_estado['etapa'] = 'exercicios'
        st.rerun()

def mostrar_exercicios():
    """Mostra e gerencia os exercícios práticos"""
    st.subheader("Exercícios Práticos")
    
    # Gerar novo exercício se necessário
    if 'exercicio_atual' not in st.session_state.tutoria_estado:
        exercicio = st.session_state.tutor.gerar_exercicio(
            st.session_state.tutoria_estado['competencia_foco'],
            'intermediário'  # Poderia ser dinâmico baseado no desempenho
        )
        st.session_state.tutoria_estado['exercicio_atual'] = exercicio
    
    exercicio = st.session_state.tutoria_estado['exercicio_atual']
    
    # Mostrar exercício
    st.markdown(f"### {exercicio['titulo']}")
    st.write(exercicio['instrucoes'])
    
    # Mostrar exemplos
    with st.expander("Ver Exemplos"):
        for ex in exercicio['exemplos']:
            st.write(f"- {ex}")
    
    # Área para resposta
    resposta = st.text_area(
        "Sua resposta:",
        height=200,
        key="resposta_exercicio"
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Verificar"):
            if resposta:
                feedback = st.session_state.tutor.avaliar_resposta(
                    exercicio,
                    resposta,
                    st.session_state.tutoria_estado['competencia_foco']
                )
                
                # Mostrar feedback
                st.write("### Feedback")
                st.write(feedback['feedback_geral'])
                
                with st.expander("Detalhes"):
                    st.write("**Pontos Positivos:**")
                    for ponto in feedback['pontos_positivos']:
                        st.write(f"- {ponto}")
                        
                    st.write("**Áreas de Melhoria:**")
                    for area in feedback['areas_melhoria']:
                        st.write(f"- {area}")
                
                # Atualizar pontuação
                st.session_state.tutoria_estado['pontuacao'] += feedback['pontuacao']
                
                # Adicionar ao histórico
                st.session_state.tutoria_estado['historico'].append({
                    'exercicio': exercicio,
                    'resposta': resposta,
                    'feedback': feedback
                })
                
                # Reproduzir feedback em áudio
                if 'audio' in feedback:
                    st.audio(feedback['audio'])
            else:
                st.warning("Por favor, forneça uma resposta antes de verificar.")
    
    with col2:
        if st.button("Próximo Exercício"):
            del st.session_state.tutoria_estado['exercicio_atual']
            st.rerun()

def mostrar_feedback_final():
    """Mostra feedback final e conclusão da tutoria"""
    st.subheader("Feedback Final")
    
    feedback = st.session_state.tutor.gerar_feedback_final(
        st.session_state.tutoria_estado['competencia_foco'],
        st.session_state.tutoria_estado['historico']
    )
    
    st.write(feedback['analise_progresso'])
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Principais Conquistas:**")
        for conquista in feedback['conquistas']:
            st.write(f"- {conquista}")
            
        st.write("**Próximos Objetivos:**")
        for obj in feedback['proximos_objetivos']:
            st.write(f"- {obj}")
    
    with col2:
        st.write("**Áreas para Atenção:**")
        for area in feedback['areas_atencao']:
            st.write(f"- {area}")
            
        st.write("**Recomendações:**")
        for rec in feedback['recomendacoes']:
            st.write(f"- {rec}")
    
    if 'audio' in feedback:
        st.audio(feedback['audio'])
    
    if st.button("Concluir Tutoria"):
        # Resetar estado da tutoria
        st.session_state.tutoria_estado = {
            'etapa': 'diagnostico',
            'competencia_foco': None,
            'exercicios_completos': set(),
            'pontuacao': 0,
            'historico': []
        }
        st.rerun()

def calcular_progresso_tutoria(etapa: str) -> float:
    """Calcula o progresso da tutoria baseado na etapa atual"""
    etapas = {
        'diagnostico': 0.25,
        'plano_estudo': 0.5,
        'exercicios': 0.75,
        'feedback': 1.0
    }
    return etapas.get(etapa, 0.0)

def extrair_erros_do_resultado(resultado: str) -> List[Dict[str, str]]:
    """
    Extrai erros do texto de resultado da análise.
    
    Args:
        resultado: String contendo o resultado da análise
        
    Returns:
        Lista de dicionários contendo os erros identificados
    """
    erros = []
    padrao_erro = re.compile(r'ERRO\n(.*?)\nFIM_ERRO', re.DOTALL)
    matches = padrao_erro.findall(resultado)
    
    for match in matches:
        erro = {}
        for linha in match.split('\n'):
            if ':' in linha:
                chave, valor = linha.split(':', 1)
                chave = chave.strip().lower()
                valor = valor.strip()
                if chave == 'trecho':
                    valor = valor.strip('"')
                erro[chave] = valor
        if 'descrição' in erro and 'trecho' in erro:
            erros.append(erro)
    
    return erros

def criar_grafico_radar(notas: Dict[str, int]):
    """
    Cria e exibe gráfico radar das competências.
    
    Args:
        notas: Dicionário com notas de cada competência
    """
    categorias = list(COMPETENCIES.values())
    valores = [notas[f"competency{i+1}"] for i in range(5)]
    
    fig = go.Figure(data=go.Scatterpolar(
        r=valores,
        theta=categorias,
        fill='toself',
        line=dict(color='#4CAF50', width=2),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 200],
                tickmode='linear',
                tick0=0,
                dtick=40,
                gridcolor='rgba(0,0,0,0.1)'
            ),
            angularaxis=dict(
                gridcolor='rgba(0,0,0,0.1)'
            )
        ),
        showlegend=False,
        title={
            'text': 'Perfil de Competências',
            'y':0.95,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': dict(size=20)
        },
        paper_bgcolor='white'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def extrair_nota_e_justificativa(resposta: str) -> Dict[str, Any]:
    """
    Extrai nota e justificativa do texto de resposta.
    
    Args:
        resposta: String contendo a resposta do modelo
        
    Returns:
        Dict contendo nota e justificativa
    """
    linhas = resposta.strip().split('\n')
    nota = None
    justificativa = []
    
    lendo_justificativa = False
    
    for linha in linhas:
        linha = linha.strip()
        if linha.startswith('Nota:'):
            try:
                nota = int(linha.split(':')[1].strip())
            except ValueError:
                raise ValueError("Formato de nota inválido")
        elif linha.startswith('Justificativa:'):
            lendo_justificativa = True
        elif lendo_justificativa and linha:
            justificativa.append(linha)
    
    if nota is None:
        raise ValueError("Nota não encontrada na resposta")
        
    return {
        'nota': nota,
        'justificativa': ' '.join(justificativa)
    }

def validar_redacao(texto: str, tema: str) -> Tuple[bool, str]:
    """
    Valida o texto da redação e o tema.
    
    Args:
        texto: Texto da redação
        tema: Tema da redação
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    if not texto or not texto.strip():
        return False, "O texto da redação não pode estar vazio."
        
    if not tema or not tema.strip():
        return False, "O tema da redação não pode estar vazio."
        
    palavras = len(texto.split())
    if palavras < 50:
        return False, f"Texto muito curto ({palavras} palavras). Mínimo recomendado: 400 palavras."
        
    if palavras > 3000:
        return False, f"Texto muito longo ({palavras} palavras). Máximo recomendado: 3000 palavras."
        
    return True, ""

def formatar_erro(erro: Dict[str, str]) -> str:
    """
    Formata erro para exibição.
    
    Args:
        erro: Dicionário contendo informações do erro
        
    Returns:
        String formatada do erro
    """
    return f"""
    **Erro encontrado:**
    - Trecho: "{erro.get('trecho', '')}"
    - Explicação: {erro.get('explicacao', '')}"
    - Sugestão: {erro.get('sugestao', '')}
    """

ERROR:__main__:Erro na inicialização dos clientes: module 'openai' has no attribute 'Client'

[12:38:10] 🔄 Updated app!

ERROR:__main__:Erro na inicialização dos clientes: module 'openai' has no attribute 'Client'
