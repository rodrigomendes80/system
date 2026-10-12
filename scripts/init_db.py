"""Cria as tabelas no banco configurado no .env e cadastra os tipos de serviço iniciais.

Uso:  python -m scripts.init_db
"""
import uuid

from app.config import get_settings
from app.db import create_database
from app.repositories import TipoServicoRepository

TIPOS_SERVICO_INICIAIS = [
    ("Tráfego Pago", "Gestão de mídia paga (Google Ads, Meta Ads, etc.)"),
    ("SEO", "Otimização para mecanismos de busca"),
    ("Social Media", "Gestão de redes sociais"),
    ("CRM e E-mail Marketing", "Automação, réguas de relacionamento e CRM"),
    ("Consultoria Estratégica", "Planejamento e consultoria de marketing"),
]


def main() -> None:
    settings = get_settings()
    db = create_database(settings)
    print(f"Criando esquema no backend '{settings.db_backend}'...")
    db.create_schema()

    repo = TipoServicoRepository(db)
    if not repo.listar(somente_ativos=False):
        for nome, descricao in TIPOS_SERVICO_INICIAIS:
            repo.inserir({"id": str(uuid.uuid4()), "nome": nome, "descricao": descricao, "ativo": True})
        print(f"{len(TIPOS_SERVICO_INICIAIS)} tipos de serviço cadastrados.")
    db.close()
    print("Pronto.")


if __name__ == "__main__":
    main()
