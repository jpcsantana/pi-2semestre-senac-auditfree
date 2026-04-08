# AuditFree - Monitoramento de Disponibilidade em Rede

Projeto desenvolvido com base no escopo do Projeto Integrador (2o semestre - Senac), focado em auditoria e analise de disponibilidade de dispositivos na rede corporativa.

## Objetivo do sistema

Cadastrar dispositivos em banco de dados, verificar disponibilidade via conexoes Socket e enviar alertas por e-mail quando houver falha de comunicacao.

## Requisitos atendidos do documento original

- RF01: cadastro de dispositivos com identificador, IP, nome da maquina e e-mail de notificacao.
- RF02: teste de disponibilidade com conexao Socket TCP curta.
- RF03: historico de status (online/offline) e data/hora da verificacao no banco.
- RF04: disparo automatico de alerta por e-mail em falha.
- RN01: implementado em Python.
- RN02: armazenamento em banco de dados SQLite.
- RN03: interface em linha de comando (CLI) com menu interativo.

## Requisitos adicionais definidos na implementacao

### Funcionais adicionais

- RF05: verificacao em lote de todos os dispositivos cadastrados em uma unica opcao de menu.
- RF06: consulta de historico com filtro por dispositivo e limite de registros.
- RF07: configuracao de porta monitorada por dispositivo e timeout por execucao.
- RF08: IDs dos dispositivos gerados automaticamente pelo banco de dados.

### Nao funcionais adicionais

- RN04: arquitetura em camadas simples (CLI, servico, persistencia) para manutencao facilitada.
- RN05: uso exclusivo de biblioteca padrao do Python para reduzir custo de execucao.
- RN06: timestamps em UTC e integridade relacional com chave estrangeira no historico.

## Estrutura do projeto

- auditfree/: pacote principal
- tests/: testes automatizados
- data/: banco SQLite local
- docs/: documentacao e artefatos do projeto

## Como executar

1. Execute o programa:

```bash
python main.py
```

2. O sistema abre um menu interativo continuo.
Selecione uma opcao, execute a funcionalidade e retorne ao menu.
O programa so encerra quando a opcao `0` for escolhida.

Menu disponivel:

- 1) Inicializar banco
- 2) Cadastrar dispositivo
- 3) Listar dispositivos
- 4) Verificar um dispositivo
- 5) Verificar todos os dispositivos
- 6) Consultar historico
- 0) Sair

3. A aplicacao executa a opcao escolhida e retorna ao menu principal.
Para encerrar, escolha a opcao `0`.

## Funcionalidades do menu

### 1) Inicializar banco

- Cria as tabelas caso nao existam.
- Valida a integridade da estrutura esperada.
- Aplica migracao de esquema legado (quando necessario) para o modelo com ID automatico.

### 2) Cadastrar dispositivo

- Solicita IP/hostname, nome da maquina, e-mail e porta.
- Insere o registro no SQLite com constraints de integridade.
- Gera e exibe automaticamente o ID do dispositivo.

### 3) Listar dispositivos

- Mostra todos os dispositivos cadastrados.
- Exibe ultimo status e data/hora da ultima verificacao.
- Permite descobrir o ID automatico para uso nas demais operacoes.

### 4) Verificar um dispositivo

- Solicita o ID numerico do dispositivo.
- Executa teste de disponibilidade via Socket.
- Salva resultado no historico e atualiza ultimo status.
- Pode enviar alerta de e-mail caso o status seja offline.

### 5) Verificar todos

- Executa verificacao Socket para todos os dispositivos.
- Registra todo resultado no historico.
- Mostra resumo final com quantidade online/offline.
- Pode enviar alerta para cada dispositivo offline.

### 6) Consultar historico

- Lista historico geral ou filtrado por ID de dispositivo.
- Permite definir limite de registros retornados.
- Exibe status, data/hora, latencia e mensagem de erro.

### 0) Sair

- Finaliza a aplicacao de forma controlada.

Exemplo de uso:

1) Rodar `python main.py`.
2) Escolher `2` para cadastrar e anotar o ID gerado.
3) Escolher `4` para verificar um dispositivo pelo ID.
4) Escolher `6` para consultar historico.

## Configuracao de e-mail (SMTP)

Defina as variaveis de ambiente para envio automatico de alerta:

- AUDITFREE_SMTP_HOST
- AUDITFREE_SMTP_PORT (padrao 587)
- AUDITFREE_SMTP_FROM
- AUDITFREE_SMTP_USER (opcional)
- AUDITFREE_SMTP_PASS (opcional)
- AUDITFREE_SMTP_USE_TLS (padrao true)
- AUDITFREE_SMTP_USE_SSL (padrao false)

Exemplo (PowerShell):

```powershell
$env:AUDITFREE_SMTP_HOST = "smtp.seudominio.com"
$env:AUDITFREE_SMTP_PORT = "587"
$env:AUDITFREE_SMTP_FROM = "auditfree@seudominio.com"
$env:AUDITFREE_SMTP_USER = "auditfree@seudominio.com"
$env:AUDITFREE_SMTP_PASS = "senha-app"
$env:AUDITFREE_SMTP_USE_TLS = "true"
```

## Executar testes

```bash
python -m unittest discover -s tests -p "test_*.py"
```
