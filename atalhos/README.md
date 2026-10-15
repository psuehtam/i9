# Atalhos do NEXUS

Mantenha esta pasta dentro do projeto; os arquivos usam o controlador `scripts/windows.ps1`.

| Atalho | Quando usar |
| --- | --- |
| `instalar.bat` | Primeira instalação ou atualização do código. Verifica requisitos, instala Docker pelo WinGet quando disponível, prepara imagens e banco e solicita o administrador. |
| `iniciar.bat` | Uso diário. Se Docker ou `.env` estiverem ausentes, inicia a instalação. Abre o navegador quando o sistema estiver pronto. |
| `reiniciar.bat` | Para e inicia os serviços deste projeto. |
| `desligar.bat` | Para os serviços sem remover os dados. |

Não é necessário instalar Python ou Node.js no computador para esse modo. WSL 2, virtualização e eventuais permissões ou reinicializações podem exigir intervenção; siga as instruções e execute o instalador novamente. O computador não é reiniciado automaticamente.

Depois de entrar, use **Administração → Dados da Senatran → Baixar e importar mês**. O repositório não inclui a frota nem credenciais. Em caso de falha, consulte `data/logs/windows.log`.

Consulte o [README principal](../README.md) para requisitos, atualização, backup e desenvolvimento.
