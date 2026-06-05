# Guia De Instalacao Em VM/VPS

Este guia descreve a primeira subida controlada da aplicacao em uma VM/VPS, priorizando estabilidade operacional antes da liberacao para usuarios.

## Recomendacao Inicial

Para este projeto, a recomendacao e:

1. usar `Linux Server`
2. preferencialmente `Ubuntu Server` ou `Debian`
3. usar `Python 3.11`
4. manter codigo e dados em caminhos separados

Exemplo de estrutura:

```text
/opt/domain-guard/app
/opt/domain-guard/data
```

## Pre-Requisitos

1. Python `3.11`
2. `pip`
3. acesso de escrita ao diretorio de dados
4. porta de aplicacao liberada internamente
5. `Tesseract OCR` apenas se houver necessidade de OCR em PDF escaneado

## Estrutura De Dados Persistentes

O diretorio apontado por `DOMAIN_GUARD_DATA_DIR` deve preservar:

1. `base/`
2. `output/`
3. `uploads/`
4. `audits/`
5. `logs/`
6. `backups/`

## Passo A Passo Linux

1. copiar o projeto para a VM
2. criar o diretorio de dados persistentes
3. criar o ambiente virtual
4. instalar dependencias
5. configurar variaveis de ambiente
6. subir com `waitress`

Exemplo:

```bash
mkdir -p /opt/domain-guard/app
mkdir -p /opt/domain-guard/data
cd /opt/domain-guard/app
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
export DOMAIN_GUARD_HOST=0.0.0.0
export DOMAIN_GUARD_PORT=5000
export DOMAIN_GUARD_DATA_DIR=/opt/domain-guard/data
python -m waitress --host=0.0.0.0 --port=5000 wsgi:app
```

## Passo A Passo Windows Server

Se a escolha for Windows Server, o fluxo minimo e:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:DOMAIN_GUARD_HOST = "0.0.0.0"
$env:DOMAIN_GUARD_PORT = "5000"
$env:DOMAIN_GUARD_DATA_DIR = "C:\DomainGuard\data"
python -m waitress --host=0.0.0.0 --port=5000 wsgi:app
```

## Variaveis De Ambiente Minimas

1. `DOMAIN_GUARD_HOST`
2. `DOMAIN_GUARD_PORT`
3. `DOMAIN_GUARD_DATA_DIR`

Variaveis adicionais uteis:

1. `DOMAIN_GUARD_MAX_FILE_SIZE`
2. `DOMAIN_GUARD_ENABLE_OCR`
3. `DOMAIN_GUARD_OCR_ONLY_IF_NO_DOMAINS`
4. `DOMAIN_GUARD_OCR_LANGUAGE`
5. `DOMAIN_GUARD_RETENTION_RUN_DAYS`
6. `DOMAIN_GUARD_RETENTION_UPLOAD_DAYS`
7. `DOMAIN_GUARD_RETENTION_BACKUP_DAYS`
8. `DOMAIN_GUARD_RETENTION_UPDATED_BASE_DAYS`

## Politica Inicial De Retencao

Recomendacao inicial para a primeira VM/VPS:

1. `output/runs/`: `30` dias
2. `uploads/`: `14` dias
3. `backups/`: `90` dias
4. `output/base_atualizada_*.txt`: `30` dias

Arquivos que nao devem entrar na limpeza automatica inicial:

1. `base/base_atual.txt`
2. `base/base_rejeitados.txt`
3. `audits/auditoria.db`
4. `logs/app.log`

## Limpeza Manual

O projeto agora possui um utilitario simples de limpeza:

Linux:

```bash
.venv/bin/python cleanup.py
```

Windows:

```powershell
.\.venv\Scripts\python.exe cleanup.py
```

Em ambiente Linux, esse comando pode ser agendado depois com `cron`, mas inicialmente a recomendacao e executar manualmente ate validar bem a operacao.

## Checklist De Validacao Pos-Instalacao

1. a aplicacao sobe sem erro
2. o acesso HTTP responde no host/porta configurados
3. os diretorios operacionais foram criados
4. `base/base_atual.txt` existe
5. um `.txt` simples pode ser processado
6. os artefatos saem em `output/runs/<run_id>/`
7. a auditoria grava em `audits/auditoria.db`
8. a confirmacao da base gera backup em `backups/`

## Checklist Operacional Minimo

Antes de considerar a VM pronta para a proxima etapa:

1. rodar `python -m unittest discover -s tests`
2. testar upload de `TXT`
3. testar upload de `PDF`
4. testar download de artefatos
5. testar confirmacao da base
6. revisar `logs/app.log`
7. revisar `audits/auditoria.db`

## O Que Fazer Em Caso De Erro

1. verificar `logs/app.log`
2. verificar se o usuario do processo tem permissao de escrita no `DOMAIN_GUARD_DATA_DIR`
3. confirmar se a porta configurada esta liberada
4. validar se o Python correto esta ativo
5. confirmar se `Flask`, `waitress` e as dependencias do projeto estao instaladas no ambiente virtual
6. em caso de falha de OCR, validar a instalacao do `Tesseract`

## Observacao Importante

Esta etapa ainda e de preparacao de ambiente. Mesmo que a aplicacao ja rode via rede interna, isso nao significa que ela esteja pronta para uso compartilhado por usuarios finais sem as proximas camadas de controle.
