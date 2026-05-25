# Plataforma Local de Processamento de Dominios

Aplicacao web local para extrair, normalizar, comparar e classificar dominios a partir de arquivos `TXT` e `PDF`, com protecao automatica para dominios sensiveis via whitelist.

## Recursos

1. Upload multiplo de arquivos `.txt` e `.pdf`.
2. Extracao de dominios por regex com limpeza e deduplicacao.
3. Extracao de PDF otimizada com `PyMuPDF`, fallback com `pdfplumber` e OCR opcional com `Tesseract`.
4. Comparacao contra `base/base_atual.txt` para descartar dominios ja existentes.
5. Whitelist inteligente para bancos, governo, educacao, saude, seguranca e redes sociais.
6. Geracao de `output/base_atualizada_YYYYMMDD_HHMMSS.txt`, `output/novos_dominios.txt`, `output/whitelist.txt` e `output/relatorio.txt`.
7. Auditoria em log local e SQLite (`audits/auditoria.db`).
8. Interface responsiva com drag and drop, progresso de upload, modo escuro e downloads.

## Estrutura

```text
Extrator_e_comparador_dominios/
├── app.py
├── config.py
├── processing.py
├── requirements.txt
├── setup.ps1
├── audits/
├── backups/
├── base/
│   └── base_atual.txt
├── output/
├── templates/
│   └── index.html
├── static/
│   ├── app.js
│   └── styles.css
├── uploads/
└── tests/
    └── test_processing.py
```

## Instalacao

Requisitos:

1. Python 3.11 recomendado.
2. Tesseract OCR instalado no sistema se quiser OCR de PDFs escaneados.
3. Poppler nao e obrigatorio; o OCR usa renderizacao via PyMuPDF.

Instalacao automatica no PowerShell:

```powershell
.\setup.ps1
```

Instalacao manual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Uso

1. Coloque a base atual em `base/base_atual.txt`, um dominio por linha.
2. Forma mais simples: execute `iniciar_plataforma.bat` com duplo clique.

Ou execute manualmente:

```powershell
python app.py
```

3. Acesse `http://127.0.0.1:5000` se o navegador nao abrir automaticamente.
4. Arraste arquivos `.txt` ou `.pdf` para a area de upload.
5. Clique em `Processar arquivos`.
6. Baixe os resultados pela interface.

Observacao: abrir `templates/index.html` diretamente no navegador nao executa a aplicacao, porque upload, processamento, relatorios e downloads dependem do servidor Flask local.

## Arquivos Gerados

`output/base_atualizada_YYYYMMDD_HHMMSS.txt` contem a base completa com os novos dominios de bloqueio adicionados.

`output/novos_dominios.txt` contem apenas dominios novos e nao sensiveis para bloqueio.

`output/whitelist.txt` contem dominios novos protegidos pela whitelist, com categoria e justificativa.

`output/relatorio.txt` contem auditoria detalhada do processamento, erros, duplicatas e tempo de execucao.

## OCR

O OCR e controlado por `ENABLE_OCR` e `OCR_LANGUAGE` em `config.py`.

Se o Tesseract nao estiver instalado, PDFs com texto continuam funcionando. PDFs escaneados retornarao aviso no relatorio.

## Seguranca Operacional

1. Nenhum arquivo e enviado para servicos externos.
2. A base `base/base_atual.txt` so e atualizada apos confirmacao manual na interface.
3. Dominios sensiveis e borderline nao entram na lista de bloqueio.
4. Toda execucao relevante e registrada em `logs/app.log` e `audits/auditoria.db`.
5. Um backup da base e criado antes da atualizacao em `backups/`.

## Testes

Execute:

```powershell
python -m unittest discover -s tests
```

Os testes cobrem extracao de TXT, normalizacao, deduplicacao, comparacao, whitelist e geracao de relatorio.
