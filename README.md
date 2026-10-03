# G41_Greedy_PA-26.2

Projeto base de um jogo de ação/sobrevivência em laboratório, com ambiente de coleta, interface da mochila e itens de substâncias. Este repositório representa a Parte 1 do trabalho: construção do cenário e da interface visual.

## Objetivo do projeto

- Criar uma sala de loot/laboratório com visual funcional.
- Definir um personagem principal com movimentação básica.
- Inserir substâncias espalhadas no ambiente.
- Exibir uma mochila com capacidade de peso/volume.
- Preparar a base para que a Pessoa 2 implemente o algoritmo da mochila fracionária.

## Como executar

1. Crie um ambiente virtual (opcional, mas recomendado):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Execute o jogo:
   ```bash
   python game.py
   ```

## Itens do cenário

Os itens abaixo já estão definidos na base visual do jogo:

- Soro Curativo
  - Peso: 1.5 kg
  - Valor: 18 pontos
  - Quantidade máxima disponível no cenário: 8

- Pólvora
  - Peso: 2.0 kg
  - Valor: 32 pontos
  - Quantidade máxima disponível no cenário: 6

- Combustível
  - Peso: 3.2 kg
  - Valor: 45 pontos
  - Quantidade máxima disponível no cenário: 5

## A estrutura da mochila

A mochila possui capacidade máxima de 7 kg e uma barra visual para indicar o peso atual carregado. Como os itens disponíveis somam 13,4 kg, o jogador precisa priorizar o que coletar.

## Pontuação e objetivo

Cada item coletado acrescenta seus pontos à pontuação. A mochila mostra o progresso até a meta de 100 pontos; atingir a meta representa vitória. O jogador perde quando, considerando os itens restantes e o espaço livre na mochila, não existe mais uma combinação capaz de alcançar 100 pontos.
