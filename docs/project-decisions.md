# Decisoes de implementacao e obstaculos

## Obstaculo 1 - Envio de e-mail sem credenciais no ambiente academico

- Decisao: tornar o envio SMTP configuravel por variaveis de ambiente (AUDITFREE_SMTP_*).
- Motivo: evitar credenciais hardcoded e permitir executar o projeto mesmo sem servidor SMTP real.
- Impacto: o sistema continua monitorando e gravando historico; quando offline, informa claramente se o alerta nao foi enviado por falta de configuracao.

## Obstaculo 2 - Validacao de disponibilidade sem ICMP/ping privilegiado

- Decisao: usar conexao Socket TCP curta para IP/porta cadastrados.
- Motivo: manter aderencia ao escopo (Socket), evitar dependencias externas e restricoes de privilegio do ping ICMP em alguns ambientes.
- Impacto: resultado reflete disponibilidade do servico naquela porta, nao apenas resposta de camada de rede.

## Obstaculo 3 - Persistencia simples, portavel e sem servidor

- Decisao: usar SQLite em arquivo local (data/auditfree.db).
- Motivo: aderencia ao documento e simplicidade de setup para avaliacao em laboratorio.
- Impacto: projeto fica facil de transportar e executar em qualquer maquina com Python.

## Obstaculo 4 - Escopo academico com necessidade de manutencao futura

- Decisao: separar em camadas (CLI, service, database, network, emailer).
- Motivo: facilitar evolucao sem fugir da proposta original.
- Impacto: cada funcionalidade fica isolada, melhorando legibilidade e testabilidade.

## Obstaculo 5 - Ajuste de usabilidade para sessao interativa

- Decisao: manter o menu aberto apos cada comando, encerrando apenas quando o usuario escolher sair.
- Motivo: reduzir friccao operacional durante monitoramento e testes em laboratorio.
- Impacto: o usuario pode executar varias funcoes em sequencia sem reiniciar a aplicacao.

## Obstaculo 6 - Integridade e rastreabilidade de identificadores

- Decisao: mudar o identificador para ID numerico autogerado pelo SQLite (AUTOINCREMENT).
- Motivo: evitar colisao de IDs manuais e reforcar integridade referencial entre dispositivos e historico.
- Impacto: o cadastro ficou mais simples e a relacao com check_history ficou consistente por chave numerica.

## Requisitos complementares adicionados

### Funcionais

- RF05: verificar todos os dispositivos em lote.
- RF06: consultar historico com filtros.
- RF07: configurar porta por dispositivo e timeout por verificacao.
- RF08: gerar ID de dispositivo automaticamente no banco.

### Nao funcionais

- RN04: arquitetura modular com separacao de responsabilidades.
- RN05: uso de biblioteca padrao Python (sem dependencias externas).
- RN06: timestamps em UTC e integridade relacional via chave estrangeira.
