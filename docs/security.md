# Segurança e limitações

## Modelo de confiança

O texto produzido pelo modelo é tratado como entrada não confiável. Uma chamada de ferramenta só é executada quando:

1. o nome existe no registry;
2. os argumentos atendem à validação da ferramenta;
3. o recurso está em uma allowlist, quando aplicável;
4. o usuário confirma operações sensíveis;
5. a `ToolPolicy` permite a execução naquele contexto.

## Proteções existentes

- SQL parametrizado e identificadores cadastrados;
- filtro obrigatório para update e delete;
- confirmação humana para escrita;
- scripts limitados a arquivos criados por tools autorizadas na sessão;
- verificação estática de scripts;
- limites de linhas, páginas, caracteres e rodadas;
- timeout HTTP e timeout de espera das tools;
- logs de auditoria para banco e Git;
- segredos e artefatos locais cobertos pelo `.gitignore`.

## Limitações conhecidas

- Não existe sandbox de sistema operacional para scripts.
- `future.result(timeout=...)` não encerra uma thread que já começou.
- O quota tracker estima chamadas locais e pode divergir da cota real da API.
- A reconstrução de sessão usa texto local; resultados completos de tools não são recuperados.
- Confirmação humana reduz acidentes, mas não corrige uma configuração de banco excessivamente privilegiada.
- Logs locais podem conter informação sensível do ambiente do usuário.

## Recomendações

- use credenciais somente-leitura sempre que possível;
- conceda acesso apenas aos schemas necessários;
- não publique `.env`, logs, traces ou sessões;
- revise allowlists antes de habilitar escrita;
- prefira timeouts nativos para operações remotas;
- execute scripts em container ou sandbox quando o risco justificar.
