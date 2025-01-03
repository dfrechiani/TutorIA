import os
import streamlit as st
import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Tuple
import plotly.graph_objects as go
from collections import Counter
from openai import OpenAI  # Nova importação
from elevenlabs import Client
from elevenlabs import Voice, VoiceSettings
import re

# Configuração inicial do Streamlit
st.set_page_config(
    page_title="Sistema de Análise de Redação ENEM",
    page_icon="📝",
    layout="wide"
)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Na inicialização dos clientes
try:
    # OpenAI (GPT-4)
    openai_client = OpenAI(api_key=st.secrets["openai"]["api_key"])
    # ElevenLabs
    eleven_client = Client(api_key=st.secrets["elevenlabs"]["api_key"])
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

def processar_redacao_completa(redacao_texto: str, tema_redacao: str) -> Dict[str, Any]:
    """
    Processa a redação completa e gera todos os resultados necessários usando IA.
    
    Args:
        redacao_texto: Texto da redação
        tema_redacao: Tema da redação
        
    Returns:
        Dict contendo todos os resultados da análise
    """
    logger.info("Iniciando processamento da redação")

    resultados = {
        'analises_detalhadas': {},
        'notas': {},
        'nota_total': 0,
        'erros_especificos': {},
        'justificativas': {},
        'total_erros_por_competencia': {},
        'sugestoes_estilo': {},
        'texto_original': redacao_texto
    }
    
    # Processar cada competência
    for comp, descricao in COMPETENCIES.items():
        try:
            # Realizar análise da competência
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
            
            # Garantir que erros existam, mesmo que vazio
            erros_revisados = resultado_analise.get('erros', [])
            
            # Atribuir nota baseado na análise completa e erros
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
            
            # Preencher resultados para esta competência
            resultados['analises_detalhadas'][comp] = resultado_analise['analise']
            resultados['notas'][comp] = resultado_nota['nota']
            resultados['justificativas'][comp] = resultado_nota['justificativa']
            resultados['erros_especificos'][comp] = erros_revisados
            resultados['total_erros_por_competencia'][comp] = len(erros_revisados)
            
            if 'sugestoes_estilo' in resultado_analise:
                resultados['sugestoes_estilo'][comp] = resultado_analise['sugestoes_estilo']

        except Exception as e:
            logger.error(f"Erro ao processar competência {comp}: {str(e)}")
            resultados['analises_detalhadas'][comp] = "Erro na análise"
            resultados['notas'][comp] = 0
            resultados['justificativas'][comp] = "Não foi possível realizar a análise"
            resultados['erros_especificos'][comp] = []
            resultados['total_erros_por_competencia'][comp] = 0

    # Calcular nota total
    resultados['nota_total'] = sum(resultados['notas'].values())
    
    # Salvar no session_state
    st.session_state.analise_realizada = True
    st.session_state.resultados = resultados
    st.session_state.redacao_texto = redacao_texto
    st.session_state.tema_redacao = tema_redacao
    st.session_state.erros_especificos_todas_competencias = resultados['erros_especificos']
    st.session_state.notas_atualizadas = resultados['notas'].copy()
    st.session_state.ultima_analise_timestamp = datetime.now().isoformat()
    
    logger.info("Processamento concluído. Resultados gerados.")
    return resultados

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

def analisar_competency2(redacao_texto: str, tema_redacao: str) -> Dict[str, Any]:
    """
    Análise da Competência 2: Compreensão do Tema.
    
    Args:
        redacao_texto: Texto da redação
        tema_redacao: Tema da redação
        
    Returns:
        Dict contendo análise e erros identificados
    """
    MODELO_COMP2 = "ft:gpt-4o-2024-08-06:personal:competencia-2:AHDT84HO"
    
    prompt_analise = f"""
    Analise a compreensão do tema na seguinte redação:
    
    Texto da redação: {redacao_texto}
    Tema proposto: {tema_redacao}
    
    Forneça uma análise detalhada, incluindo:
    1. Avaliação do domínio do tema proposto.
    2. Análise da presença das palavras principais do tema ou seus sinônimos em cada parágrafo.
    3. Avaliação da argumentação e uso de repertório sociocultural.
    4. Análise da clareza do ponto de vista adotado.
    5. Avaliação do vínculo entre o repertório e a discussão proposta.
    6. Verificação de cópia de trechos dos textos motivadores.
    7. Análise da citação de fontes do repertório utilizado.
    
    Para cada ponto analisado que represente um erro ou área de melhoria, forneça um exemplo específico do texto, no seguinte formato:
    ERRO
    Trecho: "[Trecho exato do texto]"
    Explicação: [Explicação detalhada]
    Sugestão: [Sugestão de melhoria]
    FIM_ERRO

    Se não houver erros significativos, indique isso claramente na análise.

    Formato da resposta:
    Domínio do Tema: [Sua análise aqui]
    Uso de Palavras-chave: [Sua análise aqui]
    Argumentação e Repertório: [Sua análise aqui]
    Clareza do Ponto de Vista: [Sua análise aqui]
    Vínculo Repertório-Discussão: [Sua análise aqui]
    Originalidade: [Sua análise aqui]
    Citação de Fontes: [Sua análise aqui]
    """

# Continuação da função analisar_competency2
    resposta_analise = client.messages.create(
        model=MODELO_COMP2,
        messages=[{"role": "user", "content": prompt_analise}],
        temperature=0.3
    )
    
    # Remover blocos de ERRO do texto da análise
    analise_geral = re.sub(r'ERRO\n.*?FIM_ERRO', '', resposta_analise.content, flags=re.DOTALL)
    
    # Extrair e revisar erros
    erros_identificados = extrair_erros_do_resultado(resposta_analise.content)
    erros_revisados = revisar_erros_competency2(erros_identificados, redacao_texto)

    return {
        'analise': analise_geral.strip(),
        'erros': erros_revisados
    }

def analisar_competency3(redacao_texto: str, tema_redacao: str) -> Dict[str, Any]:
    """
    Análise da Competência 3: Seleção e Organização das Informações.
    
    Args:
        redacao_texto: Texto da redação
        tema_redacao: Tema da redação
        
    Returns:
        Dict contendo análise e erros identificados
    """
    MODELO_COMP3 = "ft:gpt-4o-2024-08-06:personal:competencia-3:AHDUfZRb"
    
    prompt_analise = f"""
    Analise a seleção e organização das informações na seguinte redação:
    
    Texto da redação: {redacao_texto}
    Tema: {tema_redacao}

    Forneça uma análise detalhada, incluindo:
    1. Avaliação da progressão das ideias e seleção de argumentos.
    2. Análise da organização das informações e fatos relacionados ao tema.
    3. Comentários sobre a defesa do ponto de vista e consistência argumentativa.
    4. Avaliação da autoria e originalidade das informações apresentadas.
    5. Análise do encadeamento das ideias entre parágrafos.
    6. Verificação de repetições desnecessárias ou saltos temáticos.
    7. Avaliação da estrutura de cada parágrafo (argumento, justificativa, repertório, justificativa, frase de finalização).

    Para cada ponto analisado que represente um erro ou área de melhoria, forneça um exemplo específico do texto, no seguinte formato:
    ERRO
    Trecho: "[Trecho exato do texto]"
    Explicação: [Explicação detalhada]
    Sugestão: [Sugestão de melhoria]
    FIM_ERRO

    Se não houver erros significativos, indique isso claramente na análise.

    Formato da resposta:
    Progressão de Ideias: [Sua análise aqui]
    Organização de Informações: [Sua análise aqui]
    Defesa do Ponto de Vista: [Sua análise aqui]
    Autoria e Originalidade: [Sua análise aqui]
    Encadeamento entre Parágrafos: [Sua análise aqui]
    Estrutura dos Parágrafos: [Sua análise aqui]
    """

    resposta_analise = client.messages.create(
        model=MODELO_COMP3,
        messages=[{"role": "user", "content": prompt_analise}],
        temperature=0.3
    )
    
    # Remover blocos de ERRO do texto da análise
    analise_geral = re.sub(r'ERRO\n.*?FIM_ERRO', '', resposta_analise.content, flags=re.DOTALL)
    
    # Extrair e revisar erros
    erros_identificados = extrair_erros_do_resultado(resposta_analise.content)
    erros_revisados = revisar_erros_competency3(erros_identificados, redacao_texto)

    return {
        'analise': analise_geral.strip(),
        'erros': erros_revisados
    }

def analisar_competency4(redacao_texto: str, tema_redacao: str) -> Dict[str, Any]:
    """
    Análise da Competência 4: Conhecimento dos Mecanismos Linguísticos.
    
    Args:
        redacao_texto: Texto da redação
        tema_redacao: Tema da redação
        
    Returns:
        Dict contendo análise e erros identificados
    """
    MODELO_COMP4 = "ft:gpt-4o-2024-08-06:personal:competencia-4:AHDXewU3"
    
    prompt_analise = f"""
    Analise o conhecimento dos mecanismos linguísticos na seguinte redação:
    
    Texto da redação: {redacao_texto}
    Tema: {tema_redacao}

    Forneça uma análise detalhada, incluindo:
    1. Avaliação do uso de conectivos no início de cada período.
    2. Análise da articulação entre as partes do texto.
    3. Avaliação do repertório de recursos coesivos.
    4. Análise do uso de referenciação (pronomes, sinônimos, advérbios).
    5. Avaliação das transições entre ideias (causa/consequência, comparação, conclusão).
    6. Análise da organização de períodos complexos.
    7. Verificação da repetição de conectivos ao longo do texto.

    Para cada ponto analisado que represente um erro ou área de melhoria, forneça um exemplo específico do texto, no seguinte formato:
    ERRO
    Trecho: "[Trecho exato do texto]"
    Explicação: [Explicação detalhada]
    Sugestão: [Sugestão de melhoria]
    FIM_ERRO

    Se não houver erros significativos, indique isso claramente na análise.

    Formato da resposta:
    Uso de Conectivos: [Sua análise aqui]
    Articulação Textual: [Sua análise aqui]
    Recursos Coesivos: [Sua análise aqui]
    Referenciação: [Sua análise aqui]
    Transições de Ideias: [Sua análise aqui]
    Estrutura de Períodos: [Sua análise aqui]
    """

    resposta_analise = client.messages.create(
        model=MODELO_COMP4,
        messages=[{"role": "user", "content": prompt_analise}],
        temperature=0.3
    )
    
    # Remover blocos de ERRO do texto da análise
    analise_geral = re.sub(r'ERRO\n.*?FIM_ERRO', '', resposta_analise.content, flags=re.DOTALL)
    
    # Extrair e revisar erros
    erros_identificados = extrair_erros_do_resultado(resposta_analise.content)
    erros_revisados = revisar_erros_competency4(erros_identificados, redacao_texto)

    return {
        'analise': analise_geral.strip(),
        'erros': erros_revisados
    }

def analisar_competency5(redacao_texto: str, tema_redacao: str) -> Dict[str, Any]:
    """
    Análise da Competência 5: Proposta de Intervenção.
    
    Args:
        redacao_texto: Texto da redação
        tema_redacao: Tema da redação
        
    Returns:
        Dict contendo análise e erros identificados
    """
    MODELO_COMP5 = "ft:gpt-4o-2024-08-06:personal:competencia-5:AHGVPnJG"
    
    prompt_analise = f"""
    Analise a proposta de intervenção na seguinte redação:
    
    Texto da redação: {redacao_texto}
    Tema: {tema_redacao}

    Forneça uma análise detalhada, incluindo:
    1. Avaliação da presença dos cinco elementos obrigatórios: agente, ação, modo/meio, detalhamento e finalidade.
    2. Análise do nível de detalhamento e articulação da proposta com a discussão do texto.
    3. Avaliação da viabilidade e respeito aos direitos humanos na proposta.
    4. Verificação da retomada do contexto inicial (se houver).
    5. Análise da coerência entre a proposta e o tema discutido.

    Para cada ponto que represente um erro ou área de melhoria, forneça um exemplo específico do texto no seguinte formato:
    ERRO
    Trecho: "[Trecho exato do texto]"
    Explicação: [Explicação detalhada]
    Sugestão: [Sugestão de melhoria]
    FIM_ERRO

    Se não houver erros significativos, indique isso claramente na análise.

    Formato da resposta:
    Elementos da Proposta: [Sua análise aqui]
    Detalhamento e Articulação: [Sua análise aqui]
    Viabilidade e Direitos Humanos: [Sua análise aqui]
    Retomada do Contexto: [Sua análise aqui]
    Coerência com o Tema: [Sua análise aqui]
    """

    resposta_analise = client.messages.create(
        model=MODELO_COMP5,
        messages=[{"role": "user", "content": prompt_analise}],
        temperature=0.3
    )
    
    # Remover blocos de ERRO do texto da análise
    analise_geral = re.sub(r'ERRO\n.*?FIM_ERRO', '', resposta_analise.content, flags=re.DOTALL)
    
    # Extrair e revisar erros
    erros_identificados = extrair_erros_do_resultado(resposta_analise.content)
    erros_revisados = revisar_erros_competency5(erros_identificados, redacao_texto)

    return {
        'analise': analise_geral.strip(),
        'erros': erros_revisados
    }

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

class RedacaoTutor:
    """Sistema de tutoria inteligente para redações do ENEM"""
    def __init__(self, client: Anthropic, eleven_labs_client):
        self.client = client
        self.eleven_labs = eleven_labs_client
        self.competencies = COMPETENCIES

    def iniciar_tutoria(self, resultados_analise: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inicia uma sessão de tutoria baseada nos resultados da análise.
        
        Args:
            resultados_analise: Resultados da análise da redação
            
        Returns:
            Dict contendo plano de tutoria
        """
        # Extrair dados relevantes
        erros_por_competencia = resultados_analise['erros_especificos']
        notas = resultados_analise['notas']
        analises = resultados_analise['analises_detalhadas']
        
        # Identificar competência com menor nota
        competencia_foco = min(notas.items(), key=lambda x: x[1])[0]
        
        # Criar plano de tutoria
        plano = self.criar_plano_tutoria(
            competencia_foco,
            erros_por_competencia[competencia_foco],
            notas[competencia_foco],
            analises[competencia_foco]
        )
        
        return plano

    def criar_plano_tutoria(
        self, 
        competencia: str, 
        erros: List[Dict], 
        nota: int, 
        analise: str
    ) -> Dict[str, Any]:
        """
        Cria um plano de tutoria personalizado.
        """
        prompt = f"""
        Com base na análise desta redação na competência {self.competencies[competencia]}:
        
        Nota: {nota}/200
        Análise: {analise}
        Erros identificados: {json.dumps(erros, indent=2)}
        
        Crie um plano de tutoria que inclua:
        1. Diagnóstico detalhado das dificuldades
        2. Sequência de exercícios específicos
        3. Pontos de checagem de progresso
        4. Recomendações de estudo
        5. Critérios de avanço para próximo nível
        
        O plano deve ser interativo e usar voz para feedback.
        
        Responda em formato JSON com a seguinte estrutura:
        {
            "diagnostico": {
                "dificuldades_principais": [],
                "pontos_fortes": [],
                "areas_foco": []
            },
            "plano_estudo": {
                "modulos": [
                    {
                        "titulo": "",
                        "objetivo": "",
                        "exercicios": [],
                        "recursos": []
                    }
                ],
                "criterios_avanco": [],
                "tempo_estimado": ""
            },
            "recomendacoes": []
        }
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            return json.loads(response.content)
            
        except Exception as e:
            logger.error(f"Erro ao gerar plano de estudos: {e}")
            return {
                "diagnostico": {
                    "dificuldades_principais": ["Erro ao gerar diagnóstico"],
                    "pontos_fortes": [],
                    "areas_foco": []
                },
                "plano_estudo": {
                    "modulos": [],
                    "criterios_avanco": [],
                    "tempo_estimado": "N/A"
                },
                "recomendacoes": ["Tente novamente mais tarde"]
            }
    def gerar_exercicio(self, competencia: str, dificuldade: str) -> Dict[str, Any]:
        """
        Gera exercício personalizado baseado na competência e nível de dificuldade.
        
        Args:
            competencia: Competência a ser trabalhada
            dificuldade: Nível de dificuldade (básico, intermediário, avançado)
            
        Returns:
            Dict contendo exercício
        """
        prompt = f"""
        Crie um exercício prático para desenvolver habilidades na competência {self.competencies[competencia]} do ENEM.
        
        Nível de dificuldade: {dificuldade}
        
        O exercício deve:
        1. Ser específico e focado na competência
        2. Incluir instruções claras
        3. Ter formato interativo
        4. Incluir exemplos
        5. Ter critérios claros de avaliação
        
        Responda em formato JSON:
        {{
            "titulo": "Título do exercício",
            "instrucoes": "Instruções detalhadas",
            "exemplos": ["exemplo 1", "exemplo 2"],
            "tarefa": "Descrição da tarefa",
            "dicas": ["dica 1", "dica 2"],
            "criterios_avaliacao": ["critério 1", "critério 2"],
            "feedback_template": "Template para feedback baseado nos critérios"
        }}
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            return json.loads(response.content)
        
        except Exception as e:
            logger.error(f"Erro ao gerar exercício: {e}")
            return {
                "titulo": "Exercício Básico",
                "instrucoes": "Não foi possível gerar o exercício",
                "exemplos": [],
                "tarefa": "Tente novamente mais tarde",
                "dicas": [],
                "criterios_avaliacao": [],
                "feedback_template": ""
            }

    def avaliar_resposta(
        self, 
        exercicio: Dict[str, Any], 
        resposta: str, 
        competencia: str
    ) -> Dict[str, Any]:
        """
        Avalia resposta do aluno para um exercício.
        
        Args:
            exercicio: Exercício proposto
            resposta: Resposta do aluno
            competencia: Competência sendo avaliada
            
        Returns:
            Dict com feedback
        """
        prompt = f"""
        Avalie a seguinte resposta para um exercício de {self.competencies[competencia]}:
        
        Exercício:
        {json.dumps(exercicio, indent=2)}
        
        Resposta do aluno:
        {resposta}
        
        Critérios de avaliação:
        {json.dumps(exercicio['criterios_avaliacao'], indent=2)}
        
        Forneça:
        1. Feedback detalhado e construtivo
        2. Pontos positivos específicos
        3. Áreas de melhoria com sugestões práticas
        4. Próximos passos recomendados
        5. Pontuação (0-10)
        
        Responda em formato JSON:
        {{
            "feedback_geral": "Feedback principal",
            "pontos_positivos": ["ponto 1", "ponto 2"],
            "areas_melhoria": ["área 1", "área 2"],
            "sugestoes": ["sugestão 1", "sugestão 2"],
            "proximos_passos": ["passo 1", "passo 2"],
            "pontuacao": int,
            "feedback_voz": "Versão resumida do feedback para áudio"
        }}
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            feedback = json.loads(response.content)
            
            # Gerar áudio do feedback
            if self.eleven_labs:
                audio = self.gerar_audio_feedback(feedback['feedback_voz'])
                feedback['audio'] = audio
                
            return feedback
            
        except Exception as e:
            logger.error(f"Erro ao avaliar resposta: {e}")
            return {
                "feedback_geral": "Não foi possível avaliar a resposta",
                "pontos_positivos": [],
                "areas_melhoria": [],
                "sugestoes": [],
                "proximos_passos": ["Tente novamente"],
                "pontuacao": 0,
                "feedback_voz": "Erro na avaliação"
            }

    def gerar_audio_feedback(self, texto: str) -> bytes:
        """
        Gera áudio do feedback usando ElevenLabs.
        
        Args:
            texto: Texto do feedback
            
        Returns:
            Bytes do áudio gerado
        """
        try:
            return self.eleven_labs.generate(text=texto)
        except Exception as e:
            logger.error(f"Erro ao gerar áudio: {e}")
            return b""

    def gerar_feedback_final(
        self, 
        competencia: str, 
        historico_exercicios: List[Dict]
    ) -> Dict[str, Any]:
        """
        Gera feedback final da sessão de tutoria.
        
        Args:
            competencia: Competência trabalhada
            historico_exercicios: Histórico de exercícios realizados
            
        Returns:
            Dict com feedback final
        """
        prompt = f"""
        Gere um feedback final para a sessão de tutoria em {self.competencies[competencia]}.
        
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
            "analise_progresso": "Análise detalhada",
            "conquistas": ["conquista 1", "conquista 2"],
            "areas_atencao": ["área 1", "área 2"],
            "recomendacoes": ["recomendação 1", "recomendação 2"],
            "proximos_objetivos": ["objetivo 1", "objetivo 2"],
            "mensagem_motivacional": "Mensagem para áudio"
        }}
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            feedback = json.loads(response.content)
            
            # Gerar áudio da mensagem motivacional
            if self.eleven_labs:
                audio = self.gerar_audio_feedback(feedback['mensagem_motivacional'])
                feedback['audio'] = audio
                
            return feedback
            
        except Exception as e:
            logger.error(f"Erro ao gerar feedback final: {e}")
            return {
                "analise_progresso": "Não foi possível gerar análise",
                "conquistas": [],
                "areas_atencao": [],
                "recomendacoes": ["Continuar praticando"],
                "proximos_objetivos": [],
                "mensagem_motivacional": "Continue se esforçando"
            }

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

def main():
    """Função principal que controla o fluxo da aplicação"""
    # Configuração inicial da sessão
    if 'page' not in st.session_state:
        st.session_state.page = 'envio'

    # Navegação lateral
    with st.sidebar:
        st.title("📝 Análise de Redação ENEM")
        
        # Botões de navegação
        if st.button("Nova Redação 📝"):
            st.session_state.page = 'envio'
            st.rerun()
        
        if 'resultados' in st.session_state:
            if st.button("Ver Análise 📊"):
                st.session_state.page = 'resultado'
                st.rerun()
            
            if st.button("Tutoria 👨‍🏫"):
                st.session_state.page = 'tutoria'
                st.rerun()
        
        # Mostrar progresso da tutoria se estiver ativa
        if st.session_state.page == 'tutoria' and 'tutoria_estado' in st.session_state:
            st.divider()
            st.subheader("Progresso da Tutoria")
            st.progress(calcular_progresso_tutoria(st.session_state.tutoria_estado['etapa']))
            st.metric("Pontuação", st.session_state.tutoria_estado.get('pontuacao', 0))

    # Roteamento de páginas
    try:
        if st.session_state.page == 'envio':
            pagina_envio_redacao()
            
        elif st.session_state.page == 'resultado':
            if 'resultados' in st.session_state:
                pagina_resultado_analise()
            else:
                st.warning("Nenhuma análise disponível. Por favor, envie uma redação primeiro.")
                st.session_state.page = 'envio'
                st.rerun()
                
        elif st.session_state.page == 'tutoria':
            if 'resultados' in st.session_state:
                pagina_tutoria()
            else:
                st.warning("Nenhuma análise disponível. Por favor, envie uma redação primeiro.")
                st.session_state.page = 'envio'
                st.rerun()
                
        else:
            st.error("Página não encontrada")
            st.session_state.page = 'envio'
            st.rerun()

    except Exception as e:
        # Log do erro
        logger.error(f"Erro na execução: {str(e)}", exc_info=True)
        
        # Mensagem amigável para o usuário
        st.error("""
        Ocorreu um erro inesperado. Por favor, tente novamente.
        Se o problema persistir, entre em contato com o suporte.
        """)
        
        # Botão para reiniciar
        if st.button("Reiniciar Aplicação"):
            for key in list(st.session_state.keys()):
                if key != 'user':  # Mantém apenas o estado do usuário
                    del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Erro crítico na aplicação: {str(e)}")
        logger.critical("Erro crítico na aplicação", exc_info=True)
