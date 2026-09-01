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
  };
  const confidenceLabels = {
    robust: 'amostra robusta', established: 'amostra validada', insufficient: 'amostra insuficiente',
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
      box.innerHTML = '<div class="intel-empty"><strong>Nenhuma carteira atingiu o padrão de qualidade</strong>O filtro exige histórico de 90 dias, pelo menos 10 resultados, compras e vendas suficientes, acerto mínimo de 55% e PnL realizado positivo.</div>';
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
            <div class="wallet-stat"><span>Vista em lançamentos</span><b>${compact(wallet.recent_tokens_seen)}</b></div>
          </div>
        </div>
        <div class="wallet-score"><b>${wallet.score}</b><span>score / 100</span><i class="confidence-pill ${escapeHTML(wallet.confidence)}">${confidenceLabels[wallet.confidence] || wallet.confidence}</i></div>
        ${risky ? '<div class="wallet-risk-note">Carteira excluída das oportunidades por risco de vínculo com o lançamento.</div>' : ''}
      </article>`;
    }).join('');
  }

  function boolLabel(value) {
    return value === true ? 'desabilitada' : value === false ? 'ativa' : 'sem dado';
  }

  function renderTokens(tokens = [], birdeyeConfigured = false) {
    const box = document.querySelector('#solanaLaunchList');
    if (!box) return;
    if (!tokens.length) {
      box.innerHTML = birdeyeConfigured
        ? '<div class="intel-empty"><strong>Nenhuma oportunidade passou pelo filtro</strong>Isso é um resultado válido: os lançamentos atuais não combinaram segurança mínima com uma carteira de histórico comprovado. O radar não completa espaço com moedas fracas.</div>'
        : '<div class="intel-empty"><strong>Filtro aguardando a Birdeye</strong>Sem o histórico das carteiras, nenhum lançamento é promovido a oportunidade.</div>';
      return;
    }
    box.innerHTML = tokens.map(token => {
      const flags = token.risk_flags || [];
      const icon = token.icon
        ? `<img src="${escapeHTML(token.icon)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
        : escapeHTML((token.symbol || '?').slice(0, 2));
      const flagHTML = flags.length
        ? flags.map(flag => `<span class="risk-flag">${escapeHTML(flagLabels[flag] || flag)}</span>`).join('')
        : '<span class="risk-flag clean">sem alerta estrutural nos campos disponíveis</span>';
      const reasons = (token.reasons || []).map(reason => `<li>${escapeHTML(reason)}</li>`).join('');
      const evidence = (token.wallet_evidence || []).map(wallet => `<a class="opportunity-wallet" href="${escapeHTML(wallet.solscan_url)}" target="_blank" rel="noopener noreferrer">
        <span>${escapeHTML(short(wallet.wallet))}${wallet.early ? ' · EARLY' : ''}</span>
        <b>${Number(wallet.win_rate_pct).toFixed(1)}% · ${compact(wallet.outcomes)} resultados · ${money(wallet.realized_pnl_usd)}</b>
      </a>`).join('');
      const conviction = token.conviction === 'high' ? 'alta convicção' : 'seletiva';
      return `<article class="launch-card opportunity-card" data-mint="${escapeHTML(token.mint)}">
        <div class="launch-icon">${icon}</div>
        <div>
          <div class="launch-name-row"><span class="launch-name">${escapeHTML(token.symbol)} · ${escapeHTML(token.name)}</span><span class="conviction-pill ${escapeHTML(token.conviction)}">${conviction}</span><span class="launch-age">${age(token.first_pool_at)}</span></div>
          <div class="opportunity-score"><b>${Number(token.opportunity_score)}</b><span>score da oportunidade</span><i>${compact(token.quality_wallet_count)} carteira(s) qualificada(s)</i></div>
          <div class="launch-meta"><span>Liquidez <b>${money(token.liquidity_usd)}</b></span><span>Holders <b>${compact(token.holder_count)}</b></span><span>Organic <b>${Number(token.organic_score || 0).toFixed(0)}</b></span><span>Top holders <b>${token.top_holders_pct == null ? '—' : `${Number(token.top_holders_pct).toFixed(1)}%`}</b></span></div>
          <div class="launch-meta"><span>Mint <b>${boolLabel(token.mint_authority_disabled)}</b></span><span>Freeze <b>${boolLabel(token.freeze_authority_disabled)}</b></span><span>Traders 5m <b>${compact(token.traders_5m)}</b></span></div>
          <div class="safety-track" title="Score estrutural, não previsão de retorno"><i style="width:${Math.max(0, Math.min(100, Number(token.safety_score)))}%"></i></div>
          <div class="launch-flags">${flagHTML}</div>
          <ul class="opportunity-reasons">${reasons}</ul>
          <div class="opportunity-wallets">${evidence}</div>
        </div>
        <div class="launch-actions"><button class="route-button" data-route-mint="${escapeHTML(token.mint)}">Validar rotas Jupiter</button><a class="jupiter-link" href="${escapeHTML(token.jupiter_url)}" target="_blank" rel="noopener noreferrer">Abrir na jup.ag ↗</a><span class="route-result" data-route-result="${escapeHTML(token.mint)}">Somente cotação · 0,25 SOL</span></div>
      </article>`;
    }).join('');
  }

  function renderIntel(data) {
    intelState = data;
    renderProviders(data.providers);
    const summary = data.summary || {};
    const values = {
      '#intelRecentTokens': summary.launches_in_window || 0,
      '#intelEligibleTokens': summary.analyzed_tokens || 0,
      '#intelOpportunities': summary.opportunities || 0,
      '#intelQualityWallets': summary.quality_wallets || 0,
      '#intelRejectedTokens': summary.pending_tokens || 0,
    };
    Object.entries(values).forEach(([selector, value]) => {
      const element = document.querySelector(selector);
      if (element) element.textContent = compact(value);
    });
    const setup = document.querySelector('#solanaIntelSetup');
    const birdeyeConfigured = Boolean(data.providers?.birdeye?.configured);
    const historyPersistent = Boolean(data.providers?.history?.persistent);
    const jupiterAvailable = data.providers?.jupiter?.available === true;
    const errors = data.errors || [];
    setup.classList.toggle('show', !jupiterAvailable || !birdeyeConfigured || !historyPersistent || errors.length > 0);
    setup.innerHTML = !jupiterAvailable
      ? `<span class="solana-error">Jupiter indisponível nesta atualização: ${escapeHTML(errors.find(error => error.provider === 'jupiter')?.message || 'não foi possível consultar os lançamentos agora.')}</span>`
      : !birdeyeConfigured
        ? 'Jupiter está ativa para descoberta e rotas. Nenhum token será promovido sem a evidência histórica da carteira; configure <code>BIRDEYE_API_KEY</code> no backend. Helius permanece opcional.'
        : !historyPersistent
          ? 'A coleta ampliada está usando memória temporária. Para preservar a janela de centenas de lançamentos entre reinicializações, configure <code>SUPABASE_URL</code>, <code>SUPABASE_SERVICE_ROLE_KEY</code> e o bucket indicado por <code>SUPABASE_STORAGE_BUCKET</code>.'
        : errors.length
          ? `<span class="solana-error">Atualização parcial: ${escapeHTML(errors[0].provider)} · ${escapeHTML(errors[0].message)}</span>`
          : '';
    renderWallets(data.wallets, birdeyeConfigured);
    renderTokens(data.opportunities, birdeyeConfigured);
    const generated = document.querySelector('#solanaGeneratedAt');
    if (generated) generated.textContent = data.generated_at
      ? `Atualizado ${new Date(data.generated_at * 1000).toLocaleTimeString(locale(), {hour: '2-digit', minute: '2-digit'})} · ${compact(summary.analyzed_this_cycle)} neste ciclo · janela ${compact(summary.launches_in_window)}/${compact(summary.history_capacity)}`
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
