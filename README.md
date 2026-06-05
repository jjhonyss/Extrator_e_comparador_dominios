# Plataforma Local de Processamento de Dominios

Aplicacao web local para extrair dominios de arquivos `TXT` e `PDF`, comparar com a base atual, separar o que ja existe, gerar novos dominios para bloqueio e proteger apenas dominios explicitamente previstos em whitelist.

## Objetivo

O projeto foi desenhado para automatizar o fluxo abaixo:

1. Adicionar arquivos novos.
2. Extrair dominios com tratamento de ruido real de `TXT` e `PDF`.
3. Comparar com `base/base_atual.txt`.
4. Gerar um `.txt` final com os novos dominios para incremento no servidor.
5. Atualizar a base local somente apos confirmacao manual.

## Recursos

1. Upload multiplo de arquivos `.txt` e `.pdf`.
2. Processamento por execucao com `run_id` proprio.
3. Extracao paralela por arquivo.
4. Extracao de `PDF` com `PyMuPDF`, fallback com `pdfplumber` e OCR opcional.
5. Parser de `TXT` mais estrito e parser de `PDF` mais tolerante a ruido visual.
6. Comparacao contra a base atual para descartar dominios ja existentes.
7. Whitelist estrita para dominios oficiais e padroes explicitamente protegidos.
8. Geracao de artefatos por execucao em `output/runs/<run_id>/`.
9. Auditoria em log local e SQLite em `audits/auditoria.db`.
10. Confirmacao manual para atualizar `base/base_atual.txt` com lock de seguranca.

## Comportamento Atual do Motor

### Regras de classificacao

1. Apenas dominios e padroes explicitamente definidos em whitelist sao protegidos.
2. Palavras como `bank`, `banco`, `faculdade` e similares nao colocam mais dominio em whitelist por si so.
3. Todo dominio novo que nao bater em regra legitima de whitelist vai para bloqueio.

### Diferenca entre `TXT` e `PDF`

1. `TXT`:
   - parser mais estrito
   - linhas com separadores invalidos como `|` sao ignoradas

2. `PDF`:
   - parser mais tolerante
   - tenta recompor dominios quebrados por layout
   - evita colar dois dominios validos completos
   - trata melhor fragmentacoes como:
     - `softoni` + `c.com.br`
     - `catalog.k` + `yte.site`
     - `storage-usa-sv07-` + `user....workers.dev`

### Comparacao com a base

1. O motor compara contra `base/base_atual.txt`.
2. A leitura da base esta mais estrita para nao deixar entradas malformadas contaminarem a comparacao.
3. O projeto hoje preserva `www.` como parte do dominio, ou seja, `www.site.com` e `site.com` sao tratados como entradas diferentes.

## Estrutura

```text
Extrator_e_comparador_dominios/
├── app.py
├── config.py
├── processing.py
├── README.md
├── ARCHITECTURE.md
├── requirements.txt
├── setup.ps1
├── iniciar_plataforma.ps1
├── iniciar_plataforma.bat
├── domain_processing/
│   ├── __init__.py
│   ├── classification.py
│   ├── extraction.py
│   ├── models.py
│   ├── outputs.py
│   ├── pipeline.py
│   └── runtime.py
├── audits/
├── backups/
├── base/
│   └── base_atual.txt
├── fixtures/
├── logs/
├── output/
│   └── runs/
├── static/
│   ├── app.js
│   └── styles.css
├── templates/
│   └── index.html
├── tests/
│   └── test_processing.py
└── uploads/
```

## Instalacao

Requisitos:

1. Python 3.11 recomendado.
2. `Tesseract OCR` instalado se quiser OCR em PDFs escaneados.
3. `Poppler` nao e obrigatorio.

Instalacao automatica:

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

Guia recomendado para primeira subida em VM/VPS:

1. `INSTALL_VM.md`

## Configuracao por Ambiente

O projeto continua funcionando com os defaults atuais, mas agora pode ser configurado por variaveis de ambiente com prefixo `DOMAIN_GUARD_`.

Variaveis principais:

1. `DOMAIN_GUARD_HOST`
2. `DOMAIN_GUARD_PORT`
3. `DOMAIN_GUARD_DATA_DIR`
4. `DOMAIN_GUARD_UPLOAD_DIR`
5. `DOMAIN_GUARD_OUTPUT_DIR`
6. `DOMAIN_GUARD_AUDIT_DIR`
7. `DOMAIN_GUARD_LOG_DIR`
8. `DOMAIN_GUARD_BACKUP_DIR`
9. `DOMAIN_GUARD_BASE_FILE_PATH`
10. `DOMAIN_GUARD_REJECTED_FILE_PATH`
11. `DOMAIN_GUARD_MAX_FILE_SIZE`
12. `DOMAIN_GUARD_ENABLE_OCR`
13. `DOMAIN_GUARD_OCR_ONLY_IF_NO_DOMAINS`
14. `DOMAIN_GUARD_OCR_LANGUAGE`
15. `DOMAIN_GUARD_RETENTION_RUN_DAYS`
16. `DOMAIN_GUARD_RETENTION_UPLOAD_DAYS`
17. `DOMAIN_GUARD_RETENTION_BACKUP_DAYS`
18. `DOMAIN_GUARD_RETENTION_UPDATED_BASE_DAYS`

Exemplo PowerShell:

```powershell
$env:DOMAIN_GUARD_HOST = "0.0.0.0"
$env:DOMAIN_GUARD_PORT = "5000"
$env:DOMAIN_GUARD_DATA_DIR = "C:\DomainGuard\data"
python app.py
```

## Diretorios Operacionais

Para uso em VM/VPS, o ideal e tratar `DOMAIN_GUARD_DATA_DIR` como raiz persistente dos dados operacionais.

Estrutura padrao:

```text
<data_dir>/
├── audits/
├── backups/
├── base/
├── logs/
├── output/
│   └── runs/
└── uploads/
```

O que precisa persistir entre reinicios:

1. `base/`
2. `audits/`
3. `backups/`
4. `logs/`
5. `output/`
6. `uploads/`

Recomendacao pratica para servidor:

1. codigo da aplicacao em uma pasta de deploy
2. dados operacionais em outra pasta persistente, por exemplo `/opt/domain-guard/data` no Linux
3. configurar `DOMAIN_GUARD_DATA_DIR` apontando para essa pasta

Exemplo conceitual:

```text
/opt/domain-guard/app
/opt/domain-guard/data
```

Ao iniciar, a aplicacao agora garante a criacao dos diretorios pais necessarios para base, logs, auditoria, backups, saidas e arquivos por execucao.

## Uso

1. Coloque a base atual em `base/base_atual.txt`.
2. Execute `iniciar_plataforma.bat` ou rode manualmente:

```powershell
python app.py
```

3. Acesse `http://127.0.0.1:5000` ou o host/porta configurados por ambiente.
4. Envie um ou mais arquivos `.txt` ou `.pdf`.
5. Revise o resultado da execucao.
6. Baixe os artefatos gerados.
7. Se estiver correto, confirme a atualizacao da base pela interface.

Observacao: abrir `templates/index.html` diretamente no navegador nao executa a aplicacao. O processamento depende do servidor Flask local.

## Execucao Em Servidor

Para ambiente de servidor, a recomendacao agora e usar um servidor WSGI em vez de depender de `python app.py`.

Instale as dependencias:

```powershell
pip install -r requirements.txt
```

Subida recomendada com `waitress`:

```powershell
python -m waitress --host=0.0.0.0 --port=5000 wsgi:app
```

Ou usando as variaveis de ambiente ja suportadas:

```powershell
$env:DOMAIN_GUARD_HOST = "0.0.0.0"
$env:DOMAIN_GUARD_PORT = "5000"
python -m waitress --host=$env:DOMAIN_GUARD_HOST --port=$env:DOMAIN_GUARD_PORT wsgi:app
```

Arquivos de entrada para servidor:

1. `app.py`: aplicacao Flask
2. `wsgi.py`: ponto de entrada para servidor WSGI

`python app.py` continua util para desenvolvimento local e validacao rapida.

## Checklist Rapido Antes Da VM

1. Validar a suite de testes com `python -m unittest discover -s tests`
2. Confirmar que o fluxo local continua funcional com `TXT` e `PDF`
3. Definir o `DOMAIN_GUARD_DATA_DIR` persistente no servidor
4. Separar pasta de codigo e pasta de dados operacionais
5. Garantir acesso de escrita em `base/`, `output/`, `uploads/`, `audits/`, `logs/` e `backups/`
6. Definir host e porta de subida
7. Subir a aplicacao com `waitress`
8. Validar acesso HTTP pela rede esperada
9. Testar processamento, download e confirmacao da base no ambiente alvo

## Retencao E Limpeza

Politica inicial recomendada:

1. `output/runs/`: manter `30` dias
2. `uploads/`: manter `14` dias
3. `backups/`: manter `90` dias
4. `output/base_atualizada_*.txt`: manter `30` dias

Esses valores podem ser ajustados por ambiente com:

1. `DOMAIN_GUARD_RETENTION_RUN_DAYS`
2. `DOMAIN_GUARD_RETENTION_UPLOAD_DAYS`
3. `DOMAIN_GUARD_RETENTION_BACKUP_DAYS`
4. `DOMAIN_GUARD_RETENTION_UPDATED_BASE_DAYS`

Limpeza manual:

```powershell
.\.venv\Scripts\python.exe cleanup.py
```

Para ambiente Linux:

```bash
.venv/bin/python cleanup.py
```

O script remove apenas:

1. diretorios antigos em `output/runs/`
2. diretorios antigos em `uploads/`
3. backups antigos em `backups/`
4. arquivos antigos `base_atualizada_*.txt`

Ele nao remove:

1. `base/base_atual.txt`
2. `base/base_rejeitados.txt`
3. `audits/auditoria.db`
4. `logs/app.log`

## Artefatos Gerados

### Saida global mais recente

1. `output/novos_dominios.txt`
2. `output/whitelist.txt`
3. `output/relatorio.txt`
4. `output/base_atualizada_YYYYMMDD_HHMMSS.txt`

### Saida por execucao

Cada processamento recebe um `run_id` e grava em:

```text
output/runs/<run_id>/
```

Arquivos principais:

1. `novos_dominios.txt`
2. `whitelist.txt`
3. `relatorio.txt`
4. `pendente_atualizacao.json`
5. `manifest.json`

## Rotas Principais

1. `GET /`
2. `POST /process`
3. `POST /confirm-update`
4. `GET /download/<name>`
5. `GET /whitelist`

`/confirm-update`, `/download/<name>` e `/whitelist` podem trabalhar com `run_id` para acessar artefatos especificos de uma execucao.

Para operacao em servidor, o fluxo recomendado e sempre usar os artefatos vinculados ao `run_id` da execucao atual. Os arquivos globais em `output/` permanecem apenas como fallback operacional e compatibilidade.

## OCR

Controlado por `config.py`:

1. `ENABLE_OCR`
2. `OCR_ONLY_IF_NO_DOMAINS`
3. `OCR_LANGUAGE`

Se o `Tesseract` nao estiver instalado, PDFs com texto nativo continuam funcionando. PDFs escaneados podem gerar aviso no relatorio.

## Seguranca Operacional

1. Nenhum arquivo e enviado para servicos externos.
2. A base principal so e atualizada apos confirmacao manual.
3. Existe lock para evitar duas atualizacoes simultaneas da base.
4. Cada execucao tem artefatos e manifesto proprios.
5. Toda execucao relevante e registrada em `logs/app.log` e `audits/auditoria.db`.
6. Um backup da base e criado antes da atualizacao em `backups/`.

## Testes

Execute:

```powershell
python -m unittest discover -s tests
```

Os testes hoje cobrem, entre outros pontos:

1. normalizacao de dominio
2. contagem sem duplicacao indevida
3. whitelist estrita
4. comparacao com a base
5. artefatos por execucao
6. regressao para dominios fragmentados em `PDF`
7. regressao para dominios colados indevidamente em `PDF`

## Observacoes Importantes

1. A base atual pode conter entradas historicas operacionais com porta ou path.
2. O motor atual tenta proteger a comparacao contra linhas malformadas antigas.
3. O parser de `PDF` foi sendo refinado em cima de casos reais do acervo; novos exemplos concretos ajudam a melhorar o motor sem relaxar demais as validacoes.
