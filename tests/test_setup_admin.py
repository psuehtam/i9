import sys
import pytest
from scripts import setup_admin


def test_password_retries_without_writing_invalid_credentials(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['setup_admin', '--username', 'matheus'])
    invalid = 'curta'
    valid = 'uma frase de teste longa'
    answers = iter([invalid, valid, 'outra confirmacao', valid, valid])
    monkeypatch.setattr(setup_admin.getpass, 'getpass', lambda prompt: next(answers))
    created = []
    monkeypatch.setattr(setup_admin.auth, 'create_admin', lambda *args, **kwargs: created.append((args, kwargs)))
    setup_admin.main()
    assert created == [(('matheus', valid), {'reset': False})]
    output = capsys.readouterr().out
    assert 'pelo menos 12 caracteres' in output
    assert 'As senhas não conferem' in output
    assert 'Conta pronta' in output
    assert invalid not in output and valid not in output


@pytest.mark.parametrize('interruption', [EOFError, KeyboardInterrupt])
def test_cancel_does_not_create_account(monkeypatch, capsys, interruption):
    monkeypatch.setattr(sys, 'argv', ['setup_admin', '--username', 'matheus'])
    def cancel(prompt):
        raise interruption()
    monkeypatch.setattr(setup_admin.getpass, 'getpass', cancel)
    def forbidden(*args, **kwargs):
        pytest.fail('Cancellation must not create a user')
    monkeypatch.setattr(setup_admin.auth, 'create_admin', forbidden)
    with pytest.raises(SystemExit) as exc:
        setup_admin.main()
    assert exc.value.code == 130
    assert 'Criação cancelada' in capsys.readouterr().out
