# Deploy Em VPS

Este guia descreve o caminho recomendado para subir o projeto em uma VPS Linux usando `systemd` e `waitress`.

## Objetivo

Colocar a aplicacao no ar em uma VPS com:

1. codigo separado dos dados operacionais
2. ambiente virtual Python
3. variaveis de ambiente centralizadas
4. servico automatico no boot
5. logs e base persistidos em disco

## Estrutura Recomendada Na VPS

```text
/opt/domain-guard/app
/opt/domain-guard/data
```

Onde:

1. `/opt/domain-guard/app` guarda o codigo
2. `/opt/domain-guard/data` guarda base, logs, auditoria, uploads, backups e saidas

## Pacote Que Deve Ser Enviado Para A VPS

Use o arquivo zip de deploy gerado localmente neste projeto.

Ele contem:

1. codigo Python
2. templates
3. static
4. testes
5. arquivos de documentacao
6. exemplos de deploy em `deploy/`

## Passo A Passo Na VPS

### 1. Instalar pacotes do sistema

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip unzip
```

Se precisar de OCR:

```bash
sudo apt install -y tesseract-ocr tesseract-ocr-por tesseract-ocr-eng
```

## 2. Criar estrutura de pastas

```bash
sudo mkdir -p /opt/domain-guard/app
sudo mkdir -p /opt/domain-guard/data
sudo mkdir -p /opt/domain-guard/data/base
sudo mkdir -p /opt/domain-guard/data/uploads
sudo mkdir -p /opt/domain-guard/data/output
sudo mkdir -p /opt/domain-guard/data/audits
sudo mkdir -p /opt/domain-guard/data/logs
sudo mkdir -p /opt/domain-guard/data/backups
```

## 3. Enviar o pacote para a VPS

Exemplo com `scp` a partir da sua maquina:

```bash
scp domain_guard_vps_deploy.zip usuario@IP_DA_VPS:/tmp/
```

## 4. Extrair o projeto

```bash
cd /opt/domain-guard/app
sudo unzip /tmp/domain_guard_vps_deploy.zip -d /opt/domain-guard/app
```

Se o unzip criar uma pasta interna extra, mova o conteudo para `/opt/domain-guard/app`.

## 5. Criar ambiente virtual

```bash
cd /opt/domain-guard/app
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 6. Criar arquivo de ambiente

Copie o exemplo:

```bash
cp deploy/domain-guard.env.example /opt/domain-guard/app/.env.vps
```

Edite o arquivo:

```bash
nano /opt/domain-guard/app/.env.vps
```

## 7. Ajustar base inicial

Copie sua base real para:

```text
/opt/domain-guard/data/base/base_atual.txt
```

Se quiser levar tambem os rejeitados e correcoes:

1. `/opt/domain-guard/data/base/base_rejeitados.txt`
2. `/opt/domain-guard/data/base/correcoes_manuais.txt`

## 8. Testar subida manual

```bash
cd /opt/domain-guard/app
set -a
. ./.env.vps
set +a
. .venv/bin/activate
python -m waitress --host=0.0.0.0 --port=5000 wsgi:app
```

Se subir sem erro, teste no navegador:

```text
http://IP_DA_VPS:5000
```

## 9. Criar servico systemd

Copie o exemplo:

```bash
sudo cp /opt/domain-guard/app/deploy/domain-guard.service /etc/systemd/system/domain-guard.service
```

Recarregue e habilite:

```bash
sudo systemctl daemon-reload
sudo systemctl enable domain-guard
sudo systemctl start domain-guard
```

Verifique:

```bash
sudo systemctl status domain-guard
```

## 10. Liberar firewall

Se usar `ufw`:

```bash
sudo ufw allow 5000/tcp
sudo ufw status
```

## 11. Validacao final

Valide pelo menos:

1. abertura da pagina inicial
2. upload de `TXT`
3. upload de `PDF`
4. geracao de `novos_dominios.txt`
5. geracao de `relatorio.txt`
6. confirmacao manual da base
7. criacao de backup em `backups/`
8. gravacao em `audits/auditoria.db`
9. gravacao em `logs/app.log`

## Comandos De Diagnostico

Ver logs do servico:

```bash
sudo journalctl -u domain-guard -n 100 --no-pager
```

Ver log da aplicacao:

```bash
tail -n 100 /opt/domain-guard/data/logs/app.log
```

Reiniciar servico:

```bash
sudo systemctl restart domain-guard
```

## Atualizacao De Versao

Quando precisar atualizar:

1. pare o servico
2. faca backup do codigo atual se quiser
3. substitua arquivos em `/opt/domain-guard/app`
4. mantenha `/opt/domain-guard/data` intacto
5. reinstale dependencias se `requirements.txt` mudar
6. suba o servico novamente

Comandos:

```bash
sudo systemctl stop domain-guard
cd /opt/domain-guard/app
. .venv/bin/activate
pip install -r requirements.txt
sudo systemctl start domain-guard
```

## Observacao Importante

Para o seu cenario atual, esta VPS deve ser tratada como ambiente controlado de operacao, inicialmente com voce como unico operador.

Se depois houver uso compartilhado, o proximo passo deve incluir:

1. login
2. perfis
3. auditoria por usuario
4. proxy reverso
5. HTTPS
