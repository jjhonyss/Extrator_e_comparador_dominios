# Arquitetura

## Objetivo

Organizar o processamento em camadas para permitir evolucao segura para:

1. Extracao concorrente de multiplos arquivos.
2. Comparacao agregada dos dominios extraidos em uma unica execucao.
3. Operacao com melhor rastreabilidade, isolamento por execucao e menos acoplamento.

## Camadas atuais

### `app.py`

Camada HTTP.

Responsavel por:

1. Receber uploads.
2. Validar extensoes.
3. Acionar o pipeline.
4. Retornar JSON e downloads.

### `domain_processing/extraction.py`

Camada de extracao e leitura.

Responsavel por:

1. Extrair dominios de TXT.
2. Extrair dominios de PDF.
3. OCR opcional.
4. Normalizacao.
5. Leitura da base.

### `domain_processing/classification.py`

Camada de classificacao.

Responsavel por:

1. Regras de whitelist.
2. Regras borderline.
3. Separacao entre blocklist e whitelist.
4. Descarte de dominios ja existentes.

### `domain_processing/outputs.py`

Camada de persistencia operacional.

Responsavel por:

1. Gerar relatorio.
2. Gerar arquivos de saida.
3. Salvar atualizacao pendente.
4. Confirmar atualizacao da base.
5. Backup da base.

### `domain_processing/pipeline.py`

Camada de orquestracao.

Responsavel por:

1. Executar a extracao dos arquivos.
2. Consolidar dominios.
3. Comparar com a base.
4. Disparar geracao de saidas.
5. Montar o resumo final.

## Direcao para concorrencia

### Estagio 1: extracao por arquivo em paralelo

Cada arquivo deve ser tratado como unidade independente de trabalho.

Fluxo:

1. Receber lista de arquivos.
2. Criar uma tarefa de extracao por arquivo.
3. Consolidar os resultados em memoria.
4. Somente depois comparar com a base.

Essa etapa e a mais segura para paralelizar porque cada arquivo e isolado.

### Estagio 2: consolidacao unica

A comparacao com a base deve ocorrer uma vez por execucao, apos a extracao de todos os arquivos.

Motivo:

1. Evita contagem duplicada entre arquivos diferentes.
2. Mantem o relatorio consistente.
3. Reduz disputa por escrita.

### Estagio 3: escrita serializada

As operacoes abaixo devem continuar serializadas:

1. Escrita de `pendente_atualizacao.json`.
2. Confirmacao da atualizacao da base.
3. Backup de base.
4. Escrita de `base/base_atual.txt`.

Concorrencia nessas etapas sem controle introduz risco real de corrida.

## Proximos passos recomendados

1. `run_id` por execucao para rastrear lote, artefatos e erros.
2. Artefatos isolados em `output/runs/<run_id>/`.
3. Extracao paralela por arquivo com consolidacao unica.
4. Lock em arquivo para serializar confirmacao da base.
5. Externalizar regras de whitelist para arquivo configuravel.
6. Adicionar testes de integracao da API e do pipeline concorrente.

## Decisao importante

O sistema pode processar varios arquivos em paralelo, mas a base principal nao deve ser atualizada em paralelo.

Isso nao e limitacao da arquitetura; e uma regra de seguranca operacional.
