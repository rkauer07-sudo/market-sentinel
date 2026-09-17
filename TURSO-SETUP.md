# Migração do banco de mercado para o Turso (libSQL)

## Por que

O modelo antigo despachava o **arquivo SQLite inteiro** (~3,5 MB com o WAL) para
o Supabase Storage a cada ciclo/leitura. Isso estourou a **cota de egress** do
plano free do Supabase (HTTP 402 – `exceed_egress_quota`), o worker passou a
falhar no upload e a página ficou sem dados.

O Turso/libSQL resolve na raiz: o app **consulta linhas** no banco remoto em vez
de baixar/subir o arquivo. O egress cai de MB por ciclo para KB por query, e o
tempo real continua igual — o worker escreve as linhas, a página lê as linhas.

Free tier do Turso (set/2026): **5 GB de storage, 500 M linhas lidas/mês,
10 M linhas escritas/mês, 100 bancos, sem pausa por inatividade**. Muito acima
do que este projeto consome.

O **login Web3, usuários e chat continuam no Supabase Postgres** — isso não muda.
Só o banco de mercado (sinais, runs, candidatos, aprendizado) foi para o Turso.

## O que mudou no código

- `src/market_sentinel/storage.py` — `Store` agora conecta no Turso (`libsql`)
  quando `TURSO_DATABASE_URL` existe; senão, usa SQLite local. Se o Turso cair,
  degrada para local e reporta `storage_error` **sem derrubar** o serviço.
- `pyproject.toml` — adiciona a dependência `libsql`.
- `.github/workflows/scan.yml` — worker usa `TURSO_*` (removidos `SYNC_DB_*` e
  `SUPABASE_*` do banco de mercado).
- `.env.example` — novas variáveis `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN`.

Nenhuma mudança foi necessária em `web.py`, `social.py`, `app.py` ou `cli.py`.

## Passo a passo

### 1. Criar o banco no Turso

Instale a CLI (https://docs.turso.tech) e rode:

```bash
turso auth signup            # ou: turso auth login
turso db create market-sentinel
turso db show market-sentinel --url        # -> TURSO_DATABASE_URL  (libsql://...)
turso db tokens create market-sentinel     # -> TURSO_AUTH_TOKEN
```

Guarde os dois valores.

### 2. GitHub Actions (o worker que alimenta os dados)

Em **GitHub → Settings → Secrets and variables → Actions**, crie:

- `TURSO_DATABASE_URL`
- `TURSO_AUTH_TOKEN`

Os secrets antigos `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` e os `SYNC_DB_*`
não são mais usados pelo worker (pode remover).

### 3. Vercel (a página que lê os dados)

Em **Project Settings → Environment Variables** (Production + Preview), adicione:

- `TURSO_DATABASE_URL`
- `TURSO_AUTH_TOKEN`

Mantenha `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` (login/chat) e o
`SESSION_SECRET`. Faça **Redeploy**.

### 4. (Opcional) Render

Se você usa o serviço 24/7 no Render e quer que ele compartilhe o mesmo banco,
adicione `TURSO_DATABASE_URL` e `TURSO_AUTH_TOKEN` no serviço. Sem isso, o Render
continua usando o disco SQLite local dele.

### 5. Publicar e ligar

```bash
git add -A && git commit -m "feat(storage): migra banco de mercado para Turso/libSQL"
git push origin main
```

O push dispara o worker. Depois rode uma vez manualmente em
**GitHub → Actions → Continuous market scan → Run workflow** e confirme que a run
volta a durar horas (não ~20 s) e termina no passo **Verify remote database
(Turso)** mostrando a contagem de sinais/runs.

## Observações

- **Histórico:** o banco Turso começa vazio. O aprendizado diário volta a
  acumular a partir de agora (ele já precisa de ~30 resultados para calibrar). Se
  você recuperar o `sentinel.db` antigo do Supabase (após o reset mensal do
  egress ou um upgrade), dá para fazer um export/import único para o Turso — posso
  montar esse script depois.
- **Concorrência:** worker (escreve) e página (lê) usam conexões independentes ao
  mesmo banco Turso; o libSQL lida com isso nativamente.
- **Custo:** dentro do free tier do Turso, o consumo deste projeto é uma fração
  dos limites; não há mais o risco de egress do modelo de blob.
