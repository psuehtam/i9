"""Run: python -m scripts.setup_admin --username seu.usuario [--reset]."""
import argparse
import getpass
from src import auth


def main():
    parser = argparse.ArgumentParser(description='Criar ou recuperar a conta administrativa i9.')
    parser.add_argument('--username', required=True)
    parser.add_argument('--reset', action='store_true', help='Trocar senha e invalidar todas as sessões do usuário.')
    args = parser.parse_args()
    password = getpass.getpass('Senha (mínimo de 12 caracteres): ')
    confirmation = getpass.getpass('Repita a senha: ')
    if password != confirmation:
        parser.error('As senhas não conferem.')
    try:
        auth.create_admin(args.username, password, reset=args.reset)
    except ValueError as exc:
        parser.error(str(exc))
    print('Conta pronta. A senha não foi gravada em texto nem exibida em logs.')


if __name__ == '__main__':
    main()
