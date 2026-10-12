-- CHECK constraints (validadas pelo Delta a cada escrita).
-- O script de inicialização ignora o erro "already exists" ao reexecutar.

ALTER TABLE {fq}.projetos ADD CONSTRAINT chk_projetos_status
  CHECK (status IN ('PLANEJAMENTO', 'EM_ANDAMENTO', 'FINALIZADO'));

ALTER TABLE {fq}.tarefas ADD CONSTRAINT chk_tarefas_status
  CHECK (status IN ('A_FAZER', 'EM_ANDAMENTO', 'BLOQUEADA', 'FINALIZADA'));

ALTER TABLE {fq}.tarefas ADD CONSTRAINT chk_tarefas_prioridade
  CHECK (prioridade IN ('BAIXA', 'MEDIA', 'ALTA', 'URGENTE'));

ALTER TABLE {fq}.cliente_servicos ADD CONSTRAINT chk_cliente_servicos_valor
  CHECK (valor >= 0);

ALTER TABLE {fq}.tarefa_historico ADD CONSTRAINT chk_tarefa_historico_tipo
  CHECK (tipo IN ('COMENTARIO', 'SISTEMA'));
