# AuditFree - Auditoria de Maquinas

Projeto desenvolvido como Projeto Integrador do 2o semestre (Senac), focado em auditoria e monitoramento de maquinas em ambiente corporativo via linha de comando.

## Objetivo do sistema

Cadastrar maquinas em banco de dados e realizar auditorias: verificacao de conectividade via ping, varredura de portas inseguras, auditoria da maquina local e validacao de registros DNS.

## Dependencias

```
psutil>=5.9
rich>=13.0
pyfiglet>=1.0
```

Instalar:

```bash
pip install -r requirements.txt
```

## Como executar

```bash
python main.py
```

Opcoes de linha de comando (opcionais):

```
--db-path   Caminho do banco SQLite  (padrao: data/auditfree.db)
--log-dir   Diretorio de logs        (padrao: logs/)
```

## Menu principal

```
1  Gerenciar dispositivos   cadastrar, listar, editar ou excluir maquinas
2  Verificar conectividade  ping em uma maquina por ID
3  Verificar todas          ping em todas as maquinas cadastradas
4  Varredura de portas      escaneia portas inseguras conhecidas
5  Auditoria local          audita a maquina onde o programa esta rodando
6  Validar registros DNS    consulta hostname via IP e atualiza cadastro
7  Historico de ping        mostra verificacoes anteriores
0  Sair
```

## Funcionalidades

### 1) Gerenciar dispositivos

Submenu com CRUD completo de maquinas cadastradas:

- **Cadastrar**: solicita IP/hostname, nome e codigo AnyDesk (opcional). Ao informar o IP, o sistema tenta resolver o hostname via DNS e oferece usa-lo como nome automaticamente.
- **Listar**: exibe tabela com ID, IP, nome, AnyDesk, ultimo status e data da ultima verificacao.
- **Editar**: permite alterar IP, nome e codigo AnyDesk de uma maquina ja cadastrada.
- **Excluir**: remove a maquina e todo o seu historico de verificacoes (CASCADE).

### 2) Verificar conectividade

Executa ping em uma maquina pelo ID, registra o resultado (online/offline, latencia, erro) no banco de dados e no log de auditoria.

### 3) Verificar todas

Executa ping em batch para todas as maquinas cadastradas e exibe um resumo com quantidade de dispositivos online e offline.

### 4) Varredura de portas inseguras

Escaneia 19 portas conhecidamente inseguras na maquina alvo:

| Porta | Servico |
|------:|---------|
| 21 | FTP |
| 23 | Telnet |
| 25 | SMTP sem TLS |
| 69 | TFTP |
| 135-139 | NetBIOS / MS RPC |
| 445 | SMB |
| 1433 | SQL Server |
| 1521 | Oracle DB |
| 2049 | NFS |
| 3306 | MySQL |
| 3389 | RDP |
| 5432 | PostgreSQL |
| 5900 | VNC |
| 6379 | Redis |
| 11211 | Memcached |
| 27017 | MongoDB |

Se o host nao responder a nenhuma tentativa de conexao, exibe aviso de host inacessivel em vez de falso positivo de "nenhuma porta aberta".

### 5) Auditoria local

Coleta informacoes da maquina onde o programa esta sendo executado:

- Sistema operacional e arquitetura
- Quantidade de CPUs e frequencia
- Uso de RAM (total e em uso)
- Uso de disco
- Usuarios ativos
- Interfaces de rede (IPv4)
- Top 10 processos por consumo de CPU

**Persistencia:** o IP e hostname da maquina local sao registrados na tabela `devices` e um check com status `online` e gravado em `check_history`. Os detalhes de hardware, processos e interfaces sao salvos apenas em `logs/local_audit.log`, que e sobrescrito a cada execucao.

### 6) Validar registros DNS

Executa `gethostbyaddr` sobre o IP da maquina cadastrada e exibe o hostname retornado. Caso o hostname encontrado seja diferente do nome salvo no cadastro, oferece a opcao de atualizar o registro.

### 7) Historico de ping

Consulta o historico de verificacoes com filtro opcional por ID de maquina e limite de registros retornados. Exibe status, data/hora, latencia e mensagem de erro quando houver.

## Estrutura do projeto

```
auditfree/
  cli.py          interface de linha de comando (menus, entrada, exibicao)
  service.py      logica de negocio e orquestracao
  database.py     acesso ao SQLite (dispositivos e historico)
  network.py      ping, varredura de portas e lookup DNS
  local_audit.py  coleta de informacoes da maquina local
  logger.py       registro de auditorias e erros em arquivo
  config.py       constantes de configuracao padrao

data/
  auditfree.db    banco de dados SQLite

logs/
  audits.log      registro de todas as operacoes de auditoria
  errors.log      registro de erros e eventos criticos
  local_audit.log ultimo resultado de auditoria local (sobrescrito)
```

## Banco de dados

Duas tabelas SQLite:

**devices** — maquinas cadastradas

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | INTEGER PK | identificador automatico |
| ip | TEXT | endereco IP ou hostname |
| machine_name | TEXT | nome da maquina |
| anydesk_code | TEXT | codigo AnyDesk (opcional) |
| created_at | TEXT | data de cadastro (UTC) |
| last_status | TEXT | ultimo status: online / offline |
| last_checked_at | TEXT | data da ultima verificacao |

**check_history** — historico de verificacoes de conectividade

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | INTEGER PK | identificador automatico |
| device_id | INTEGER FK | referencia para devices |
| status | TEXT | online / offline |
| checked_at | TEXT | data/hora da verificacao (UTC) |
| latency_ms | INTEGER | latencia em milissegundos |
| error_message | TEXT | descricao do erro, se houver |

## Requisitos atendidos

- RF01: cadastro de maquinas com IP, nome e identificador automatico
- RF02: verificacao de disponibilidade via ping (ICMP)
- RF03: historico de status com data/hora no banco de dados
- RF04: varredura de portas inseguras com identificacao de risco
- RF05: verificacao em lote de todas as maquinas cadastradas
- RF06: consulta de historico com filtro por dispositivo e limite
- RF07: auditoria da maquina local com registro em log dedicado
- RF08: validacao e atualizacao de registros DNS
- RN01: implementado em Python
- RN02: armazenamento em SQLite sem dependencias externas de banco
- RN03: interface interativa em linha de comando
- RN04: arquitetura em camadas (CLI, servico, persistencia, rede)
- RN05: timestamps em UTC e integridade relacional com chave estrangeira
