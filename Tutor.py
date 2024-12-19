import streamlit as st
import random
import time
from datetime import datetime
from typing import Dict, List, Tuple, Set, Optional

# Constantes
BANCO_PALAVRAS = {
    'ARGUMENTAÇÃO': [
        'TESE', 'ARGUMENTO', 'PREMISSA', 'SILOGISMO', 'DEDUÇÃO',
        'INDUÇÃO', 'DIALÉTICA', 'RETÓRICA', 'PERSUASÃO', 'LÓGICA',
        'FALÁCIA', 'SOFISMO', 'INFERÊNCIA', 'CONCLUSÃO', 'REFUTAÇÃO'
    ],
    'ESTRUTURA': [
        'INTRODUÇÃO', 'DESENVOLVIMENTO', 'CONCLUSÃO', 'PARÁGRAFO',
        'PERÍODO', 'TÓPICO', 'TRANSIÇÃO', 'CONEXÃO', 'ESTRUTURA',
        'SEQUÊNCIA', 'ORDENAÇÃO', 'HIERARQUIA', 'SEÇÃO', 'SEGMENTO'
    ],
    'CONECTIVOS': [
        'PORTANTO', 'CONTUDO', 'ENTRETANTO', 'ADEMAIS', 'OUTROSSIM',
        'TODAVIA', 'PORQUANTO', 'CONQUANTO', 'PORÉM', 'ASSIM',
        'LOGO', 'POIS', 'ENTÃO', 'PORQUE', 'VISTO'
    ],
    'COMPETÊNCIAS': [
        'COESÃO', 'COERÊNCIA', 'REPERTÓRIO', 'PROPOSTA', 'AUTORIA',
        'ARGUMENTATIVO', 'DISSERTATIVO', 'INTERPRETAÇÃO', 'ANÁLISE',
        'SÍNTESE', 'AVALIAÇÃO', 'CRIATIVIDADE', 'ORIGINALIDADE'
    ],
    'REPERTÓRIO': [
        'FILOSOFIA', 'SOCIOLOGIA', 'HISTÓRIA', 'LITERATURA', 'CIÊNCIA',
        'POLÍTICA', 'ECONOMIA', 'CULTURA', 'TECNOLOGIA', 'ARTE',
        'DIREITO', 'PSICOLOGIA', 'ANTROPOLOGIA', 'LINGUÍSTICA'
    ],
    'DOCUMENTAÇÃO': [
        'CITAÇÃO', 'REFERÊNCIA', 'ALUSÃO', 'MENÇÃO', 'FONTE',
        'EVIDÊNCIA', 'EXEMPLO', 'PROVA', 'DADO', 'PESQUISA',
        'ESTUDO', 'ANÁLISE', 'DOCUMENTO', 'REGISTRO'
    ],
    'ESCRITA': [
        'CLAREZA', 'CONCISÃO', 'OBJETIVIDADE', 'PRECISÃO', 'FLUIDEZ',
        'ELEGÂNCIA', 'ESTILO', 'REGISTRO', 'TOM', 'VOCABULÁRIO',
        'EXPRESSÃO', 'LINGUAGEM', 'COMUNICAÇÃO'
    ],
    'PROCESSOS': [
        'PLANEJAR', 'REDIGIR', 'REVISAR', 'EDITAR', 'REESCREVER',
        'ESTRUTURAR', 'ORGANIZAR', 'DESENVOLVER', 'CONCLUIR',
        'ARGUMENTAR', 'DEFENDER', 'EXPLICAR', 'DEMONSTRAR'
    ]
}

GABARITOS = [
    {
        'distribuicao': {'VERMELHO': 9, 'AZUL': 8, 'NEUTRO': 7, 'ASSASSINO': 1},
        'primeiro_jogador': 'VERMELHO'
    },
    {
        'distribuicao': {'AZUL': 9, 'VERMELHO': 8, 'NEUTRO': 7, 'ASSASSINO': 1},
        'primeiro_jogador': 'AZUL'
    },
    {
        'distribuicao': {'VERMELHO': 8, 'AZUL': 9, 'NEUTRO': 7, 'ASSASSINO': 1},
        'primeiro_jogador': 'AZUL'
    },
    {
        'distribuicao': {'AZUL': 8, 'VERMELHO': 9, 'NEUTRO': 7, 'ASSASSINO': 1},
        'primeiro_jogador': 'VERMELHO'
    }
]

class Gabarito:
    def __init__(self):
        self.template = random.choice(GABARITOS)
        self.mapa = self.gerar_mapa()
        self.primeiro_jogador = self.template['primeiro_jogador']

    def gerar_mapa(self) -> List[str]:
        """Gera um mapa aleatório de cores baseado na distribuição do template"""
        mapa = []
        for cor, quantidade in self.template['distribuicao'].items():
            mapa.extend([cor] * quantidade)
        random.shuffle(mapa)
        return mapa

class CodenamesGame:
    def __init__(self):
        self.palavras: List[str] = self.selecionar_palavras()
        self.gabaritos: List[Gabarito] = [Gabarito() for _ in range(3)]
        self.gabarito_atual: int = 0
        self.reveladas: Set[str] = set()
        self.historico_dicas: List[Tuple[str, str, int]] = []
        self.turno_atual: str = self.gabaritos[0].primeiro_jogador
        self.dica_atual: Optional[Tuple[str, int]] = None
        self.tentativas_restantes: int = 0
        self.game_over: bool = False
        self.vencedor: Optional[str] = None
        self.pontuacao: Dict[str, int] = {'AZUL': 0, 'VERMELHO': 0}

    def selecionar_palavras(self) -> List[str]:
        """Seleciona 25 palavras aleatórias do banco de palavras"""
        todas_palavras = []
        for categoria, palavras in BANCO_PALAVRAS.items():
            todas_palavras.extend(palavras)
        return random.sample(todas_palavras, 25)

    def trocar_gabarito(self) -> Gabarito:
        """Troca para o próximo gabarito na sequência"""
        self.gabarito_atual = (self.gabarito_atual + 1) % len(self.gabaritos)
        return self.gabaritos[self.gabarito_atual]

    def dar_dica(self, palavra: str, numero: int) -> None:
        """Registra uma nova dica e atualiza o número de tentativas"""
        self.dica_atual = (palavra, numero)
        self.tentativas_restantes = numero + 1
        self.historico_dicas.append((self.turno_atual, palavra, numero))

    def fazer_jogada(self, idx: int) -> bool:
        """Processa uma jogada no índice especificado"""
        if idx >= len(self.palavras) or self.game_over:
            return False

        palavra = self.palavras[idx]
        if palavra in self.reveladas:
            return False

        self.reveladas.add(palavra)
        gabarito_atual = self.gabaritos[self.gabarito_atual]
        cor_revelada = gabarito_atual.mapa[idx]

        if cor_revelada == 'ASSASSINO':
            self.game_over = True
            self.vencedor = 'VERMELHO' if self.turno_atual == 'AZUL' else 'AZUL'
            return True

        if cor_revelada in ['AZUL', 'VERMELHO']:
            self.pontuacao[cor_revelada] += 1

        if cor_revelada != self.turno_atual:
            self.tentativas_restantes = 0
        else:
            self.tentativas_restantes -= 1

        if self.tentativas_restantes <= 0:
            self.trocar_turno()

        self.verificar_vitoria()
        return True

    def trocar_turno(self) -> None:
        """Troca o turno atual entre as equipes"""
        self.turno_atual = 'VERMELHO' if self.turno_atual == 'AZUL' else 'AZUL'
        self.dica_atual = None
        self.tentativas_restantes = 0

    def verificar_vitoria(self) -> None:
        """Verifica se alguma equipe atingiu as condições de vitória"""
        gabarito_atual = self.gabaritos[self.gabarito_atual]
        total_palavras = gabarito_atual.template['distribuicao']
        
        for cor in ['AZUL', 'VERMELHO']:
            if self.pontuacao[cor] >= total_palavras[cor]:
                self.game_over = True
                self.vencedor = cor

def get_palavra_style(cor: str) -> str:
    """Retorna o estilo CSS para cada tipo de palavra"""
    estilos = {
        'VERMELHO': """
            background-color: #ff4b4b;
            color: white;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            margin: 2px;
            font-weight: bold;
        """,
        'AZUL': """
            background-color: #4b4bff;
            color: white;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            margin: 2px;
            font-weight: bold;
        """,
        'NEUTRO': """
            background-color: #d3d3d3;
            color: black;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            margin: 2px;
        """,
        'ASSASSINO': """
            background-color: #000000;
            color: white;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            margin: 2px;
            font-weight: bold;
        """
    }
    return estilos.get(cor, '')

def interface_spymaster(col_spymaster, game: CodenamesGame) -> None:
    """Interface para o Spymaster"""
    with col_spymaster:
        st.markdown("### 🕵️ Spymaster View")
        
        st.markdown("### Selecione o Gabarito")
        gabarito_idx = st.radio(
            "Gabarito:",
            options=[1, 2, 3],
            key="gabarito_selection",
            horizontal=True
        )
        
        if gabarito_idx - 1 != game.gabarito_atual:
            game.gabarito_atual = gabarito_idx - 1
        
        if st.checkbox("Mostrar mapa do Spymaster", key="spymaster_view"):
            gabarito_atual = game.gabaritos[game.gabarito_atual]
            st.markdown(f"Primeiro jogador: {gabarito_atual.primeiro_jogador}")
            
            for i in range(5):
                cols = st.columns(5)
                for j in range(5):
                    idx = i * 5 + j
                    palavra = game.palavras[idx]
                    cor = gabarito_atual.mapa[idx]
                    style = get_palavra_style(cor)
                    cols[j].markdown(
                        f"<div style='{style}'>{palavra}</div>",
                        unsafe_allow_html=True
                    )

        with st.form("dar_dica"):
            st.markdown(f"### Dar dica para time {game.turno_atual}")
            dica = st.text_input("Palavra-dica:")
            numero = st.number_input(
                "Número de palavras relacionadas:",
                min_value=0,
                max_value=9
            )
            
            if st.checkbox("Ver sugestões de dicas"):
                st.markdown("Sugestões baseadas nas palavras não reveladas:")
                # Aqui você pode implementar um sistema de sugestões de dicas
            
            submitted = st.form_submit_button("Dar dica")
            if submitted and dica and numero >= 0:
                game.dar_dica(dica, numero)

def interface_tabuleiro(col_tabuleiro, game: CodenamesGame) -> Optional[int]:
    """Interface principal do tabuleiro de jogo"""
    with col_tabuleiro:
        st.markdown("### 🎮 Código Secreto - Edição Redação")
        
        st.markdown(f"### Turno: {game.turno_atual}")
        if game.dica_atual:
            st.markdown(f"""
            ### Dica atual: {game.dica_atual[0]} ({game.dica_atual[1]})
            Tentativas restantes: {game.tentativas_restantes}
            """)

        # Grade do tabuleiro
        for i in range(5):
            cols = st.columns(5)
            for j in range(5):
                idx = i * 5 + j
                palavra = game.palavras[idx]
                
                if palavra in game.reveladas:
                    cor = game.gabaritos[game.gabarito_atual].mapa[idx]
                    style = get_palavra_style(cor)
                    cols[j].markdown(
                        f"<div style='{style}'>{palavra}</div>",
                        unsafe_allow_html=True
                    )
                else:
                    button_style = """
                    <style>
                    div.stButton > button:hover {
                        background-color: #f0f0f0;
                        border-color: #cccccc;
                    }
                    div.stButton > button {
                        width: 100%;
                        padding: 10px 5px;
                        text-align: center;
                        font-size: 0.9em;
                    }
                    </style>
                    """
                    st.markdown(button_style, unsafe_allow_html=True)
                    if cols[j].button(palavra, key=f"btn_{idx}"):
                        return idx
    return None

def interface_status(col_status, game: CodenamesGame) -> None:
    """Interface de status e estatísticas do jogo"""
    with col_status:
        st.markdown("### 📊 Status do Jogo")
        
        gabarito_atual = game.gabaritos[game.gabarito_atual]
        total_palavras = gabarito_atual.template['distribuicao']
        
        # Pontuação
        st.markdown(f"""
        🔵 Time Azul: {game.pontuacao['AZUL']}/{total_palavras['AZUL']}
        🔴 Time Vermelho: {game.pontuacao['VERMELHO']}/{total_palavras['VERMELHO']}
        """)
        
        # Barras de progresso
        azul_progress = game.pontuacao['AZUL'] / total_palavras['AZUL']
        vermelho_progress = game.pontuacao['VERMELHO'] / total_palavras['VERMELHO']
        
        st.progress(azul_progress)
        st.progress(vermelho_progress)
        
        # Histórico de dicas
        st.markdown("### 📝 Histórico de Dicas")
        for time, dica, numero in game.historico_dicas:
            cor = '🔵' if time == 'AZUL' else '🔴'
            st.markdown(f"{cor} {dica} ({numero})")
        
        # Estatísticas
        st.markdown("### 📈 Estatísticas")
        palavras_restantes = 25 - len(game.reveladas)
        st.markdown(f"Palavras restantes: {palavras_restantes}")
        
        # Timer opcional
        if st.checkbox("Ativar timer"):
            timer = st.empty()
            if 'tempo_inicio' not in st.session_state:
                st.session_state.tempo_inicio = time.time()
            
            tempo_passado = int(time.time() - st.session_state.tempo_inicio)
            timer.markdown(f"⏱️ Tempo: {tempo_passado//60}:{tempo_passado%60:02d}")

def main():
    """Função principal que controla o fluxo do jogo"""
    st.set_page_config(
        layout="wide",
        page_title="Codenames - Redação",
        page_icon="🎯"
    )

    # Inicialização do estado do jogo
    if 'game' not in st.session_state:
        st.session_state.game = CodenamesGame()

    st.title("🎯 Código Secreto - Edição Redação")
    st.markdown("""
    ---
    #### Como jogar:
    1. O Spymaster dá uma dica relacionada a uma ou mais palavras de sua equipe
    2. Os jogadores tentam adivinhar as palavras baseadas na dica
    3. Evite as palavras do time adversário e a palavra assassina!
    """)
    st.markdown("---")

    # Layout principal com três colunas
    col_spymaster, col_tabuleiro, col_status = st.columns([1, 2, 1])
    
    game = st.session_state.game

    if not game.game_over:
        # Interface do jogo ativo
        interface_spymaster(col_spymaster, game)
        jogada = interface_tabuleiro(col_tabuleiro, game)
        interface_status(col_status, game)

        if jogada is not None and game.dica_atual:
            if game.fazer_jogada(jogada):
                st.experimental_rerun()
    else:
        # Tela de fim de jogo
        st.markdown(f"""
        # 🏆 Jogo encerrado!
        ### Vencedor: {'🔵 Time Azul' if game.vencedor == 'AZUL' else '🔴 Time Vermelho'}
        """)
        
        # Estatísticas finais
        st.markdown("### 📊 Estatísticas finais")
        st.markdown(f"""
        - Total de rodadas: {len(game.historico_dicas)}
        - Palavras reveladas: {len(game.reveladas)}/25
        - Pontuação final: 
            - 🔵 Azul: {game.pontuacao['AZUL']}
            - 🔴 Vermelho: {game.pontuacao['VERMELHO']}
        """)
        
        # Botão de novo jogo
        if st.button("🔄 Novo Jogo"):
            st.session_state.game = CodenamesGame()
            if 'tempo_inicio' in st.session_state:
                del st.session_state.tempo_inicio
            st.experimental_rerun()

        # Mostrar tabuleiro final
        st.markdown("### Tabuleiro Final")
        gabarito_final = game.gabaritos[game.gabarito_atual]
        for i in range(5):
            cols = st.columns(5)
            for j in range(5):
                idx = i * 5 + j
                palavra = game.palavras[idx]
                cor = gabarito_final.mapa[idx]
                style = get_palavra_style(cor)
                cols[j].markdown(
                    f"<div style='{style}'>{palavra}</div>",
                    unsafe_allow_html=True
                )

    # Footer com informações adicionais
    st.markdown("---")
    st.markdown("""
    #### 📝 Sobre o jogo
    Esta é uma versão educacional do Codenames, focada em vocabulário e conceitos de redação.
    Desenvolvido para fins educacionais.
    """)

if __name__ == "__main__":
    main()
