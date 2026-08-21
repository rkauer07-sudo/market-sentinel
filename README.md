# Market Sentinel

Agente **read-only** que monitora mercados da Hyperliquid, Backpack, Nado e Arcus, calcula oportunidades técnicas e envia alertas pelo Telegram. Ele não contém código de execução de ordens nem solicita chaves de trading.

## Universo

- Criptos obrigatórias: BTC, ETH, SOL, HYPE, ZEC, BNB, NEAR, SUI, JUP, UNI, AVAX, ZRO e LINK.
- Todas as commodities tokenizadas identificadas com segurança nas venues.
- Todas as ações americanas tokenizadas identificadas nas venues.
- Índices tokenizados identificados nas venues.
- Arcus incluída em modo somente leitura para mercados perpétuos públicos.
- Hyperliquid HIP-3 DEXes são descobertas dinamicamente.

## Estratégia inicial

Analisa candles fechados nos tempos configurados. Usa SMA 20/50/200, ATR, RSI, MACD, pivôs, zonas de suporte/resistência, rompimento/reteste, volume relativo e liquidez. O regime diário do BTC é aplicado somente às criptos, nunca a commodities ou ações tokenizadas.

Esta heurística é um ponto de partida que precisa de backtest e calibração. Nenhum alerta é garantia de retorno ou recomendação financeira.

## Instalação no Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

## Telegram

1. Crie um bot conversando com `@BotFather` no Telegram e copie o token.
2. Envie uma mensagem ao bot.
3. Abra `https://api.telegram.org/botSEU_TOKEN/getUpdates` e copie `message.chat.id`.
4. Preencha localmente `.env`:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

O `.env` é ignorado pelo Git. Nunca use uma chave de corretora neste projeto.

## Uso

```powershell
# Listar o universo descoberto
market-sentinel markets

# Executar uma única varredura
market-sentinel once

# Monitorar continuamente
market-sentinel run
```

## Interface gráfica

```powershell
market-sentinel-web
```

Abra `http://127.0.0.1:8765`. O painel permite iniciar/parar o loop, executar uma
varredura imediata, atualizar o universo e acompanhar oportunidades e logs. Por
padrão, a interface escuta somente no computador local.

## Login Web3 e chat

O painel aceita login por carteira compatível com `personal_sign` (MetaMask, Rabby e similares).
A assinatura serve apenas para provar a posse do endereço: ela não cria transação, não pede chave
privada e não concede acesso aos fundos. A sessão fica em cookie `HttpOnly` assinado.

Em SQLite/Render, usuários e mensagens são criados automaticamente. No modo Vercel + Supabase:

1. Execute [`supabase_social.sql`](supabase_social.sql) uma vez no SQL Editor do Supabase.
2. Configure `SESSION_SECRET` com um valor longo e aleatório na Vercel e no worker web.
3. Mantenha `SUPABASE_SERVICE_ROLE_KEY` apenas no backend; ela nunca deve ir para o JavaScript.

As tabelas de usuários já incluem `plan`, `subscription_status`, provedor, cliente externo e fim do
período. Esses campos deixam a base pronta para a futura cobrança mensal, mas nenhum pagamento é
processado nesta versão.

## Aprendizado diário auditável

O primeiro ciclo após a virada do dia em `America/Sao_Paulo` avalia apenas sinais já
encerrados até o fim do dia anterior. A calibração segue o fluxo de diário e validação
walk-forward do [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading):

- usa uma janela móvel de até 180 dias e separa os 20% mais recentes como validação;
- exige ao menos 30 resultados totais e 12 por segmento;
- só promove um ajuste quando histórico e período posterior apontam na mesma direção;
- limita o ajuste a quatro pontos e registra amostra, acerto e evidência no SQLite;
- falha fechado: amostra pequena ou validação divergente mantém o modelo atual.

O aprendizado serve para calibrar e filtrar sinais futuros; não altera resultados passados,
não usa dados posteriores ao corte e não executa ordens. Ele pode melhorar a seleção ao longo
do tempo, mas não garante aumento de acerto. O resumo fica disponível em `/api/learning`.

Sem Telegram configurado, `once` mostra oportunidades no terminal e `run` apenas registra logs; nada é enviado.

## Docker 24/7

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose logs -f sentinel
```

Abra `http://127.0.0.1:8765` após o contêiner iniciar.

O SQLite persiste em `data/sentinel.db`. O contêiner reinicia automaticamente, mas uma VPS/máquina ligada continuamente ainda é necessária.

## Hospedagem 24/7 no Render

O projeto inclui `render.yaml` com serviço Docker pago, health check e disco persistente.

1. Coloque o projeto em um repositório privado no GitHub ou GitLab.
2. No Render, escolha **New > Blueprint** e conecte o repositório.
3. Confirme o plano `starter` e o disco de 1 GB.
4. Preencha `DASHBOARD_PASSWORD`, `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` quando solicitado.
5. Após o deploy, abra a URL `onrender.com` exibida e entre com usuário `admin` e sua senha.
6. Clique em **Iniciar monitor** no painel.

Não use o plano gratuito: ele pode suspender o serviço e não aceita disco persistente. Não publique
uma instância sem `DASHBOARD_PASSWORD`; sem as duas variáveis de login, a autenticação local fica
desativada para facilitar desenvolvimento.

## Controles relevantes

## Modo gratuito: Vercel + GitHub Actions + Supabase Storage

O workflow `.github/workflows/scan.yml` executa uma varredura a cada cinco minutos. O banco SQLite
é baixado e reenviado para um bucket privado do Supabase, permitindo que execuções independentes
preservem sinais, eventos, cooldowns e cenários.

1. Crie um projeto gratuito no Supabase e um bucket privado chamado `sentinel` em Storage.
2. No GitHub, em **Settings > Secrets and variables > Actions**, crie os secrets
   `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.
3. Na Vercel, adicione `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
   `SUPABASE_STORAGE_BUCKET=sentinel`, `SUPABASE_DB_OBJECT=sentinel.db` e `SESSION_SECRET`.
4. Envie `.github/workflows/scan.yml` e o restante das alterações para a branch `main`.
5. Em **GitHub > Actions > Market scan**, execute **Run workflow** uma vez para criar o banco.

Nunca coloque a service role key em arquivos versionados ou no JavaScript do navegador. Ela deve
existir somente nos secrets do GitHub e nas variáveis protegidas da função Vercel.

Edite `config.yaml` para alterar intervalo de varredura, timeframes, score, liquidez e cooldown. O sistema:

- ignora candles ainda abertos;
- deduplica alertas por venue/setup/zona;
- mantém oportunidades ativas mesmo quando o setup deixa de reaparecer no scanner;
- registra criação, alvo, stop e expiração em uma linha do tempo persistente;
- mede movimento favorável/adverso máximo e taxa histórica de concretização;
- falha isoladamente por venue;
- limita e repete chamadas da Hyperliquid quando houver HTTP 429;
- registra logs estruturados e um diagnóstico de filtros para cada ciclo;
- não classifica instrumentos ambíguos;
- não envia alerta se o R:R calculado não alcançar o mínimo.

## Limitações do MVP

- A classificação de HIP-3/Nado depende dos metadados públicos e de nomes inequívocos.
- O endpoint V2 da Nado está em evolução; falhas ficam isoladas e são registradas.
- Linhas de tendência são aproximadas inicialmente por estrutura de pivôs e médias; regressão robusta e validação histórica entram na próxima fase.
- Ainda não há backtest walk-forward, painel web ou acompanhamento de alvo/invalidação após o alerta.
