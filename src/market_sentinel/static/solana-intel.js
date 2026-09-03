(() => {
  let intelState = null;
  let loading = false;

  const locale = () => document.documentElement.lang || 'pt-BR';
  const escapeHTML = value => String(value ?? '').replace(/[&<>"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;',
  }[character]));
  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      cache: 'no-store',
      headers: {...(options.headers || {}), 'Cache-Control': 'no-cache'},
    });
    if (!response.ok) {
      let message = await response.text();
      try { message = JSON.parse(message).detail; } catch {}
      throw new Error(message || `HTTP ${response.status}`);
    }
    return response.json();
  }
  function toast(message, bad = false) {
    const element = document.querySelector('#toast');
    if (!element) return;
    element.textContent = message;
    element.className = `toast show${bad ? ' bad' : ''}`;
    window.setTimeout(() => { element.className = 'toast'; }, 2800);
  }
  const compact = value => new Intl.NumberFormat(locale(), {
    notation: 'compact', maximumFractionDigits: 1,
  }).format(Number(value || 0));
  const money = value => new Intl.NumberFormat(locale(), {
    style: 'currency', currency: 'USD', notation: Math.abs(Number(value || 0)) >= 10000 ? 'compact' : 'standard',
    maximumFractionDigits: Math.abs(Number(value || 0)) >= 1000 ? 1 : 0,
  }).format(Number(value || 0));
  const short = value => value ? `${value.slice(0, 5)}…${value.slice(-4)}` : '—';
  const seconds = value => {
    if (value == null) return '—';
    const number = Number(value);
    if (number < 60) return `${Math.round(number)}s`;
    if (number < 3600) return `${Math.round(number / 60)}min`;
    return `${(number / 3600).toFixed(1)}h`;
  };
  const age = value => {
    if (!value) return 'horário indisponível';
    const elapsed = Math.max(0, Date.now() - new Date(value).getTime());
    if (elapsed < 60000) return 'agora';
    if (elapsed < 3600000) return `há ${Math.floor(elapsed / 60000)}min`;
    if (elapsed < 86400000) return `há ${Math.floor(elapsed / 3600000)}h`;
    return `há ${Math.floor(elapsed / 86400000)}d`;
  };

  const flagLabels = {
    mint_authority_active: 'mint ativa',
    freeze_authority_active: 'freeze ativa',
    high_holder_concentration: 'concentração alta',
    thin_liquidity: 'liquidez baixa',
    low_organic_activity: 'atividade pouco orgânica',
    low_safety_score: 'segurança abaixo do corte',
    metadata_unavailable: 'metadados ainda indisponíveis',
  };
  const confidenceLabels = {
    robust: '8+ lucros distintos', established: '5+ lucros distintos', aggressive: 'filtro agressivo',
  };

  function providerClass(provider) {
    if (provider.mode === 'memory') return 'waiting';
    if (provider.available === true) return 'ready';
    if (provider.available === false) return 'error';
    return 'waiting';
  }

  function renderProviders(providers = {}) {
    ['jupiter', 'birdeye', 'history', 'helius'].forEach(name => {
      const element = document.querySelector(`#provider-${name}`);
      const provider = providers[name] || {};
      if (!element) return;
      element.className = `provider-chip ${providerClass(provider)}`;
      const state = name === 'history' && provider.available === true
        ? provider.persistent ? 'persistente' : 'memória temporária'
        : provider.available === true ? 'ativo' : provider.available === false
        ? 'falha' : provider.configured ? 'configurado' : name === 'jupiter' ? 'keyless' : 'sem chave';
      element.textContent = `${name} · ${state}`;
    });
  }

  function renderWallets(wallets = [], birdeyeConfigured = false) {
    const box = document.querySelector('#smartWalletList');
    if (!box) return;
    if (!birdeyeConfigured) {
      box.innerHTML = '<div class="intel-empty"><strong>Ranking aguardando a Birdeye</strong>Configure <code>BIRDEYE_API_KEY</code> no backend para cruzar traders, PnL e tempo de entrada.</div>';
      return;
    }
    if (!wallets.length) {
      box.innerHTML = '<div class="intel-empty"><strong>Nenhuma carteira atingiu o corte agressivo</strong>A carteira entra no monitor ao comprovar PnL realizado positivo em pelo menos 3 memecoins diferentes. Lucro não realizado e mints repetidos não contam; dev, insider e bundler ficam de fora.</div>';
      return;
    }
    box.innerHTML = wallets.slice(0, 20).map((wallet, index) => {
      const risky = wallet.risk_penalty > 0;
      const tags = (wallet.tags || []).map(tag => `<span class="intel-tag ${escapeHTML(tag)}">${escapeHTML(tag.replace('_', ' '))}</span>`).join('');
      return `<article class="smart-wallet">
        <div class="wallet-rank">#${index + 1}</div>
        <div>
          <div class="wallet-address"><a href="${escapeHTML(wallet.solscan_url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(short(wallet.wallet))}</a><div class="intel-tags">${tags || '<span class="intel-tag">sem tag</span>'}</div></div>
          <div class="wallet-stats">
            <div class="wallet-stat"><span>Resultados 90d</span><b>${compact(wallet.outcomes)}</b></div>
            <div class="wallet-stat"><span>Acerto observado</span><b>${Number(wallet.win_rate_pct).toFixed(1)}%</b></div>
            <div class="wallet-stat"><span>Piso estatístico</span><b>${Number(wallet.confidence_win_rate_pct).toFixed(1)}%</b></div>
            <div class="wallet-stat"><span>Compra / venda</span><b>${compact(wallet.total_buy)} / ${compact(wallet.total_sell)}</b></div>
            <div class="wallet-stat"><span>PnL realizado</span><b class="${wallet.realized_pnl_usd >= 0 ? 'positive' : ''}">${money(wallet.realized_pnl_usd)}</b></div>
            <div class="wallet-stat"><span>Memecoins com lucro</span><b>${compact(wallet.profitable_memecoins)}</b></div>
          </div>
        </div>
        <div class="wallet-score"><b>${wallet.score}</b><span>score de contexto</span><i class="confidence-pill ${escapeHTML(wallet.confidence)}">${confidenceLabels[wallet.confidence] || wallet.confidence}</i></div>
        ${risky ? '<div class="wallet-risk-note">Carteira excluída das oportunidades por risco de vínculo com o lançamento.</div>' : ''}
      </article>`;
    }).join('');
  }

  const basisLabels = {
    cohort: 'lucro em várias memecoins', track_record: 'track record 90d', none: 'contexto',
  };

  function renderOpportunities(opportunities = [], birdeyeConfigured = false) {
    const box = document.querySelector('#solanaOpportunityList');
    if (!box) return;
    if (!birdeyeConfigured) {
      box.innerHTML = '<div class="intel-empty"><strong>Análise aguardando a Birdeye</strong>Configure <code>BIRDEYE_API_KEY</code> no backend para cruzar as carteiras que estão dentro de cada memecoin.</div>';
      return;
    }
    if (!opportunities.length) {
      box.innerHTML = '<div class="intel-empty"><strong>Nenhuma memecoin com players qualificados ainda</strong>A memecoin aparece aqui quando passa no filtro estrutural (liquidez, autoridade de mint/freeze, concentração e segurança) e tem pelo menos uma carteira qualificada comprando. A janela vai preenchendo a cada ciclo.</div>';
      return;
    }
    box.innerHTML = opportunities.slice(0, 24).map(op => {
      const icon = op.icon
        ? `<img src="${escapeHTML(op.icon)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
        : escapeHTML((op.symbol || '?').slice(0, 2));
      const conviction = op.conviction === 'high' ? 'ALTA CONVICÇÃO' : 'SELETIVA';
      const flags = (op.risk_flags || []);
      const flagHTML = flags.length
        ? flags.map(flag => `<span class="risk-flag">${escapeHTML(flagLabels[flag] || flag)}</span>`).join('')
        : '<span class="risk-flag clean">sem alerta estrutural nos campos disponíveis</span>';
      const players = (op.wallet_evidence || []).map(player => `
        <a class="op-player" href="${escapeHTML(player.solscan_url)}" target="_blank" rel="noopener noreferrer">
          <span class="op-player-addr">${escapeHTML(short(player.wallet))}${player.early ? ' <i class="op-early">entrada precoce</i>' : ''}</span>
          <span class="op-player-stats"><b class="${player.realized_pnl_usd >= 0 ? 'positive' : ''}">${money(player.realized_pnl_usd)}</b> · ${Number(player.win_rate_pct).toFixed(0)}% acerto · ${compact(player.profitable_memecoins)} memecoins · score ${player.score}</span>
        </a>`).join('');
      return `<article class="launch-card opportunity-card" data-mint="${escapeHTML(op.mint)}">
        <div class="launch-icon">${icon}</div>
        <div>
          <div class="launch-name-row"><span class="launch-name">${escapeHTML(op.symbol)} · ${escapeHTML(op.name)}</span><span class="conviction-pill ${op.conviction === 'high' ? 'high' : ''}">${conviction}</span><span class="op-score">score ${Number(op.opportunity_score)}/100</span></div>
          <div class="launch-meta"><span>Liquidez <b>${money(op.liquidity_usd)}</b></span><span>Market cap <b>${money(op.mcap_usd)}</b></span><span>Holders <b>${compact(op.holder_count)}</b></span><span>Safety <b>${Number(op.safety_score || 0)}/100</b></span></div>
          <div class="safety-track" title="Score estrutural, não previsão de retorno"><i style="width:${Math.max(0, Math.min(100, Number(op.safety_score)))}%"></i></div>
          <div class="op-players-head">${compact(op.quality_wallet_count)} carteira(s) qualificada(s) dentro</div>
          <div class="op-players">${players}</div>
          <div class="launch-flags">${flagHTML}</div>
        </div>
        <div class="launch-actions"><button class="route-button" data-route-mint="${escapeHTML(op.mint)}">Validar rotas Jupiter</button><a class="jupiter-link" href="${escapeHTML(op.jupiter_url)}" target="_blank" rel="noopener noreferrer">Abrir na jup.ag ↗</a><span class="route-result" data-route-result="${escapeHTML(op.mint)}"></span></div>
      </article>`;
    }).join('');
  }

  function renderPurchases(purchases = [], heliusConfigured = false) {
    const box = document.querySelector('#solanaLaunchList');
    if (!box) return;
    if (!purchases.length) {
      box.innerHTML = heliusConfigured
        ? '<div class="intel-empty"><strong>Monitor ativo; nenhuma compra nova detectada</strong>Reforços em posições já conhecidas, vendas e transferências não geram alerta. A próxima abertura em um mint novo aparecerá aqui.</div>'
        : '<div class="intel-empty"><strong>Monitor aguardando a Helius</strong>Configure o webhook autenticado para receber swaps confirmados das carteiras ranqueadas.</div>';
      return;
    }
    box.innerHTML = purchases.map(purchase => {
      const flags = purchase.risk_flags || [];
      const icon = purchase.icon
        ? `<img src="${escapeHTML(purchase.icon)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
        : escapeHTML((purchase.symbol || '?').slice(0, 2));
      const flagHTML = flags.length
        ? flags.map(flag => `<span class="risk-flag">${escapeHTML(flagLabels[flag] || flag)}</span>`).join('')
        : '<span class="risk-flag clean">sem alerta estrutural nos campos disponíveis</span>';
      const payment = purchase.payment_amount == null
        ? 'valor não identificado'
        : `${Number(purchase.payment_amount).toLocaleString(locale(), {maximumFractionDigits: 6})} ${escapeHTML(purchase.payment_symbol || '')}`;
      const alertState = purchase.alert_sent_at ? 'Telegram enviado' : purchase.alert_error ? 'Telegram pendente' : 'aguardando entrega';
      return `<article class="launch-card opportunity-card purchase-card" data-mint="${escapeHTML(purchase.mint)}">
        <div class="launch-icon">${icon}</div>
        <div>
          <div class="launch-name-row"><span class="launch-name">${escapeHTML(purchase.symbol)} · ${escapeHTML(purchase.name)}</span><span class="conviction-pill high">NOVA POSIÇÃO</span><span class="launch-age">${age(Number(purchase.purchased_at_unix) * 1000)}</span></div>
          <div class="purchase-wallet-line"><a href="${escapeHTML(purchase.solscan_url)}" target="_blank" rel="noopener noreferrer">Carteira #${Number(purchase.wallet_rank)} · ${escapeHTML(short(purchase.wallet))}</a><b>${money(purchase.wallet_realized_pnl_usd)} realizados · ${compact(purchase.wallet_profitable_memecoins)} memecoins lucrativas</b></div>
          <div class="launch-meta"><span>Recebeu <b>${Number(purchase.token_amount || 0).toLocaleString(locale(), {maximumFractionDigits: 4})} ${escapeHTML(purchase.symbol)}</b></span><span>Pagou <b>${payment}</b></span><span>Origem <b>${escapeHTML(purchase.source)}</b></span></div>
          <div class="launch-meta"><span>Liquidez <b>${money(purchase.liquidity_usd)}</b></span><span>Market cap <b>${money(purchase.mcap_usd)}</b></span><span>Holders <b>${compact(purchase.holder_count)}</b></span><span>Safety <b>${Number(purchase.safety_score || 0)}/100</b></span></div>
          <div class="safety-track" title="Score estrutural, não previsão de retorno"><i style="width:${Math.max(0, Math.min(100, Number(purchase.safety_score)))}%"></i></div>
          <div class="launch-flags">${flagHTML}</div>
        </div>
        <div class="launch-actions"><button class="route-button" data-route-mint="${escapeHTML(purchase.mint)}">Validar rotas Jupiter</button><a class="jupiter-link" href="${escapeHTML(purchase.transaction_url)}" target="_blank" rel="noopener noreferrer">Ver transação ↗</a><a class="jupiter-link" href="${escapeHTML(purchase.jupiter_url)}" target="_blank" rel="noopener noreferrer">Abrir na jup.ag ↗</a><span class="route-result" data-route-result="${escapeHTML(purchase.mint)}">${escapeHTML(alertState)}</span></div>
      </article>`;
    }).join('');
  }

  function renderIntel(data) {
    intelState = data;
    renderProviders(data.providers);
    const summary = data.summary || {};
    const values = {
      '#intelRecentTokens': compact(summary.quality_wallets || 0),
      '#intelEligibleTokens': compact(summary.monitored_wallets || 0),
      '#intelOpportunities': compact(summary.opportunities || 0),
      '#intelQualityWallets': money(summary.realized_pnl_usd || 0),
      '#intelRejectedTokens': compact(summary.pending_alert_delivery || 0),
    };
    Object.entries(values).forEach(([selector, value]) => {
      const element = document.querySelector(selector);
      if (element) element.textContent = value;
    });
    const setup = document.querySelector('#solanaIntelSetup');
    const birdeyeConfigured = Boolean(data.providers?.birdeye?.configured);
    const heliusConfigured = Boolean(data.providers?.helius?.configured);
    const historyPersistent = Boolean(data.providers?.history?.persistent);
    const jupiterAvailable = data.providers?.jupiter?.available === true;
    const errors = data.errors || [];
    setup.classList.toggle('show', !jupiterAvailable || !birdeyeConfigured || !heliusConfigured || !historyPersistent || errors.length > 0);
    setup.innerHTML = !jupiterAvailable
      ? `<span class="solana-error">Jupiter indisponível nesta atualização: ${escapeHTML(errors.find(error => error.provider === 'jupiter')?.message || 'não foi possível consultar os lançamentos agora.')}</span>`
      : !birdeyeConfigured
        ? 'Configure <code>BIRDEYE_API_KEY</code> para descobrir e ranquear as carteiras pelo histórico de PnL realizado.'
        : !heliusConfigured
          ? 'O ranking pode ser calculado, mas o alerta em tempo real exige <code>HELIUS_API_KEY</code>, <code>HELIUS_WEBHOOK_URL</code> e <code>HELIUS_WEBHOOK_SECRET</code> no backend.'
          : !historyPersistent
          ? 'A coleta ampliada está usando memória temporária. Para preservar a janela de centenas de lançamentos entre reinicializações, configure <code>SUPABASE_URL</code>, <code>SUPABASE_SERVICE_ROLE_KEY</code> e o bucket indicado por <code>SUPABASE_STORAGE_BUCKET</code>.'
        : errors.length
          ? `<span class="solana-error">Atualização parcial: ${escapeHTML(errors[0].provider)} · ${escapeHTML(errors[0].message)}</span>`
          : '';
    renderOpportunities(data.opportunities, birdeyeConfigured);
    renderWallets(data.wallets, birdeyeConfigured);
    renderPurchases(data.purchases, heliusConfigured);
    const generated = document.querySelector('#solanaGeneratedAt');
    if (generated) generated.textContent = data.generated_at
      ? `Atualizado ${new Date(data.generated_at * 1000).toLocaleTimeString(locale(), {hour: '2-digit', minute: '2-digit'})} · ${compact(summary.quality_wallets)} carteiras ranqueadas · ${compact(summary.purchase_alerts)} compras novas registradas`
      : 'Ainda não atualizado';
  }

  async function loadIntel(force = false) {
    if (loading) return;
    loading = true;
    const button = document.querySelector('#refreshSolanaIntel');
    if (button) {
      button.disabled = true;
      button.textContent = force ? 'Atualizando…' : 'Carregando…';
    }
    try {
      const data = await api('/api/solana-intel' + (force ? '/refresh' : ''), force ? {method: 'POST'} : {});
      renderIntel(data);
      if (force) toast('Memecoins Analyser atualizado');
    } catch (error) {
      const setup = document.querySelector('#solanaIntelSetup');
      setup.classList.add('show');
      setup.innerHTML = `<span class="solana-error">Não foi possível atualizar o Memecoins Analyser: ${escapeHTML(error.message)}</span>`;
      if (force) toast(error.message, true);
    } finally {
      loading = false;
      if (button) {
        button.disabled = false;
        button.textContent = 'Atualizar análise';
      }
    }
  }

  async function validateRoutes(button) {
    const mint = button.dataset.routeMint;
    const result = document.querySelector(`[data-route-result="${mint}"]`);
    button.disabled = true;
    result.className = 'route-result';
    result.textContent = 'Consultando compra e venda…';
    try {
      const route = await api(`/api/solana-intel/routes/${encodeURIComponent(mint)}?amount_sol=0.25`);
      result.className = `route-result ${route.tradable ? 'good' : 'bad'}`;
      const buy = route.buy.available ? `compra ${route.buy.router || 'ok'}` : 'compra sem rota';
      const sell = route.sell.available ? `venda ${route.sell.router || 'ok'}` : 'venda sem rota';
      result.textContent = `${route.tradable ? 'ROTAS OK' : 'ATENÇÃO'} · ${buy} · ${sell}`;
    } catch (error) {
      result.className = 'route-result bad';
      result.textContent = `Falha: ${error.message}`;
    } finally {
      button.disabled = false;
    }
  }

  document.querySelector('#refreshSolanaIntel')?.addEventListener('click', () => loadIntel(true));
  document.querySelector('#solanaLaunchList')?.addEventListener('click', event => {
    const button = event.target.closest('[data-route-mint]');
    if (button) validateRoutes(button);
  });
  loadIntel();
  setInterval(() => {
    if (!document.hidden && document.querySelector('#solana-intel')) loadIntel();
  }, 120000);
})();
