# Domain Guard

Aplicacao web em Python para extrair dominios e alvos especificos de arquivos `TXT` e `PDF`, comparar contra uma base local, separar o que deve ser protegido em whitelist e preparar os novos alvos para incremento manual na base operacional.

Este README foi reorganizado para servir como documento de continuidade do projeto.

## Intuito Do Projeto

O sistema existe para reduzir trabalho manual em um fluxo operacional de analise de dominios.

Fluxo principal:

1. receber um ou mais arquivos de entrada
2. extrair dominios e URLs especificas mesmo quando o material vier com ruido de OCR ou quebra de layout
3. comparar os resultados com a base atual de referencias ja conhecidas
4. separar o que ja existe, o que deve ir para whitelist e o que deve virar novo alvo de bloqueio
5. permitir revisao manual antes de atualizar a base
6. gerar auditoria, artefatos e backup da base antes da confirmacao

O projeto nao foi pensado como produto publico. O uso esperado e interno e controlado.

## Estado Atual

No momento, o projeto esta em um ponto bom para:

1. execucao local
2. subida em VM para uso individual controlado
3. testes manuais do fluxo completo

Ainda nao esta maduro para uso compartilhado sem camadas adicionais de:

1. login
2. perfis de acesso
3. auditoria por usuario
4. rotina operacional formal

## Stack Tecnica

Backend:

1. Python 3.11
2. Flask
3. Waitress para subida WSGI

Extracao:

1. PyMuPDF
2. pdfplumber
3. pytesseract
4. Pillow

Persistencia e rastreabilidade:

1. arquivos em disco
2. SQLite para historico e dominios rejeitados

Frontend:

1. HTML
2. CSS
3. JavaScript vanilla

## Estrutura Do Projeto

```text
Extrator_e_comparador_dominios/
├── app.py
├── wsgi.py
├── config.py
├── processing.py
├── cleanup.py
├── requirements.txt
├── setup.ps1
├── iniciar_plataforma.ps1
├── iniciar_plataforma.bat
├── README.md
├── ARCHITECTURE.md
├── INSTALL_VM.md
├── GUIA_EVOLUCAO_VM_E_LIBERACAO.txt
├── domain_processing/
│   ├── __init__.py
│   ├── audit.py
│   ├── classification.py
│   ├── extraction.py
│   ├── models.py
│   ├── outputs.py
│   ├── pipeline.py
│   └── runtime.py
├── templates/
│   └── index.html
├── static/
│   ├── app.js
│   └── styles.css
├── tests/
│   ├── test_app_audit_history.py
│   ├── test_app_factory.py
│   ├── test_app_routes.py
│   ├── test_cleanup.py
│   ├── test_config.py
│   ├── test_directories.py
│   ├── test_processing.py
│   └── test_runtime_validation.py
├── base/
│   ├── base_atual.txt
│   ├── base_rejeitados.txt
│   └── correcoes_manuais.txt
├── fixtures/
├── uploads/
├── output/
├── logs/
├── audits/
└── backups/
```

## O Papel De Cada Arquivo Principal

### `app.py`

Camada HTTP.

Responsabilidades:

1. criar a aplicacao Flask
2. validar configuracao de runtime
3. inicializar logging e banco SQLite
4. receber uploads
5. chamar o pipeline de processamento
6. confirmar atualizacao da base
7. expor downloads e historico de auditoria

Rotas principais:

1. `/`
2. `/process`
3. `/download/<name>`
4. `/confirm-update`
5. `/whitelist`
6. `/audit-history`

### `wsgi.py`

Ponto de entrada simples para subir com `waitress`.

### `config.py`

Centraliza a configuracao por variaveis de ambiente com prefixo `DOMAIN_GUARD_`.

Tambem define os caminhos operacionais e politicas de retencao.

### `processing.py`

Arquivo de compatibilidade que reexporta funcoes do pacote `domain_processing`.

### `cleanup.py`

Responsavel pela limpeza manual de artefatos antigos como:

1. `output/runs/`
2. `uploads/`
3. `backups/`
4. arquivos `base_atualizada_*.txt`

## Pacote `domain_processing`

### `extraction.py`

Responsavel por:

1. normalizacao de dominios
2. leitura de `TXT`
3. leitura de `PDF`
4. heuristicas para reconstruir dominios quebrados por layout
5. OCR opcional
6. carregamento da base atual
7. aplicacao de correcoes manuais

### `classification.py`

Responsavel por:

1. regras de whitelist
2. separacao entre whitelist e blocklist
3. descarte de entradas que ja existem na base

### `pipeline.py`

Orquestra o fluxo principal.

Passos:

1. extracao paralela por arquivo
2. consolidacao dos resultados
3. comparacao com a base
4. classificacao
5. geracao de artefatos
6. escrita do manifesto da execucao

### `outputs.py`

Responsavel por:

1. gerar `novos_dominios.txt`
2. gerar `whitelist.txt`
3. gerar `relatorio.txt`
4. salvar `pendente_atualizacao.json`
5. confirmar a atualizacao da base
6. gravar backup da base
7. registrar dominios rejeitados

### `runtime.py`

Responsavel por:

1. gerar `run_id`
2. definir caminhos por execucao
3. ler e gravar manifesto
4. controlar lock de atualizacao da base

### `audit.py`

Le historico da auditoria no SQLite para alimentar a interface.

### `models.py`

Modelos simples de dados usados no fluxo de extracao.

## Diretorios Operacionais

Estes diretorios precisam existir e ser persistidos entre reinicios, principalmente em VM:

1. `base/`
2. `uploads/`
3. `output/`
4. `audits/`
5. `logs/`
6. `backups/`

Descricao rapida:

1. `base/`: arquivos mestres da operacao
2. `uploads/`: arquivos enviados em cada execucao
3. `output/`: saidas mais recentes e pasta `runs/`
4. `audits/`: banco SQLite `auditoria.db`
5. `logs/`: `app.log`
6. `backups/`: copias da base antes das confirmacoes

## Fluxo Funcional

### 1. Upload

O usuario envia arquivos `TXT` e `PDF` pela interface.

### 2. Extracao

Cada arquivo e processado separadamente.

Regras importantes:

1. `TXT` usa parser mais estrito
2. `PDF` usa parser mais tolerante a ruido visual
3. OCR e opcional
4. o motor tenta reconstruir dominios quebrados por linha ou layout

### 3. Comparacao

Os dominios extraidos sao comparados com `base/base_atual.txt`.

### 4. Classificacao

O sistema separa:

1. dominios que ja existem na base
2. dominios que devem ser protegidos em whitelist
3. dominios novos para bloqueio

### 5. Artefatos

Cada execucao gera artefatos por `run_id` em `output/runs/<run_id>/`.

Arquivos esperados:

1. `novos_dominios.txt`
2. `whitelist.txt`
3. `relatorio.txt`
4. `pendente_atualizacao.json`
5. `manifest.json`

### 6. Confirmacao Manual

A base so e atualizada depois da aprovacao manual.

Ao confirmar:

1. o sistema faz backup da base
2. registra rejeicoes
3. grava uma versao `base_atualizada_*.txt`
4. atualiza `base/base_atual.txt`

## Interface Web

Arquivos:

1. `templates/index.html`
2. `static/app.js`
3. `static/styles.css`

A interface atual permite:

1. upload multiplo
2. acompanhamento do processamento
3. visualizacao dos novos alvos
4. visualizacao da whitelist
5. confirmacao manual da atualizacao
6. download dos artefatos
7. consulta ao historico de auditoria

## Configuracao Por Ambiente

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
15. `DOMAIN_GUARD_SESSION_COOKIE_SECURE` (default `true`; exige HTTPS para o cookie de sessao)
16. `DOMAIN_GUARD_LOGIN_MAX_ATTEMPTS` (default `3`)
17. `DOMAIN_GUARD_LOGIN_LOCKOUT_MINUTES` (default `15`)

Recomendacao para VM:

1. codigo em uma pasta
2. dados operacionais em outra pasta
3. `DOMAIN_GUARD_DATA_DIR` apontando para a pasta persistente de dados

Exemplo conceitual em Linux:

```text
/opt/domain-guard/app
/opt/domain-guard/data
```

## Como Executar Localmente

### Instalacao

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Ou:

```powershell
.\setup.ps1
```

### Desenvolvimento Local

```powershell
python app.py
```

Por padrao o cookie de sessao exige HTTPS (`SESSION_COOKIE_SECURE=True`). Para testar localmente via `http://` (sem TLS), defina `DOMAIN_GUARD_SESSION_COOKIE_SECURE=false` antes de subir a aplicacao, senao o login nao persiste entre requisicoes.

### Subida Recomendada Em Servidor Ou VM

```powershell
python -m waitress --host=0.0.0.0 --port=5000 wsgi:app
```

## OCR

OCR depende de `Tesseract` instalado no sistema.

Importante:

1. se o PDF ja entregar texto suficiente, o OCR pode ser ignorado
2. se o PDF for escaneado, o resultado pode depender diretamente do Tesseract
3. sem Tesseract, o restante do sistema continua funcionando, mas PDFs dependentes de OCR podem falhar

## Testes

Suite atual cobre:

1. extracao e normalizacao
2. confirmacao da base
3. artefatos por execucao
4. rotas principais
5. limpeza de artefatos
6. validacao de configuracao
7. historico de auditoria

Comando:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## Documentos Importantes Do Projeto

1. `ARCHITECTURE.md`: divisao em camadas e direcao tecnica
2. `INSTALL_VM.md`: guia de instalacao em VM/VPS
3. `GUIA_EVOLUCAO_VM_E_LIBERACAO.txt`: backlog e criterios para evolucao antes de liberar para mais usuarios

## Pontos De Atencao Para Continuidade

Para quem for assumir o projeto, os pontos mais importantes hoje sao:

1. manter a estabilidade do motor de extracao
2. aumentar regressao com casos reais de PDF problematico
3. revisar o comportamento de OCR em ambiente de VM
4. preservar a atualizacao manual da base como etapa segura
5. nao liberar uso compartilhado sem login e auditoria por usuario

## Handoff Para Continuidade Com Claude

Se outra IA ou outro desenvolvedor for continuar o trabalho, o melhor ponto de entrada e:

1. ler este `README.md`
2. ler `ARCHITECTURE.md`
3. ler `INSTALL_VM.md`
4. ler `GUIA_EVOLUCAO_VM_E_LIBERACAO.txt`
5. revisar `app.py` e o pacote `domain_processing/`
6. executar a suite de testes

Sequencia recomendada de entendimento do codigo:

1. `app.py`
2. `domain_processing/pipeline.py`
3. `domain_processing/extraction.py`
4. `domain_processing/classification.py`
5. `domain_processing/outputs.py`
6. `tests/test_processing.py`

## Resumo Final

O projeto e uma plataforma interna para extracao, comparacao, revisao e consolidacao manual de dominios.

Hoje ele ja tem:

1. fluxo funcional principal
2. configuracao por ambiente
3. rastreabilidade por execucao
4. testes automatizados relevantes
5. base tecnica suficiente para rodar em VM

Os proximos passos naturais sao:

1. consolidar uso em VM com testes manuais reais
2. endurecer ainda mais a regressao com PDFs reais
3. so depois disso adicionar login, perfis e auditoria por usuario para uso compartilhado
