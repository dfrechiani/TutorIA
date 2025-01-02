import os
import streamlit as st
import logging
import json
from datetime import datetime
from typing import Dict, List, Any
import plotly.graph_objects as go
from anthropic import Anthropic
from elevenlabs import generate
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

# Inicialização do cliente Anthropic
try:
    client = Anthropic(api_key=st.secrets["anthropic"]["api_key"])
except Exception as e:
    logger.error(f"Erro na inicialização do cliente Anthropic: {e}")
    st.error("Erro ao inicializar conexões. Por favor, tente novamente mais tarde.")

# Constantes
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
            resultado_analise = analisar_competencia(redacao_texto, tema_redacao, comp)
            
            # Garantir que erros existam, mesmo que vazio
            erros_revisados = resultado_analise.get('erros', [])
            
            # Atribuir nota baseado na análise completa e erros
            resultado_nota = atribuir_nota_competencia(comp, resultado_analise['analise'], erros_revisados)
            
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

def analisar_competency1(redacao_texto: str, tema_redacao: str) -> Dict[str, Any]:
    """
    Análise da Competência 1: Domínio da Norma Culta.
    Identifica apenas erros reais que devem penalizar a nota, separando sugestões estilísticas.
    
    Args:
        redacao_texto: Texto da redação
        tema_redacao: Tema da redação
        
    Returns:
        Dict contendo análise, erros, sugestões e total de erros
    """
    
    MODELO_COMP1 = "ft:gpt-4o-2024-08-06:personal:competencia-1:AHDQQucG"
    
    criterios = {
        "ortografia": """
        Analise o texto linha por linha quanto à ortografia, identificando APENAS ERROS REAIS em:
        1. Palavras escritas incorretamente
        2. Problemas de acentuação
        3. Uso incorreto de maiúsculas/minúsculas
        4. Grafia de estrangeirismos
        5. Abreviações inadequadas
        
        NÃO inclua sugestões de melhoria ou preferências estilísticas.
        Inclua apenas desvios claros da norma culta.
        
        Texto para análise: {redacao_texto}
        
        Para cada ERRO REAL encontrado, forneça:
        ERRO
        Descrição: [Descrição objetiva do erro ortográfico]
        Trecho: "[Trecho exato do texto]"
        Explicação: [Explicação técnica do erro]
        Sugestão: [Correção necessária]
        FIM_ERRO
        """,
        
        "pontuacao": """
        Analise o texto linha por linha quanto à pontuação, identificando APENAS ERROS REAIS em:
        1. Uso incorreto de vírgulas em:
           - Enumerações
           - Orações coordenadas
           - Orações subordinadas
           - Apostos e vocativos
           - Adjuntos adverbiais deslocados
        2. Uso inadequado de ponto e vírgula
        3. Uso incorreto de dois pontos
        4. Problemas com pontos finais
        5. Uso inadequado de reticências
        6. Problemas com travessões e parênteses
        
        NÃO inclua sugestões de melhoria ou pontuação opcional.
        Inclua apenas desvios claros das regras de pontuação.
        
        Texto para análise: {redacao_texto}
        
        Para cada ERRO REAL encontrado, forneça:
        ERRO
        Descrição: [Descrição objetiva do erro de pontuação]
        Trecho: "[Trecho exato do texto]"
        Explicação: [Explicação técnica do erro]
        Sugestão: [Correção necessária]
        FIM_ERRO
        """,
       
       "concordancia": """
        Analise o texto linha por linha quanto à concordância, identificando APENAS ERROS REAIS em:
        1. Concordância verbal
           - Sujeito e verbo
           - Casos especiais (coletivos, expressões partitivas)
        2. Concordância nominal
           - Substantivo e adjetivo
           - Casos especiais (é necessário, é proibido)
        3. Concordância ideológica
        4. Silepse (de gênero, número e pessoa)
        
        NÃO inclua sugestões de melhoria ou preferências de concordância.
        Inclua apenas desvios claros das regras de concordância.
        
        Texto para análise: {redacao_texto}
        
        Para cada ERRO REAL encontrado, forneça:
        ERRO
        Descrição: [Descrição objetiva do erro de concordância]
        Trecho: "[Trecho exato do texto]"
        Explicação: [Explicação técnica do erro]
        Sugestão: [Correção necessária]
        FIM_ERRO
        """,
        
        "regencia": """
        Analise o texto linha por linha quanto à regência, identificando APENAS ERROS REAIS em:
        1. Regência verbal
           - Uso inadequado de preposições com verbos
           - Ausência de preposição necessária
        2. Regência nominal
           - Uso inadequado de preposições com nomes
        3. Uso da crase: Verifique CUIDADOSAMENTE se há:
           - Junção de preposição 'a' com artigo definido feminino 'a'
           - Palavra feminina usada em sentido definido
           - Locuções adverbiais femininas
           
        IMPORTANTE: Analise cada caso considerando:
        - O contexto completo da frase
        - A função sintática das palavras
        - O sentido pretendido (definido/indefinido)
        - A regência dos verbos e nomes envolvidos
        
        NÃO marque como erro casos onde:
        - Não há artigo definido feminino
        - A palavra está sendo usada em sentido indefinido
        - Há apenas preposição 'a' sem artigo
        
        Texto para análise: {redacao_texto}
        
        Para cada ERRO REAL encontrado, forneça:
        ERRO
        Descrição: [Descrição objetiva do erro de regência]
        Trecho: "[Trecho exato do texto]"
        Explicação: [Explicação técnica DETALHADA do erro, incluindo análise sintática]
        Sugestão: [Correção necessária com justificativa]
        FIM_ERRO
        """
    }
    
    erros_por_criterio = {}
    for criterio, prompt in criterios.items():
        prompt_formatado = prompt.format(redacao_texto=redacao_texto)
        resposta = client.messages.create(
            model=MODELO_COMP1,
            messages=[{"role": "user", "content": prompt_formatado}],
            temperature=0.3
        )
        erros_por_criterio[criterio] = extrair_erros_do_resultado(resposta.content)

# Continuação da função analisar_competency1
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
    
    # Gerar análise final apenas com erros confirmados
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
    analise_geral = resposta_analise.content
    
    return {
        'analise': analise_geral,
        'erros': erros_revisados,
        'sugestoes_estilo': sugestoes_estilo,
        'total_erros': len(erros_revisados)
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

    # Gerar análise inicial
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

    # Gerar análise inicial
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

    # Gerar análise inicial
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

    # Gerar análise inicial
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


    
