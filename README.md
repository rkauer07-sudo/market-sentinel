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

### Memecoins Analyser

A página **Memecoins Analyser** fica em `/memecoins-analyser` e é um módulo
read-only independente do radar de futuros:

- Jupiter Tokens V2 fornece a coorte de memecoins recentes usada para descobrir
  traders e enriquece cada mint comprado com nome, liquidez, holders e riscos;
- Birdeye cruza os top traders `sniper`/`smart_trader`, o PnL realizado por mint
  e o resumo de 90 dias de cada carteira;
- uma carteira entra no monitor por **um de dois caminhos** (sempre sem as tags
  `dev`, `insider`, `bundler`): (a) **3 memecoins diferentes com PnL realizado
  positivo** na coorte recente, ou (b) **track record 90d comprovado** pela
  Birdeye — PnL realizado acima de `SOLANA_INTEL_MIN_PNL_QUALIFYING_USD`, taxa
  de acerto acima de `SOLANA_INTEL_MIN_PNL_WIN_RATE`% em pelo menos
  `SOLANA_INTEL_MIN_PNL_OUTCOMES` resultados e ao menos uma memecoin lucrativa
  observada. O caminho (b) evita que carteiras excelentes fiquem de fora só
  porque um lote pequeno de lançamentos expõe apenas um de seus mints. Mints
  repetidos e lucro apenas não realizado continuam não contando;
- a página destaca **Memecoins promissoras**: cada token que passou no filtro
  estrutural e tem carteiras qualificadas comprando aparece com os players
  dentro (PnL realizado, acerto, nº de memecoins lucrativas e marca de entrada
  precoce), score de oportunidade e link para a jup.ag — isso funciona só com a
  Birdeye, sem depender da Helius;
- as carteiras aprovadas são ordenadas pelo **maior lucro realizado**, não pelo
  score composto; compras, vendas e taxa de acerto permanecem como contexto;
- tags `dev`, `insider` e `bundler` desqualificam uma carteira;
- as melhores carteiras são sincronizadas com um webhook Enhanced da Helius,
  filtrado para `SWAP` confirmado; a direção da compra é validada pelos tokens
  recebidos e pelo pagamento que saiu da carteira;
- um alerta só nasce quando a carteira recebe, em troca de SOL ou outro token,
  um mint fungível ainda não observado para ela. Reforços, vendas, airdrops,
  NFTs e entregas repetidas do webhook não duplicam o alerta;
- a compra é salva no painel e enviada ao Telegram com ranking da carteira, PnL,
  taxa de acerto, valor detectado, metadados do token e links da transação;
- Jupiter Swap V2 continua validando rotas sob demanda, sem `taker`: nenhuma
  transação é criada, assinada ou enviada.

Configure as chaves apenas no backend. `HELIUS_WEBHOOK_URL` deve ser a URL pública
completa do receptor, por exemplo
`https://seu-dominio.com/api/solana-intel/helius`. O serviço cria o webhook na
primeira sincronização e só o atualiza quando muda o conjunto de carteiras, para
evitar consumo desnecessário de créditos:

Use um domínio estável de produção, sem autenticação de preview ou Deployment
Protection; a Helius precisa alcançar esse endpoint diretamente por HTTPS.

```env
JUPITER_API_KEY=...
BIRDEYE_API_KEY=...
HELIUS_API_KEY=...
HELIUS_WEBHOOK_URL=https://seu-dominio.com/api/solana-intel/helius
HELIUS_WEBHOOK_SECRET=...       # segredo longo; nunca exponha no frontend
HELIUS_WEBHOOK_ID=...           # opcional; reutiliza um webhook já existente
SOLANA_INTEL_MAX_TOKENS=30
SOLANA_INTEL_MAX_WALLETS=50
SOLANA_INTEL_MONITOR_WALLETS=25
SOLANA_INTEL_PURCHASE_HISTORY_LIMIT=200
SOLANA_INTEL_HISTORY_LIMIT=500
SOLANA_INTEL_HISTORY_HOURS=24
SOLANA_INTEL_REANALYZE_SECONDS=21600
SOLANA_INTEL_WALLET_CACHE_SECONDS=21600
SOLANA_INTEL_MAX_CONCURRENCY=4
SOLANA_INTEL_HISTORY_OBJECT=solana-intel-history.json
SOLANA_INTEL_MIN_LIQUIDITY_USD=2000
SOLANA_INTEL_MIN_TOKEN_SAFETY=60
SOLANA_INTEL_MIN_ORGANIC_SCORE=0
SOLANA_INTEL_MIN_PROFITABLE_MEMECOINS=3
SOLANA_INTEL_MIN_OPPORTUNITY_SCORE=50
SOLANA_INTEL_MIN_PNL_QUALIFYING_USD=5000
SOLANA_INTEL_MIN_PNL_WIN_RATE=40
SOLANA_INTEL_MIN_PNL_OUTCOMES=8
SOLANA_INTEL_MIN_PNL_PROFITABLE_MEMECOINS=1
SOLANA_INTEL_CACHE_SECONDS=300
```

Sem `JUPITER_API_KEY`, o serviço tenta o acesso keyless com limite menor. Sem
`BIRDEYE_API_KEY`, não há ranking verificável. Sem as três variáveis Helius, o
ranking ainda funciona, mas não há alerta em tempo real. O histórico do provedor
pode ser incompleto e uma entidade pode usar várias carteiras; o resultado é um
filtro investigativo, não uma garantia de retorno.

A janela usa o mesmo Supabase Storage já configurado pelo projeto. Com
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` e `SUPABASE_STORAGE_BUCKET`, o objeto
`solana-intel-history.json` é criado automaticamente e sobrevive aos reinícios da
Vercel. Sem essas variáveis, a coleta funciona em memória, mas volta a zero em um
cold start.

O worker contínuo do GitHub Actions também executa `market-sentinel
solana-intel-once` em cada ciclo. Para que ele faça o enriquecimento completo sem
depender de a página estar aberta, adicione `JUPITER_API_KEY` e `BIRDEYE_API_KEY`
também em **GitHub → Settings → Secrets and variables → Actions**. Sem a chave
Birdeye, o worker ainda coleta e deduplica lançamentos, mas deixa a análise das
carteiras pendente.

**Divisão recomendada web x worker (evita o rate limit 429 da Birdeye):** a Vercel é serverless e tem timeout curto, então configure `SOLANA_INTEL_ENRICH_ON_READ=false` no Vercel — assim a página apenas lê o histórico já enriquecido no Supabase, sem chamar a Birdeye no request. Deixe o **worker do GitHub Actions** fazer o enriquecimento (com `BIRDEYE_API_KEY` nos Secrets do Actions), que roda sem timeout. As chamadas à Birdeye são espaçadas por `SOLANA_INTEL_BIRDEYE_MIN_INTERVAL_SECONDS` e reenviadas em caso de 429; cada ciclo processa no máximo `SOLANA_INTEL_ANALYSIS_BATCH` tokens e `SOLANA_INTEL_WALLET_AUDIT_BATCH` carteiras, e a cobertura vai se acumulando no Supabase entre os ciclos.

Para produção na Vercel, abra **Project Settings > Environment Variables**, crie
`BIRDEYE_API_KEY` (obrigatória para o ranking completo) e, de preferência,
`JUPITER_API_KEY`. Marque os ambientes Production e Preview e faça um redeploy.
Para ativar os alertas no worker, adicione também `HELIUS_API_KEY`,
`HELIUS_WEBHOOK_URL` e `HELIUS_WEBHOOK_SECRET` aos Secrets. Nunca use o prefixo
`NEXT_PUBLIC_`: essas variáveis devem permanecer exclusivamente no backend.

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
