# Demonstração reproduzível

A demonstração usa exclusivamente `examples/SampleSuperstore.csv`, um dataset fictício versionado no repositório.

## Execução completa com Gemini

Com o projeto já instalado conforme o [Quick start](../README.md#quick-start):

```bash
gemini-terminal --config
gemini-terminal
```

Opcionalmente, habilite a timeline persistente com `/trace on` e envie:

```text
No arquivo examples/SampleSuperstore.csv, calcule o Profit total por Region.
Use analyze_sheet_data e apresente o resultado em ordem decrescente.
```

Critérios para uma execução correta:

1. o modelo chama `analyze_sheet_data`, em vez de calcular sobre linhas lidas;
2. a timeline informa início e conclusão da ferramenta;
3. a resposta apresenta quatro regiões e seus totais;
4. o rodapé informa modelo, chamadas, tokens, duração e cache.

Como a seleção e a redação dependem do modelo, textos e tokens podem variar. Os valores agregados devem permanecer consistentes com o CSV.

## Regenerando a imagem do README

O SVG é determinístico e não chama a API. O script executa diretamente a mesma função usada pela tool e renderiza o resultado com Rich:

```bash
python scripts/generate_demo_svg.py
```

A saída é `docs/assets/terminal-demo.svg`. Isso permite atualizar a imagem quando o visual mudar sem depender de credenciais, cota ou resposta probabilística do modelo.

## Sugestão para um GIF

1. use uma janela de aproximadamente 110 colunas;
2. comece no banner do terminal;
3. cole o prompt acima;
4. mantenha a timeline visível;
5. encerre depois da tabela e do rodapé;
6. não grave `.env`, caminhos pessoais ou logs reais.
