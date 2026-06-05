// =====================================================
// QUANTUS AI — Autonomous Trading Intelligence
// Main Application Logic
// =====================================================

// NOTIFICATION SYSTEM
let notifTimer;
function showNotif(title, body, type = 'blue') {
  const n = document.getElementById('notif');
  document.getElementById('notif-title-text').textContent = title;
  document.getElementById('notif-body').textContent = body;
  n.style.borderColor = type === 'red' ? 'rgba(255,79,109,0.4)' : 'rgba(99,140,255,0.3)';
  n.classList.add('show');
  clearTimeout(notifTimer);
  notifTimer = setTimeout(() => n.classList.remove('show'), 4500);
}

// TAB NAVIGATION
function showTab(tab) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  if (event && event.currentTarget) event.currentTarget.classList.add('active');
  const names = {
    'signals': 'AI Signals', 'nifty': 'Nifty / BankNifty', 'fo': 'F&O Options Chain',
    'watchlist': 'Watchlist', 'research': 'Deep Research', 'predictions': 'AI Predictions',
    'sector': 'Sector Analysis', 'positions': 'Positions', 'auto': 'Auto-Trade Engine',
    'risk': 'Risk Manager', 'backtest': 'Backtest Studio', 'chat': 'AI Analyst'
  };
  if (names[tab]) showNotif('📱 ' + names[tab], 'Feature in full production build. Dashboard showing overview.');
}

// RENDER DASHBOARD
function renderDashboard() {
  const content = document.getElementById('mainContent');
  content.innerHTML = `
  <!-- STAT CARDS -->
  <div class="grid-4">
    <div class="card card-sm">
      <div class="card-header"><div class="card-title">Today's P&L</div><div class="card-badge badge-green">+Live</div></div>
      <div class="stat-big up">+₹14,680</div>
      <div class="stat-change up">▲ +2.94% from yesterday</div>
      <div class="stat-sub">Realized: ₹9,200 · Unrealized: ₹5,480</div>
    </div>
    <div class="card card-sm">
      <div class="card-header"><div class="card-title">Portfolio Value</div><div class="card-badge badge-blue">6 Holdings</div></div>
      <div class="stat-big" style="color:var(--accent)">₹5,14,320</div>
      <div class="stat-change up">▲ +₹42,100 MTD</div>
      <div class="stat-sub">Deployed: 68% · Cash: 32%</div>
    </div>
    <div class="card card-sm">
      <div class="card-header"><div class="card-title">AI Accuracy</div><div class="card-badge badge-purple">30d avg</div></div>
      <div class="stat-big" style="color:var(--purple)">84.3%</div>
      <div class="stat-change up">▲ +2.1% vs last month</div>
      <div class="stat-sub">Win Rate · 67 of 79 signals</div>
    </div>
    <div class="card card-sm">
      <div class="card-header"><div class="card-title">Risk Score</div><div class="card-badge badge-amber">Moderate</div></div>
      <div class="stat-big" style="color:var(--amber)">34/100</div>
      <div class="stat-change" style="color:var(--text2)">Max Drawdown: -3.2%</div>
      <div class="stat-sub">Sharpe: 2.14 · Beta: 0.72</div>
    </div>
  </div>

  <!-- CHART + SIGNALS -->
  <div class="grid-2-1">
    <div class="card">
      <div class="card-header">
        <div class="card-title">Portfolio Performance</div>
        <div style="display:flex;gap:8px;align-items:center">
          <div class="tabs" style="margin-bottom:0;border:none">
            <div class="tab active" id="tab1d">1D</div>
            <div class="tab" id="tab1w" onclick="switchChart('1w')">1W</div>
            <div class="tab" id="tab1m" onclick="switchChart('1m')">1M</div>
            <div class="tab" id="tab3m" onclick="switchChart('3m')">3M</div>
          </div>
          <div class="card-badge badge-green">+12.4% YTD</div>
        </div>
      </div>
      <div style="height:220px"><canvas id="portfolioChart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-header"><div class="card-title">Top AI Signals</div><div class="card-badge badge-blue">12 active</div></div>
      <div id="signals-list">
        ${renderSignals()}
      </div>
    </div>
  </div>

  <!-- SECTOR + LIVE FEED -->
  <div class="grid-1-1">
    <div class="card">
      <div class="card-header"><div class="card-title">Sector Heatmap</div><div class="card-badge badge-blue">NSE · Live</div></div>
      <div class="heatmap">
        ${renderHeatmap()}
      </div>
      <div style="margin-top:14px;">
        <div class="prediction-grid">
          <div class="pred-item"><div class="pred-horizon">Nifty 1D</div><div class="pred-val up">24,960</div><div class="pred-conf">Conf: 78%</div></div>
          <div class="pred-item"><div class="pred-horizon">Nifty 1W</div><div class="pred-val up">25,280</div><div class="pred-conf">Conf: 64%</div></div>
          <div class="pred-item"><div class="pred-horizon">BNifty 1D</div><div class="pred-val up">52,750</div><div class="pred-conf">Conf: 72%</div></div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-header"><div class="card-title">Live Intelligence Feed</div><div class="card-badge badge-amber">Real-time</div></div>
      <div class="card-scroll">${renderFeed()}</div>
    </div>
  </div>

  <!-- POSITIONS + RISK -->
  <div class="grid-2-1">
    <div class="card">
      <div class="card-header"><div class="card-title">Open Positions</div><div style="display:flex;gap:6px"><div class="card-badge badge-green">3 Long</div><div class="card-badge badge-red">1 Short</div></div></div>
      ${renderPositions()}
    </div>
    <div class="card">
      <div class="card-header"><div class="card-title">Risk Dashboard</div><div class="card-badge badge-green">Safe Zone</div></div>
      ${renderRisk()}
    </div>
  </div>

  <!-- OPTIONS + CHAT -->
  <div class="grid-1-1">
    <div class="card">
      <div class="card-header"><div class="card-title">F&O Options Chain — BANKNIFTY</div><div class="card-badge badge-blue">Expiry: 27 Mar</div></div>
      <div style="overflow-x:auto">${renderOptionsChain()}</div>
      <div style="margin-top:12px;display:flex;gap:8px;font-size:11px;color:var(--text3)">
        <span>PCR: <strong style="color:var(--amber)">0.84</strong></span><span>·</span>
        <span>Max Pain: <strong style="color:var(--text)">52,400</strong></span><span>·</span>
        <span>IV Rank: <strong style="color:var(--green)">32</strong></span><span>·</span>
        <span>Expiry: <strong style="color:var(--text)">3 days</strong></span>
      </div>
    </div>
    <div class="card">
      <div class="card-header"><div class="card-title">AI Analyst — Ask Anything</div><div class="card-badge badge-purple">GPT-4 Powered</div></div>
      ${renderChat()}
    </div>
  </div>

  <!-- DEEP RESEARCH -->
  <div class="card" style="margin-bottom:20px">
    <div class="card-header"><div class="card-title">Deep Research Reports — AI Generated</div><div class="card-badge badge-purple">AI Analyst · Live</div></div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">${renderResearch()}</div>
  </div>`;

  initChart();
  startSignalUpdates();
}

// COMPONENT RENDERERS
function renderSignals() {
  const signals = [
    { t: 'ICICIBNK', s: 91, a: 'BUY', c: 'green', msg: '📊 ICICI BANK Signal|BUY · Target ₹1,510 · SL ₹1,400 · Confidence 91%' },
    { t: 'TCS', s: 87, a: 'BUY', c: 'green', msg: '📊 TCS Signal|BUY · Target ₹4,450 · SL ₹3,980 · Confidence 87%' },
    { t: 'BAJFIN', s: 82, a: 'SELL', c: 'red', msg: '📊 BAJFINANCE Signal|SELL · Target ₹6,200 · SL ₹7,050 · Confidence 82%' },
    { t: 'WIPRO', s: 71, a: 'HOLD', c: 'amber', msg: '📊 WIPRO Signal|HOLD · Awaiting breakout confirmation · Confidence 71%' },
    { t: 'HDFCBNK', s: 78, a: 'BUY', c: 'green', msg: '📊 HDFCBANK Signal|BUY · Target ₹1,960 · SL ₹1,820 · Confidence 78%' },
    { t: 'NIFTY FO', s: 69, a: 'PUT', c: 'accent', msg: '📊 NIFTY50 F&O Signal|PUT BUY 24800 · Expiry 27 Mar · Confidence 69%' },
  ];
  return signals.map(s => {
    const actionCls = s.a === 'SELL' ? 'sell-action' : s.a === 'HOLD' ? 'hold-action' : 'buy-action';
    const scoreCls = s.c === 'red' ? 'dn' : s.c === 'green' ? 'up' : '';
    const scoreStyle = s.c === 'amber' ? 'style="color:var(--amber)"' : s.c === 'accent' ? 'style="color:var(--accent)"' : '';
    const barColor = s.c === 'red' ? 'var(--red)' : s.c === 'green' ? 'var(--green)' : s.c === 'amber' ? 'var(--amber)' : 'var(--accent)';
    const [title, body] = s.msg.split('|');
    return `<div class="signal-row" onclick="showNotif('${title}','${body}')">
      <div class="signal-ticker">${s.t}</div>
      <div class="signal-bar"><div class="signal-fill" style="width:${s.s}%;background:${barColor}"></div></div>
      <div class="signal-score ${scoreCls}" ${scoreStyle}>${s.s}</div>
      <div class="signal-action ${actionCls}">${s.a}</div>
    </div>`;
  }).join('');
}

function renderHeatmap() {
  const sectors = [
    { n: 'Banking', c: '+1.84%', bg: 'rgba(34,211,165,0.18)', cl: 'var(--green)', msg: '🏦 Banking|Strong institutional buying. HDFC, ICICI leading gains.' },
    { n: 'IT', c: '+0.92%', bg: 'rgba(34,211,165,0.12)', cl: 'var(--green)', msg: '💻 IT|TCS, Infosys recovering after US tech rally overnight.' },
    { n: 'Energy', c: '-0.64%', bg: 'rgba(255,79,109,0.14)', cl: 'var(--red)', msg: '🛢 Energy|RIL dragged by crude oil dip. Short-term bearish.' },
    { n: 'Pharma', c: '+0.38%', bg: 'rgba(34,211,165,0.08)', cl: 'var(--green)', msg: '💊 Pharma|Sun Pharma outperforming. FDA approval cycle positive.' },
    { n: 'Realty', c: '+0.12%', bg: 'rgba(245,158,11,0.14)', cl: 'var(--amber)', msg: '🏗 Realty|Consolidation phase. DLF near key resistance.' },
    { n: 'Auto', c: '+1.23%', bg: 'rgba(34,211,165,0.16)', cl: 'var(--green)', msg: '🏭 Auto|EV push. Tata Motors, M&M showing momentum.' },
    { n: 'FMCG', c: '-0.31%', bg: 'rgba(255,79,109,0.10)', cl: 'var(--red)', msg: '🧱 FMCG|ITC, HUL under pressure. Rural demand still soft.' },
    { n: 'Infra', c: '+2.10%', bg: 'rgba(34,211,165,0.20)', cl: 'var(--green)', msg: '🏗 Infra|Govt capex boost. L&T, NTPC strong bullish trend.' },
  ];
  return sectors.map(s => {
    const [t, b] = s.msg.split('|');
    return `<div class="heat-cell" style="background:${s.bg};color:${s.cl}" onclick="showNotif('${t}','${b}')">
      <div class="heat-name">${s.n}</div><div class="heat-chg">${s.c}</div></div>`;
  }).join('');
}

function renderFeed() {
  const items = [
    { t: '13:41', c: 'var(--green)', txt: '<strong>AUTO TRADE</strong> · Bought 50 ICICI BANK @ ₹1,435 via Zerodha. SL set ₹1,400.' },
    { t: '13:38', c: 'var(--accent)', txt: '<strong>PATTERN</strong> · TCS Cup-and-Handle breakout detected. High-confidence BUY setup forming.' },
    { t: '13:31', c: 'var(--red)', txt: '<strong>RISK ALERT</strong> · BAJFINANCE OI build-up at 6,800 PUT. Bears loading up. Caution advised.' },
    { t: '13:20', c: 'var(--amber)', txt: '<strong>NEWS</strong> · RBI holds repo rate at 6.5%. Markets relieved — banking sector rally likely to extend.' },
    { t: '13:05', c: 'var(--green)', txt: '<strong>FII/DII</strong> · FIIs net buyers ₹1,240 Cr. DIIs ₹680 Cr. Broad market sentiment positive.' },
    { t: '12:47', c: 'var(--purple)', txt: '<strong>AI RESEARCH</strong> · Infra sector deep-dive complete. Top picks: L&T, NTPC, IRFC — 3–6 month horizon.' },
    { t: '12:30', c: 'var(--red)', txt: '<strong>AUTO TRADE</strong> · Exited WIPRO 100 shares @ ₹489. +₹2,400 profit. 52-day high resistance hit.' },
    { t: '11:52', c: 'var(--amber)', txt: '<strong>MACRO</strong> · US Fed minutes: no rate cut signal. INR marginally weaker. Gold supportive level.' },
  ];
  return items.map(i => `<div class="feed-item"><div class="feed-dot" style="background:${i.c}"></div><div class="feed-time">${i.t}</div><div class="feed-text">${i.txt}</div></div>`).join('');
}

function renderPositions() {
  const rows = [
    { n: 'ICICI BANK', sub: 'NSE Delivery', type: 'LONG', bc: 'badge-green', qty: '50', avg: '₹1,435', ltp: '₹1,436', pnl: '+₹50', cls: 'up' },
    { n: 'TCS', sub: 'NSE Delivery', type: 'LONG', bc: 'badge-green', qty: '15', avg: '₹4,050', ltp: '₹4,126', pnl: '+₹1,140', cls: 'up' },
    { n: 'NIFTY 25000 CE', sub: 'F&O · Weekly', type: 'CALL', bc: 'badge-blue', qty: '4 lots', avg: '₹142', ltp: '₹168', pnl: '+₹5,200', cls: 'up' },
    { n: 'BAJFINANCE', sub: 'Futures Short', type: 'SHORT', bc: 'badge-red', qty: '1 lot', avg: '₹6,900', ltp: '₹6,782', pnl: '+₹4,720', cls: 'up' },
  ];
  return `<table class="pos-table"><thead><tr><th>Stock</th><th>Type</th><th>Qty</th><th>Avg Cost</th><th>LTP</th><th>P&L</th><th>Action</th></tr></thead><tbody>${rows.map(r =>
    `<tr><td><div class="pos-name">${r.n}</div><div class="pos-type">${r.sub}</div></td>
    <td><span class="card-badge ${r.bc}">${r.type}</span></td>
    <td style="font-family:var(--mono)">${r.qty}</td><td style="font-family:var(--mono)">${r.avg}</td>
    <td style="font-family:var(--mono)">${r.ltp}</td><td class="${r.cls}" style="font-family:var(--mono)">${r.pnl}</td>
    <td><button class="btn" style="padding:4px 8px;font-size:10px" onclick="showNotif('Exit Order Placed','${r.n} @ Market')">Exit</button></td></tr>`
  ).join('')}</tbody></table>`;
}

function renderRisk() {
  return `<div style="margin-bottom:16px;">
    <div class="risk-meter-wrap"><div class="risk-label"><span>Capital Risk</span><span class="up">12%</span></div><div class="risk-track"><div class="risk-fill" style="width:12%;background:var(--green)"></div></div></div>
    <div class="risk-meter-wrap"><div class="risk-label"><span>Portfolio Beta</span><span style="color:var(--accent)">0.72</span></div><div class="risk-track"><div class="risk-fill" style="width:72%;background:var(--accent)"></div></div></div>
    <div class="risk-meter-wrap"><div class="risk-label"><span>VaR (95%)</span><span style="color:var(--amber)">₹8,200</span></div><div class="risk-track"><div class="risk-fill" style="width:34%;background:var(--amber)"></div></div></div>
    <div class="risk-meter-wrap"><div class="risk-label"><span>Max Drawdown</span><span class="dn">-3.2%</span></div><div class="risk-track"><div class="risk-fill" style="width:32%;background:var(--red)"></div></div></div>
    <div class="risk-meter-wrap"><div class="risk-label"><span>Concentration</span><span style="color:var(--amber)">41%</span></div><div class="risk-track"><div class="risk-fill" style="width:41%;background:var(--amber)"></div></div></div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
    <div class="pred-item"><div class="pred-horizon">Sharpe Ratio</div><div class="pred-val up">2.14</div></div>
    <div class="pred-item"><div class="pred-horizon">Sortino</div><div class="pred-val up">3.07</div></div>
  </div>
  <div style="margin-top:14px;"><div class="section-title">Auto-Trade Settings</div>
    <div style="display:flex;flex-direction:column;gap:8px;font-size:12px;">
      <label style="display:flex;justify-content:space-between;align-items:center;color:var(--text2)">Auto Buy <input type="checkbox" checked style="accent-color:var(--accent)"></label>
      <label style="display:flex;justify-content:space-between;align-items:center;color:var(--text2)">Auto Sell <input type="checkbox" checked style="accent-color:var(--accent)"></label>
      <label style="display:flex;justify-content:space-between;align-items:center;color:var(--text2)">Max daily loss limit <span style="font-family:var(--mono);color:var(--text)">₹15,000</span></label>
      <label style="display:flex;justify-content:space-between;align-items:center;color:var(--text2)">Max position size <span style="font-family:var(--mono);color:var(--text)">₹50,000</span></label>
    </div>
  </div>`;
}

function renderOptionsChain() {
  const rows = [
    { c: 'opt-call opt-itm', oi: '2.4L', vol: '8.2K', iv: '12.1', cltp: '440', strike: '52000', pltp: '12', piv: '14.2', pvol: '1.1K', poi: '0.8L' },
    { c: 'opt-call opt-itm', oi: '3.1L', vol: '12.4K', iv: '13.4', cltp: '295', strike: '52200', pltp: '28', piv: '15.1', pvol: '2.3K', poi: '1.4L' },
    { c: 'opt-call', oi: '4.8L', vol: '22.1K', iv: '14.8', cltp: '168', strike: '52400', pltp: '92', piv: '14.8', pvol: '18.9K', poi: '5.2L', atm: true },
    { c: 'opt-put', oi: '2.2L', vol: '9.8K', iv: '15.6', cltp: '78', strike: '52600', pltp: '188', piv: '15.6', pvol: '8.1K', poi: '3.1L' },
    { c: 'opt-put opt-itm', oi: '0.9L', vol: '3.2K', iv: '16.8', cltp: '28', strike: '52800', pltp: '368', piv: '16.8', pvol: '14.2K', poi: '4.6L' },
  ];
  return `<table class="opt-table"><thead><tr>
    <th colspan="4" style="color:var(--green);text-align:center">CALLS</th>
    <th class="opt-strike">STRIKE</th>
    <th colspan="4" style="color:var(--red);text-align:center">PUTS</th>
  </tr><tr><th>OI</th><th>Vol</th><th>IV%</th><th>LTP</th><th></th><th>LTP</th><th>IV%</th><th>Vol</th><th>OI</th></tr></thead>
  <tbody>${rows.map(r => `<tr class="${r.c}" ${r.atm ? 'style="background:rgba(99,140,255,0.08)"' : ''}>
    <td>${r.oi}</td><td>${r.vol}</td><td>${r.iv}</td><td class="up">${r.cltp}</td>
    <td class="opt-strike" ${r.atm ? 'style="background:rgba(99,140,255,0.2)"' : ''}>${r.strike}</td>
    <td class="dn">${r.pltp}</td><td>${r.piv}</td><td>${r.pvol}</td><td>${r.poi}</td>
  </tr>`).join('')}</tbody></table>`;
}

function renderChat() {
  return `<div class="ai-chat">
    <div class="chat-messages" id="chatMessages">
      <div class="chat-msg"><div class="chat-avatar ai-avatar">Q</div>
        <div class="chat-bubble">Good afternoon. Markets are bullish today with Banking and Infra leading. I've placed 1 auto-trade on ICICI BANK. Your portfolio is up ₹14,680 today. What would you like to analyze?</div></div>
      <div class="chat-msg user"><div class="chat-avatar user-avatar">U</div>
        <div class="chat-bubble">Should I buy Bank Nifty calls today?</div></div>
      <div class="chat-msg"><div class="chat-avatar ai-avatar">Q</div>
        <div class="chat-bubble">Based on current OI data, PCR at 0.84 (slightly bearish), and BNifty at 52,318 — the 52,400 CE is the ATM strike with max OI. I see a short-term rally potential to 52,750. <strong style="color:var(--green)">Recommended:</strong> Buy 52,400 CE @ ₹168 with SL at ₹120 and target ₹240. Position size: 2 lots only given 3-day expiry risk.</div></div>
    </div>
    <div class="chat-input-row">
      <input class="chat-input" id="chatInput" type="text" placeholder="Ask about any stock, F&O strategy, sector..." onkeydown="if(event.key==='Enter')sendChat()">
      <button class="chat-send" onclick="sendChat()">Ask</button>
    </div>
  </div>
  <div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:5px;">
    <button class="btn" style="font-size:10px;padding:4px 8px" onclick="quickChat('Best intraday picks today?')">Intraday picks</button>
    <button class="btn" style="font-size:10px;padding:4px 8px" onclick="quickChat('Nifty prediction for this week?')">Nifty outlook</button>
    <button class="btn" style="font-size:10px;padding:4px 8px" onclick="quickChat('Best long-term stocks to buy now?')">Long-term buys</button>
    <button class="btn" style="font-size:10px;padding:4px 8px" onclick="quickChat('Analyze my portfolio risk')">Portfolio risk</button>
  </div>`;
}

function renderResearch() {
  const items = [
    { title: 'Banking Sector Deep Dive', time: '2h ago', meta: 'AI analyzed 847 data points across 12 public and private sector banks. Bullish outlook driven by credit growth...', tags: [['BULLISH','badge-green'],['Banking','badge-blue'],['AI Report','badge-purple']], msg: '📊 Banking Sector Deep Dive|Full 12-page AI report generated. Covers all PSU & private banks, RBI policy impact, credit growth data, NPA trends and 6-month projections.' },
    { title: 'NIFTY Weekly Options Strategy', time: '4h ago', meta: 'Expiry analysis for 27 March. Max pain at 24,900. Iron Condor strategy recommended for range-bound conditions...', tags: [['NEUTRAL','badge-amber'],['F&O','badge-blue'],['Expiry Week','badge-amber']], msg: '📊 NIFTY Options Strategy Report|AI-generated strategy: Iron Condor 24,800-25,200 recommended for range-bound market this week.' },
    { title: 'IT Sector Q4 Earnings Preview', time: 'Yesterday', meta: 'AI-generated earnings model for top IT companies. TCS, Infosys, Wipro, HCL analyzed with DCF valuations...', tags: [['BULLISH','badge-green'],['IT','badge-blue'],['Earnings','badge-blue']], msg: '📊 IT Sector Earnings Preview|TCS Q4 results due. AI predicts 8.2% revenue growth YoY. Infosys guidance likely to be upgraded.' },
  ];
  return items.map(i => {
    const [t, b] = i.msg.split('|');
    return `<div class="research-item" style="border:1px solid var(--border);border-radius:var(--r);padding:14px;cursor:pointer" onclick="showNotif('${t}','${b}')">
      <div class="research-header"><div class="research-title">${i.title}</div><div class="research-time">${i.time}</div></div>
      <div class="research-meta">${i.meta}</div>
      <div class="research-tags">${i.tags.map(([label, cls]) => `<span class="tag ${cls}">${label}</span>`).join('')}</div>
    </div>`;
  }).join('');
}

// CHART
let portfolioChart;
const labels1d = ['09:15','09:30','10:00','10:30','11:00','11:30','12:00','12:30','13:00','13:30','13:42'];
const data1d = [499640, 501200, 503800, 502400, 506200, 508800, 510400, 509100, 511600, 513200, 514320];

function initChart() {
  const ctx = document.getElementById('portfolioChart').getContext('2d');
  portfolioChart = new Chart(ctx, {
    type: 'line',
    data: { labels: labels1d, datasets: [{ label: 'Portfolio Value', data: data1d, borderColor: '#638cff', backgroundColor: 'rgba(99,140,255,0.08)', fill: true, tension: 0.4, pointRadius: 0, pointHoverRadius: 4, borderWidth: 2 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { backgroundColor: '#1a2030', borderColor: '#638cff', borderWidth: 1, titleColor: '#8892a8', bodyColor: '#e8ecf4', callbacks: { label: ctx => '₹' + ctx.raw.toLocaleString('en-IN') } } },
      scales: {
        x: { grid: { color: 'rgba(99,140,255,0.06)' }, ticks: { color: '#4a5470', font: { size: 10 } } },
        y: { grid: { color: 'rgba(99,140,255,0.06)' }, ticks: { color: '#4a5470', font: { size: 10 }, callback: v => '₹' + (v / 1000).toFixed(0) + 'K' } }
      }
    }
  });
}

function switchChart(period) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  const el = document.getElementById('tab' + period);
  if (el) el.classList.add('active');
  const datasets = {
    '1w': [489000, 495000, 492000, 498000, 503000, 508000, 514320],
    '1m': [470000, 475000, 468000, 480000, 492000, 500000, 495000, 510000, 514320],
    '3m': [440000, 445000, 460000, 448000, 470000, 480000, 475000, 492000, 500000, 505000, 514320]
  };
  const lbls = { '1w': ['Mon','Tue','Wed','Thu','Fri','Mon','Tue'], '1m': Array.from({ length: 9 }, (_, i) => `Mar ${i + 1}`), '3m': ['Jan','','Feb','','Mar','','','','','','Now'] };
  portfolioChart.data.labels = lbls[period] || labels1d;
  portfolioChart.data.datasets[0].data = datasets[period] || data1d;
  portfolioChart.update();
}

// CHAT SYSTEM
const chatResponses = {
  'intraday': 'Top intraday picks for today: 1) ICICI BANK — Buy above ₹1,437, target ₹1,455, SL ₹1,425. 2) TCS — Buy above ₹4,130, target ₹4,165, SL ₹4,100. 3) RELIANCE — Wait for pullback to ₹2,880 before entry.',
  'nifty': 'Nifty weekly outlook: Bullish bias. Support at 24,600, resistance at 25,100. Expect range 24,700–25,200 this week. Key trigger: FII flow and global cues. AI probability of crossing 25,000: 62%.',
  'long': 'Best long-term stocks (12–24 month view): 1) HDFC Bank — Buy on dips ₹1,850. 2) L&T — Infrastructure boom play. 3) Sun Pharma — US FDA clearances positive. 4) Tata Motors — EV dominance story intact.',
  'risk': 'Your portfolio risk analysis: Current beta 0.72 (below market risk). Concentration in Banking: 41% — slightly high, consider diversifying. VaR suggests max single-day loss ₹8,200 at 95% confidence. Recommendation: Add 1 Pharma or FMCG position to hedge.',
  'default': "I've analyzed that query using 847 real-time data points across NSE, BSE, and macro indicators. Based on current momentum, technical patterns, and sentiment analysis — the outlook appears positive. Shall I generate a detailed report with entry/exit levels?"
};

function sendChat() {
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg) return;
  addChatMsg(msg, true);
  input.value = '';
  setTimeout(() => {
    const lower = msg.toLowerCase();
    let resp = chatResponses.default;
    if (lower.includes('intraday') || lower.includes('today')) resp = chatResponses.intraday;
    else if (lower.includes('nifty') || lower.includes('week')) resp = chatResponses.nifty;
    else if (lower.includes('long') || lower.includes('invest')) resp = chatResponses.long;
    else if (lower.includes('risk') || lower.includes('portfolio')) resp = chatResponses.risk;
    addChatMsg(resp, false);
  }, 800);
}

function quickChat(q) { document.getElementById('chatInput').value = q; sendChat(); }

function addChatMsg(text, isUser) {
  const div = document.createElement('div');
  div.className = 'chat-msg' + (isUser ? ' user' : '');
  div.innerHTML = `<div class="chat-avatar ${isUser ? 'user-avatar' : 'ai-avatar'}">${isUser ? 'U' : 'Q'}</div><div class="chat-bubble">${text}</div>`;
  const container = document.getElementById('chatMessages');
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// LIVE SIGNAL UPDATES
function startSignalUpdates() {
  setInterval(() => {
    const scores = document.querySelectorAll('.signal-score');
    scores.forEach(s => {
      const v = parseInt(s.textContent);
      const delta = Math.round((Math.random() - 0.48) * 3);
      const newVal = Math.max(50, Math.min(99, v + delta));
      s.textContent = newVal;
      const fill = s.closest('.signal-row').querySelector('.signal-fill');
      fill.style.width = newVal + '%';
    });
  }, 4000);
}

// INIT
document.addEventListener('DOMContentLoaded', () => {
  renderDashboard();
  setTimeout(() => showNotif('🤖 QUANTUS AI Ready', 'Auto-trade engine active. 12 signals generated. Portfolio up +₹14,680 today.'), 1200);
});
