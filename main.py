from dotenv import load_dotenv

# Carrega variaveis do arquivo .env em desenvolvimento. Em producao as
# variaveis ja vem do ambiente e nao sao sobrescritas (override=False).
load_dotenv()

from auditfree.cli import run

if __name__ == "__main__":
    raise SystemExit(run())
