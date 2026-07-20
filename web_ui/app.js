(function () {
  'use strict';

  const emptyState = document.getElementById('empty-state');
  const comparisonEmpty = document.getElementById('comparison-empty');
  const comparisonCards = document.getElementById('comparison-cards');
  const scenariosSidebar = document.getElementById('scenarios-sidebar');
  const scenarioListEl = document.getElementById('scenario-list');
  const maxSelectionMessage = document.getElementById('max-selection-message');
  const btnAddScenario = document.getElementById('btn-add-scenario');
  const btnAddScenarioSidebar = document.getElementById('btn-add-scenario-sidebar');
  const modal = document.getElementById('scenario-modal');
  const modalBackdrop = document.getElementById('modal-backdrop');
  const modalClose = document.getElementById('modal-close');
  const modalCancel = document.getElementById('modal-cancel');
  const modalSave = document.getElementById('modal-save');
  const scenarioText = document.getElementById('scenario-text');
  const upload1040 = document.getElementById('upload-1040');

  // In-memory list of scenarios. Schema: { id, text, createdAt, tax_year?, displayName?, projectionOf? }
  // tax_year: from scenario text or data_model. Strategies only apply when tax_year === 2026.
  let scenarios = [];
  let editingScenarioId = null; // set when editing an existing scenario
  var MAX_COMPARE = 3;
  var selectedForComparison = []; // up to 3 scenario ids to show side-by-side. Baseline (first) cannot be deleted.
  var currentView = 'comparison'; // 'comparison' | 'strategies'

  const modalTitleEl = document.getElementById('modal-title');
  const uploadSection = document.getElementById('upload-section');
  const copyFromBaselineSection = document.getElementById('copy-from-baseline-section');
  const copyFromBaselineSelect = document.getElementById('copy-from-baseline');
  const insightsView = document.getElementById('insights-view');
  const backToComparison = document.getElementById('back-to-comparison');
  const insightsTitle = document.getElementById('insights-title');
  const insightsPrerequisite = document.getElementById('insights-prerequisite');
  const insightsActions = document.getElementById('insights-actions');
  const insightsLoading = document.getElementById('insights-loading');
  const insightsCards = document.getElementById('insights-cards');
  const insightsPlaceholder = document.getElementById('insights-placeholder');
  const btnSaveInsights = document.getElementById('btn-save-insights');
  const btnRecalculateInsights = document.getElementById('btn-recalculate-insights');

  var currentScenarioIdForInsights = null; // scenario id when viewing insights
  var currentInsightsStrategies = [];     // last fetched/loaded strategies (for save)
  var STORAGE_PREFIX = 'project_air_insights_';
  var hide2024Actual = false;
  var WORKSPACE_STATE_VERSION = 1;

  var btnWorkspaceSave = document.getElementById('btn-workspace-save');
  var btnWorkspaceLoad = document.getElementById('btn-workspace-load');
  var workspaceLoadModal = document.getElementById('workspace-load-modal');
  var workspaceLoadBackdrop = document.getElementById('workspace-load-backdrop');
  var workspaceSnapshotSelect = document.getElementById('workspace-snapshot-select');
  var workspaceLoadClose = document.getElementById('workspace-load-close');
  var workspaceLoadCancel = document.getElementById('workspace-load-cancel');
  var workspaceLoadConfirm = document.getElementById('workspace-load-confirm');
  var workspaceLoadStatus = document.getElementById('workspace-load-status');

  function openModal(forScenarioId) {
    editingScenarioId = forScenarioId || null;
    if (editingScenarioId) {
      var s = scenarios.find(function (sc) { return sc.id === editingScenarioId; });
      scenarioText.value = s ? s.text : '';
      modalTitleEl.textContent = 'Edit scenario';
    } else {
      scenarioText.value = '';
      modalTitleEl.textContent = 'New tax scenario';
    }
    upload1040.value = '';
    updateModalSecondarySection();
    modal.hidden = false;
    scenarioText.focus();
  }

  function updateModalSecondarySection() {
    if (scenarios.length > 0) {
      uploadSection.hidden = true;
      copyFromBaselineSection.hidden = false;
      var select = copyFromBaselineSelect;
      select.innerHTML = '<option value="">— Select a baseline —</option>';
      scenarios.forEach(function (s, i) {
        var opt = document.createElement('option');
        opt.value = s.id;
        var label = s.displayName || (getTaxYearFromScenario(s) === 2024 ? '2024 Actual' : 'Baseline ' + (i + 1));
        opt.textContent = label;
        select.appendChild(opt);
      });
      select.value = '';
    } else {
      uploadSection.hidden = false;
      copyFromBaselineSection.hidden = true;
    }
  }

  function openModalForNew() {
    openModal(null);
  }

  function openModalForEdit(id) {
    openModal(id);
  }

  function closeModal() {
    modal.hidden = true;
    editingScenarioId = null;
  }

  const API_BASE = ''; // same origin when served by web_ui_server.py

  // Display order and labels for form_1040_calculated_lines (schema keys -> label)
  var FORM_1040_LINE_LABELS = {
    adjusted_gross_income: 'AGI',
    magi: 'MAGI',
    schedule_c_net_profit_or_loss: 'Schedule C net',
    standard_or_itemized_deduction_used: 'Deduction used',
    deduction_amount: 'Deduction amount',
    qbi_deduction: 'QBI deduction',
    taxable_income: 'Taxable income',
    ordinary_income_portion: 'Ordinary income portion',
    preferential_income_portion: 'Preferential income portion',
    net_investment_income: 'Net investment income',
    tax_on_ordinary_income: 'Tax on ordinary income',
    tax_on_preferential_income: 'Tax on preferential income',
    regular_income_tax: 'Regular income tax',
    net_investment_income_tax: 'Net investment income tax',
    tax_before_credits: 'Tax before credits',
    credits_nonrefundable: 'Credits (nonrefundable)',
    tax_after_credits: 'Tax after credits',
    self_employment_tax: 'Self-employment tax',
    additional_medicare_tax: 'Additional Medicare tax',
    other_taxes: 'Other taxes',
    total_tax_liability: 'Total tax',
    total_payments: 'Total payments',
    refundable_credits: 'Refundable credits',
    amount_owed_or_refund: 'Amount owed / refund',
  };
  var FORM_1040_LINE_ORDER = [
    'adjusted_gross_income', 'magi', 'schedule_c_net_profit_or_loss',
    'standard_or_itemized_deduction_used', 'deduction_amount', 'qbi_deduction',
    'taxable_income', 'ordinary_income_portion', 'preferential_income_portion', 'net_investment_income',
    'tax_on_ordinary_income', 'tax_on_preferential_income', 'regular_income_tax',
    'net_investment_income_tax', 'tax_before_credits', 'credits_nonrefundable', 'tax_after_credits',
    'self_employment_tax', 'additional_medicare_tax', 'other_taxes', 'total_tax_liability',
    'total_payments', 'refundable_credits', 'amount_owed_or_refund',
  ];

  function format1040Value(val) {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'number') {
      var n = Number(val);
      if (isNaN(n)) return '—';
      return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return String(val);
  }

  function buildTaxSituationSummary(taxSituation) {
    if (!taxSituation || typeof taxSituation !== 'object') return [];
    var rows = [];
    var p = taxSituation.personal;
    var taxYear = (p && p.tax_year != null) ? p.tax_year : taxSituation.tax_year;
    var filing = (p && p.filing_status) ? p.filing_status : taxSituation.filing_status;
    var deps = (p && Array.isArray(p.dependents)) ? p.dependents : taxSituation.dependents;
    if (taxYear != null) rows.push({ label: 'Tax year', value: String(taxYear) });
    if (filing) rows.push({ label: 'Filing status', value: filing });
    if (Array.isArray(deps) && deps.length) {
      rows.push({ label: 'Dependents', value: String(deps.length) });
    }
    var inc = taxSituation.income;
    if (inc && typeof inc === 'object') {
      if (inc.wages != null && inc.wages !== '') rows.push({ label: 'Wages', value: format1040Value(inc.wages) });
      if (inc.ordinary_dividends != null && inc.ordinary_dividends !== '') rows.push({ label: 'Ordinary dividends', value: format1040Value(inc.ordinary_dividends) });
    }
    return rows;
  }

  function build1040LinesSection(lines) {
    if (!lines || typeof lines !== 'object') return [];
    var out = [];
    FORM_1040_LINE_ORDER.forEach(function (key) {
      if (!(key in lines)) return;
      var val = lines[key];
      if (val === null || val === undefined || val === '') return;
      var label = FORM_1040_LINE_LABELS[key] || key.replace(/_/g, ' ');
      out.push({ label: label, value: format1040Value(val) });
    });
    return out;
  }

  var STRATEGY_TITLES = { ita_002: 'S-Corp Conversion', ita_025: 'Bonus Depreciation' };

  /** Parse tax year from scenario text. Prefer "tax year 20XX", else first 2024/2025/2026. Returns number or null. */
  function parseTaxYearFromText(text) {
    if (!text || typeof text !== 'string') return null;
    var m = text.match(/\b[Tt]ax\s*year\s+(20\d{2})\b/);
    if (m) return parseInt(m[1], 10);
    m = text.match(/\b(2024|2025|2026)\b/);
    return m ? parseInt(m[1], 10) : null;
  }

  /** Get tax year for a scenario: explicit tax_year, data_model.tax_situation.tax_year, or parsed from text. */
  function getTaxYearFromScenario(s) {
    if (!s) return null;
    if (s.tax_year != null) return parseInt(s.tax_year, 10);
    var dm = s.data_model;
    if (dm && dm.tax_situation) {
      var per = dm.tax_situation.personal;
      if (per && per.tax_year != null) return parseInt(per.tax_year, 10);
      if (dm.tax_situation.tax_year != null) return parseInt(dm.tax_situation.tax_year, 10);
    }
    return parseTaxYearFromText(s.text || '');
  }

  /** Derive scenario text for a target year (e.g. 2024 → 2026). */
  function textForYear(text, targetYear) {
    if (!text || typeof text !== 'string') return text || '';
    var currentYear = parseTaxYearFromText(text) || 2024;
    return text.replace(new RegExp('\\b' + currentYear + '\\b', 'g'), String(targetYear));
  }

  function buildCardHtml(s, scenarioIndex, planEntries) {
    planEntries = planEntries || [];
    var shortId = (s.id || '').replace(/^scenario_/, '').slice(0, 8);
    var dm = s.data_model;
    var taxYear = getTaxYearFromScenario(s);
    var is2026Projection = taxYear === 2026;
    var taxSituationRows = (dm && dm.tax_situation) ? buildTaxSituationSummary(dm.tax_situation) : [];
    var summaryHtml = taxSituationRows.length
      ? taxSituationRows.map(function (l) {
          return '<div class="summary-row"><span class="summary-label">' + escapeHtml(l.label) + '</span><span class="summary-value">' + escapeHtml(l.value) + '</span></div>';
        }).join('')
      : '<p class="summary-placeholder">Run Calculate Tax to see tax situation summary.</p>';
    var llmRawHtml = '';
    if (s.loading) {
      llmRawHtml = '<div class="llm-raw-inner llm-raw-inner--loading"><span class="loading-dots">Waiting for LLM…</span></div>';
    } else if (s.error) {
      llmRawHtml = '<div class="llm-raw-inner llm-raw-inner--empty">No LLM text (request failed). Expand <strong>Calculated result</strong> for the error.</div>';
    } else if (s.result != null && String(s.result).trim() !== '') {
      llmRawHtml = '<pre class="llm-raw-pre" aria-label="Full LLM response">' + escapeHtml(String(s.result)) + '</pre>';
    } else {
      llmRawHtml = '<p class="llm-raw-placeholder">Run <strong>Calculate Tax</strong> to show the full LLM response here. Compare with structured lines below.</p>';
    }

    var calculatedInner = '';
    if (s.loading) {
      calculatedInner = '<div class="scenario-result scenario-result--loading scenario-result--compact"><span class="loading-dots">…</span></div>';
    } else if (s.error) {
      calculatedInner = '<div class="scenario-result scenario-result--error scenario-result--compact">' + escapeHtml(s.error) + '</div>';
    } else if (dm && dm.form_1040_calculated_lines) {
      var lineRows = build1040LinesSection(dm.form_1040_calculated_lines);
      if (lineRows.length) {
        calculatedInner = '<div class="summary-grid summary-grid--lines scenario-result--compact-grid">' +
          lineRows.map(function (l) {
            return '<div class="summary-row"><span class="summary-label">' + escapeHtml(l.label) + '</span><span class="summary-value">' + escapeHtml(l.value) + '</span></div>';
          }).join('') + '</div>';
      } else {
        calculatedInner = '<p class="calculated-min-placeholder">Schema filler returned no 1040 lines. Numbers above are from Key figures only.</p>';
      }
    } else if (s.result !== undefined && s.result !== '') {
      calculatedInner = '<p class="calculated-min-placeholder">Structured 1040 lines not available yet.</p>';
    } else {
      calculatedInner = '<div class="scenario-result scenario-result--empty scenario-result--compact">Click <strong>Calculate Tax</strong>.</div>';
    }
    var resultHtml =
      '<details class="collapsible-details calculated-result-details" open>' +
      '<summary class="collapsible-summary calculated-result-summary">Calculated result <span class="section-label-note">(structured 1040 from schema)</span></summary>' +
      '<div class="calculated-result-body">' + calculatedInner + '</div></details>';
    var strategiesInner;
    if (!is2026Projection) {
      strategiesInner = '<p class="strategies-placeholder">Strategies can only be applied to 2026 projections.</p>';
    } else if (planEntries.length) {
      strategiesInner = '<ul class="strategies-list">' +
        planEntries.map(function (e) {
          var title = e.title || STRATEGY_TITLES[e.strategy_id] || e.strategy_id;
          var inp = e.inputs || {};
          var inpStr = Object.keys(inp).map(function (k) { return k + ': ' + inp[k]; }).join(', ');
          return '<li class="strategies-list-item"><span class="strategies-list-title">' + escapeHtml(title) + '</span>' +
            (inpStr ? ' <span class="strategies-list-inputs">' + escapeHtml(inpStr) + '</span>' : '') + '</li>';
        }).join('') + '</ul>';
    } else {
      strategiesInner = '<p class="strategies-placeholder">No strategies added. Add strategies from Insights.</p>';
    }
    var strategiesHtml = '<details class="collapsible-details strategies-details" open>' +
      '<summary class="collapsible-summary">Strategies applied</summary>' +
      '<div class="strategies-body">' + strategiesInner + '</div></details>';
    var llmWithStrategiesInner = '';
    if (!is2026Projection) {
      llmWithStrategiesInner = '<div class="llm-raw-outer"><p class="llm-raw-placeholder">Strategies can only be applied to 2026 projections.</p></div>';
    } else if (planEntries.length) {
      if (s.loading) {
        llmWithStrategiesInner = '<div class="llm-raw-outer"><span class="loading-dots">Computing with strategies…</span></div>';
      } else if (s.resultWithStrategies != null && String(s.resultWithStrategies).trim() !== '') {
        llmWithStrategiesInner = '<div class="llm-raw-outer"><pre class="llm-raw-pre">' + escapeHtml(String(s.resultWithStrategies)) + '</pre></div>';
      } else {
        llmWithStrategiesInner = '<div class="llm-raw-outer"><p class="llm-raw-placeholder">Run <strong>Calculate Tax</strong> to compute with strategies applied.</p></div>';
      }
    } else {
      llmWithStrategiesInner = '<div class="llm-raw-outer"><p class="llm-raw-placeholder">Add strategies from Insights to see tax with strategies applied.</p></div>';
    }
    var llmWithStrategiesHtml = '<details class="collapsible-details llm-output-details" open>' +
      '<summary class="collapsible-summary llm-output-summary">LLM output (with strategies)</summary>' +
      llmWithStrategiesInner + '</details>';
    var insightsDisabled = !s.result || String(s.result).trim() === '' || !is2026Projection;
    var insightsBtnClass = insightsDisabled ? 'btn-insights btn-insights--disabled' : 'btn-insights';
    var insightsBtnAttr = insightsDisabled
      ? ' disabled aria-label="' + (is2026Projection ? 'Run Calculate Tax first' : 'Strategies only apply to 2026 projections') + '"'
      : ' aria-label="View insights"';
    var cardTitle = s.displayName || (getTaxYearFromScenario(s) === 2024 ? '2024 Actual' : 'Baseline ' + scenarioIndex);
    return '<header class="scenario-card-header">' +
      '<button type="button" class="btn ' + insightsBtnClass + '" data-id="' + escapeHtml(s.id) + '"' + insightsBtnAttr + '>Insights</button>' +
      '<div class="scenario-card-title"><span class="scenario-card-icon" aria-hidden="true"></span>' + escapeHtml(cardTitle) + (taxYear ? ' (' + taxYear + ')' : '') + '</div>' +
      '<div class="scenario-card-id">' + escapeHtml(shortId) + '</div>' +
      '</header>' +
      '<div class="scenario-card-body">' +
      '<section class="scenario-section scenario-section--description">' +
      '<details class="collapsible-details" open>' +
      '<summary class="collapsible-summary">Scenario description <span class="section-label-note">(editable)</span></summary>' +
      '<textarea class="scenario-inline-text" data-id="' + escapeHtml(s.id) + '" rows="3" placeholder="Wage income, filing status, dependents…"></textarea>' +
      '</details></section>' +
      '<section class="scenario-section scenario-section--summary">' +
      '<details class="collapsible-details" open>' +
      '<summary class="collapsible-summary">Key figures</summary>' +
      '<div class="summary-grid">' + summaryHtml + '</div>' +
      '</details></section>' +
      '<section class="scenario-section scenario-section--llm-raw">' +
      '<details class="collapsible-details llm-output-details" open>' +
      '<summary class="collapsible-summary llm-output-summary">LLM output <span class="section-label-note">(source of truth)</span></summary>' +
      '<div class="llm-raw-outer">' + llmRawHtml + '</div>' +
      '</details></section>' +
      '<section class="scenario-section scenario-section--calculated-min">' + resultHtml + '</section>' +
      '<section class="scenario-section scenario-section--strategies">' + strategiesHtml + '</section>' +
      '<section class="scenario-section scenario-section--llm-with-strategies">' + llmWithStrategiesHtml + '</section>' +
      '</div>' +
      '<footer class="scenario-card-footer">' +
      '<button type="button" class="btn btn-secondary btn-restore" data-id="' + escapeHtml(s.id) + '">Restore</button>' +
      '<button type="button" class="btn btn-primary btn-calculate" data-id="' + escapeHtml(s.id) + '">Calculate Tax</button>' +
      '</footer>';
  }

  function showInsightsPage(scenarioId) {
    currentScenarioIdForInsights = scenarioId;
    currentView = 'insights';
    comparisonEmpty.hidden = true;
    comparisonCards.hidden = true;
    if (insightsView) insightsView.hidden = false;
    renderInsights();
  }

  function showComparisonPage() {
    currentView = 'comparison';
    currentScenarioIdForInsights = null;
    if (insightsView) insightsView.hidden = true;
    if (scenarios.length === 0) return;
    renderScenarios();
  }

  function renderInsights() {
    if (!insightsView || !insightsCards || !currentScenarioIdForInsights) return;
    var s = scenarios.find(function (sc) { return sc.id === currentScenarioIdForInsights; });
    var scenarioIndex = s ? scenarios.indexOf(s) + 1 : 0;
    insightsTitle.textContent = 'Insights — Baseline ' + scenarioIndex;
    insightsPlaceholder.hidden = false;
    insightsCards.innerHTML = '';
    insightsActions.hidden = true;
    insightsLoading.hidden = true;
    insightsPrerequisite.hidden = true;

    if (!s) {
      insightsPlaceholder.textContent = 'Scenario not found.';
      return;
    }
    if (!s.result || String(s.result).trim() === '') {
      insightsPrerequisite.hidden = false;
      insightsPlaceholder.hidden = false;
      insightsPlaceholder.textContent = 'Run Calculate Tax on this scenario first, then click Insights to get recommendations.';
      return;
    }

    var stored = null;
    try {
      var raw = localStorage.getItem(STORAGE_PREFIX + currentScenarioIdForInsights);
      if (raw) stored = JSON.parse(raw);
    } catch (e) { stored = null; }

    if (stored && Array.isArray(stored.strategies) && stored.strategies.length > 0) {
      currentInsightsStrategies = stored.strategies;
      renderInsightCards(currentInsightsStrategies);
      insightsPlaceholder.hidden = true;
      insightsActions.hidden = false;
      return;
    }

    fetchInsights(s);
  }

  function renderInsightCards(strategies) {
    currentInsightsStrategies = strategies;
    if (!insightsCards) return;
    var byCategory = {};
    strategies.forEach(function (st) {
      var cat = st.category || st.strategy_type || 'Other';
      if (!byCategory[cat]) byCategory[cat] = [];
      byCategory[cat].push(st);
    });
    var categories = Object.keys(byCategory).sort();
    var html = categories.map(function (cat) {
      var items = byCategory[cat];
      var itemsHtml = items.map(function (st) {
        var title = st.title || st.strategy_id || 'Strategy';
        var summary = st.summary || '';
        var reqs = Array.isArray(st.requirements) ? st.requirements : [];
        var reqHtml = reqs.length
          ? '<ul class="insight-item-requirements">' + reqs.slice(0, 5).map(function (r) {
              return '<li>' + escapeHtml(String(r)) + '</li>';
            }).join('') + '</ul>'
          : '';
        var savingsHtml = '';
        var est = st.estimated_savings;
        if (est && (est.savings != null || (est.min != null && est.max != null))) {
          var sMin = est.min != null ? est.min : est.savings;
          var sMax = est.max != null ? est.max : est.savings;
          var savingsText = sMin === sMax ? '$' + sMin.toLocaleString('en-US') : '$' + sMin.toLocaleString('en-US') + ' – $' + sMax.toLocaleString('en-US');
          savingsHtml = '<div class="insight-item-savings"><span class="insight-item-savings-label">Est. Savings:</span> <span class="insight-item-savings-value">' + savingsText + '/yr</span></div>';
        }
        var viewCalcHtml = '';
        if (st.strategy_id === 'ita_002' || st.strategy_id === 'ita_025') {
          viewCalcHtml = ' <a href="#" class="insight-view-calculation" data-strategy-id="' + escapeHtml(st.strategy_id) + '">View calculation</a>';
        }
        return '<div class="insight-item" data-strategy-id="' + escapeHtml(st.strategy_id || '') + '">' +
          '<h4 class="insight-item-title">' + escapeHtml(title) + '</h4>' +
          '<p class="insight-item-summary">' + escapeHtml(summary) + '</p>' + reqHtml +
          savingsHtml +
          viewCalcHtml +
          '<button type="button" class="btn btn-primary btn-add-to-plan" data-strategy-id="' + escapeHtml(st.strategy_id || '') + '">Add Strategy to Plan</button></div>';
      }).join('');
      return '<details class="insight-category-section">' +
        '<summary class="insight-category-summary">' + escapeHtml(cat) + ' <span class="insight-category-count">(' + items.length + ')</span></summary>' +
        '<div class="insight-category-items">' + itemsHtml + '</div></details>';
    }).join('');
    insightsCards.innerHTML = html;
    insightsPlaceholder.hidden = strategies.length > 0;
    attachAddToPlanHandlers();
  }

  function attachAddToPlanHandlers() {
    if (!insightsCards) return;
    insightsCards.querySelectorAll('.btn-add-to-plan').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var strategyId = this.dataset.strategyId;
        addStrategyToPlan(strategyId);
      });
    });
    insightsCards.querySelectorAll('.insight-view-calculation').forEach(function (link) {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        openCalculatorDrawer(link.dataset.strategyId);
      });
    });
  }

  var currentCalcStrategyId = null;
  var currentCalcScenarioId = null;
  var currentCalcInPlan = false;
  var calcDebounceTimer = null;

  function openCalculatorDrawer(strategyId) {
    if (strategyId !== 'ita_002' && strategyId !== 'ita_025') return;
    currentCalcStrategyId = strategyId;
    currentCalcScenarioId = currentScenarioIdForInsights;
    var drawer = document.getElementById('calcDrawer');
    var overlay = document.getElementById('calcDrawerOverlay');
    var content = document.getElementById('calcDrawerContent');
    if (!drawer || !overlay || !content) return;
    currentCalcInPlan = false;
    var est = (currentInsightsStrategies.find(function (s) { return s.strategy_id === strategyId; }) || {}).estimated_savings;
    var defs = (est && est.input_defaults) || {};
    if (strategyId === 'ita_002') {
      document.getElementById('calcDrawerTitle').textContent = 'S-Corp Conversion — Calculation';
      content.innerHTML = renderScorpCalculator(defs);
    } else if (strategyId === 'ita_025') {
      document.getElementById('calcDrawerTitle').textContent = 'Bonus Depreciation — Calculation';
      content.innerHTML = renderBonusDeprCalculator(defs);
    }
    drawer.classList.add('open');
    overlay.classList.add('show');
    overlay.setAttribute('aria-hidden', 'false');
    attachCalcInputHandlers();
    runCalculator();
    loadFromPlanAndAttachSave();
  }

  function renderScorpCalculator(defs) {
    var scheduleC = defs.schedule_c_income || 200000;
    var compPct = defs.comp_percentage || 40;
    return '<div class="calc-explanation-box">' +
      '<p class="calc-explanation-text">By converting to an S-Corp, every dollar you take as distributions saves you 15 cents in self-employment taxes. Taking $10,000 as distributions instead of self-employment income saves you $1,530 in SE taxes.</p></div>' +
      '<div class="calc-section">' +
      '<div class="calc-section-header"><span class="calc-section-title">Calculation</span></div>' +
      '<ul class="calc-approach-list">' +
      '<li>IRS requires "reasonable compensation" as W-2 salary</li>' +
      '<li>Remaining income becomes S-Corp distributions</li>' +
      '<li>Distributions save ~15.3% SE tax (less some QBI impact)</li>' +
      '<li>Net savings after payroll costs (~$1,500-3,000/yr)</li></ul>' +
      '<div class="calc-input-group">' +
      '<label class="calc-input-label">Schedule C Business Income</label>' +
      '<div class="calc-input-row"><div class="calc-input-wrapper">' +
      '<span class="calc-input-prefix">$</span>' +
      '<input type="number" id="calc_schedule_c" class="calc-input" value="' + scheduleC + '" step="1000" min="0">' +
      '</div></div>' +
      '<span class="calc-input-hint">Your self-employment business income</span></div>' +
      '<div class="calc-input-group">' +
      '<label class="calc-input-label">Reasonable Compensation % <span id="calc_comp_display">' + compPct + '%</span></label>' +
      '<div class="calc-input-row">' +
      '<input type="range" id="calc_comp_percent" class="calc-slider" min="30" max="60" value="' + compPct + '">' +
      '</div>' +
      '<span class="calc-input-hint">Typical range: 30-60% (40% is common guideline)</span></div>' +
      '<div class="calc-total-box" id="calc_result">' +
      '<div class="calc-total-label">TOTAL CONTRIBUTION</div>' +
      '<div class="calc-total-amount" id="calc_result_amount">—</div>' +
      '<div class="calc-total-description" id="calc_result_description"></div></div>' +
      '<button type="button" class="btn btn-primary calc-save-to-plan" id="btn-save-to-plan">Add to Scenario</button></div>';
  }

  function renderBonusDeprCalculator(defs) {
    var scheduleC = defs.schedule_c_income || 100000;
    var equipCost = defs.equipment_cost != null ? defs.equipment_cost : Math.round(scheduleC * 0.10);
    var bonusPct = defs.bonus_percentage != null ? defs.bonus_percentage : 100;
    var taxRate = defs.tax_rate != null ? defs.tax_rate : 0.24;
    var equipMax = Math.max(Math.round(scheduleC * 0.5), 500000);
    return '<div class="calc-explanation-box">' +
      '<p class="calc-explanation-text">With the OBBB Act 2025 restoring 100% bonus depreciation, every dollar you invest in qualified equipment saves you ' + Math.round(taxRate * 100) + ' cents in taxes immediately. Heavy vehicles over 6,000 lbs have NO dollar caps!</p></div>' +
      '<div class="calc-section">' +
      '<div class="calc-section-header"><span class="calc-section-title">Calculation</span></div>' +
      '<ul class="calc-approach-list">' +
      '<li>Immediate 100% deduction for qualified property</li>' +
      '<li>Heavy vehicles (6,000+ lbs GVWR) have NO dollar caps</li>' +
      '<li>Deduction saves taxes at your marginal rate</li></ul>' +
      '<div class="calc-input-group">' +
      '<label class="calc-input-label">Equipment/Asset Cost <span class="calc-value-display" id="calc_equip_display">$' + equipCost.toLocaleString() + '</span></label>' +
      '<div class="calc-input-row">' +
      '<input type="range" id="calc_equipment_cost" class="calc-slider" min="0" max="' + equipMax + '" step="1000" value="' + equipCost + '">' +
      '</div>' +
      '<span class="calc-input-hint">Heavy vehicles (6,000+ lbs GVWR): Full deduction, no caps!</span></div>' +
      '<div class="calc-input-group">' +
      '<label class="calc-input-label">Bonus Depreciation %</label>' +
      '<select id="calc_bonus_percent" class="calc-select">' +
      '<option value="100"' + (bonusPct === 100 ? ' selected' : '') + '>100% — OBBB Act 2025 (after Jan 20, 2025)</option>' +
      '<option value="60"' + (bonusPct === 60 ? ' selected' : '') + '>60% — 2024 (Prior law)</option>' +
      '<option value="40"' + (bonusPct === 40 ? ' selected' : '') + '>40% — 2025 (Prior law)</option>' +
      '<option value="20"' + (bonusPct === 20 ? ' selected' : '') + '>20% — 2026 (Prior law)</option></select></div>' +
      '<div class="calc-input-group">' +
      '<label class="calc-input-label">Marginal Tax Rate</label>' +
      '<select id="calc_tax_rate" class="calc-select">' +
      '<option value="0.10"' + (taxRate === 0.1 ? ' selected' : '') + '>10%</option>' +
      '<option value="0.12"' + (taxRate === 0.12 ? ' selected' : '') + '>12%</option>' +
      '<option value="0.22"' + (taxRate === 0.22 ? ' selected' : '') + '>22%</option>' +
      '<option value="0.24"' + (taxRate === 0.24 ? ' selected' : '') + '>24%</option>' +
      '<option value="0.32"' + (taxRate === 0.32 ? ' selected' : '') + '>32%</option>' +
      '<option value="0.35"' + (taxRate === 0.35 ? ' selected' : '') + '>35%</option>' +
      '<option value="0.37"' + (taxRate === 0.37 ? ' selected' : '') + '>37%</option></select></div>' +
      '<div class="calc-total-box" id="calc_result">' +
      '<div class="calc-total-label">TOTAL CONTRIBUTION</div>' +
      '<div class="calc-total-amount" id="calc_result_amount">—</div>' +
      '<div class="calc-total-description" id="calc_result_description"></div></div>' +
      '<button type="button" class="btn btn-primary calc-save-to-plan" id="btn-save-to-plan">Add to Scenario</button></div>';
  }

  function loadFromPlanAndAttachSave() {
    if (!currentCalcScenarioId || !currentCalcStrategyId) return;
    fetch(API_BASE + '/api/plan/entry?scenario_id=' + encodeURIComponent(currentCalcScenarioId) + '&strategy_id=' + encodeURIComponent(currentCalcStrategyId))
      .then(function (res) {
        if (res.ok) return res.json();
        return null;
      })
      .then(function (entry) {
        if (entry && entry.inputs) {
          currentCalcInPlan = true;
          var inp = entry.inputs;
          if (currentCalcStrategyId === 'ita_002') {
            var scheduleC = document.getElementById('calc_schedule_c');
            var compPct = document.getElementById('calc_comp_percent');
            var compDisplay = document.getElementById('calc_comp_display');
            if (scheduleC && inp.schedule_c_income != null) scheduleC.value = inp.schedule_c_income;
            if (compPct) {
              var pct = inp.reasonable_comp_percentage != null ? inp.reasonable_comp_percentage : inp.comp_percentage;
              if (pct != null) {
                compPct.value = pct;
                if (compDisplay) compDisplay.textContent = pct + '%';
              }
            }
          } else if (currentCalcStrategyId === 'ita_025') {
            var equip = document.getElementById('calc_equipment_cost');
            var bonusSel = document.getElementById('calc_bonus_percent');
            var taxSel = document.getElementById('calc_tax_rate');
            var equipDisp = document.getElementById('calc_equip_display');
            if (equip && inp.equipment_cost != null) {
              equip.value = inp.equipment_cost;
              if (equipDisp) equipDisp.textContent = '$' + Number(inp.equipment_cost).toLocaleString();
            }
            if (bonusSel && inp.bonus_percentage != null) bonusSel.value = String(inp.bonus_percentage);
            if (taxSel && inp.tax_rate != null) taxSel.value = String(inp.tax_rate);
          }
          runCalculator();
        }
        var btn = document.getElementById('btn-save-to-plan');
        if (btn) btn.addEventListener('click', saveCalcToPlan);
      })
      .catch(function () {
        var btn = document.getElementById('btn-save-to-plan');
        if (btn) btn.addEventListener('click', saveCalcToPlan);
      });
  }

  function getCalcInputsForPlan() {
    if (currentCalcStrategyId === 'ita_002') {
      var scheduleC = document.getElementById('calc_schedule_c');
      var compPct = document.getElementById('calc_comp_percent');
      if (!scheduleC || !compPct) return null;
      return {
        schedule_c_income: parseFloat(scheduleC.value) || 0,
        reasonable_comp_percentage: parseFloat(compPct.value) || 40
      };
    }
    if (currentCalcStrategyId === 'ita_025') {
      var equip = document.getElementById('calc_equipment_cost');
      var bonusSel = document.getElementById('calc_bonus_percent');
      var taxSel = document.getElementById('calc_tax_rate');
      if (!equip || !bonusSel || !taxSel) return null;
      return {
        equipment_cost: parseFloat(equip.value) || 0,
        bonus_percentage: parseFloat(bonusSel.value) || 100,
        tax_rate: parseFloat(taxSel.value) || 0.24
      };
    }
    return null;
  }

  function saveCalcToPlan() {
    var btn = document.getElementById('btn-save-to-plan');
    if (!currentCalcScenarioId || !currentCalcStrategyId) {
      if (btn) { btn.textContent = 'No scenario selected'; setTimeout(function () { btn.textContent = 'Add to Scenario'; }, 2000); }
      return;
    }
    var inputs = getCalcInputsForPlan();
    if (!inputs) {
      if (btn) { btn.textContent = 'Missing inputs'; setTimeout(function () { btn.textContent = 'Add to Scenario'; }, 2000); }
      return;
    }
    if (btn) btn.disabled = true;
    fetch(API_BASE + '/api/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario_id: currentCalcScenarioId,
        strategy_id: currentCalcStrategyId,
        inputs: inputs
      })
    })
      .then(function (res) {
        if (!res.ok) throw new Error(res.statusText || 'Save failed');
        return res.json();
      })
      .then(function () {
        currentCalcInPlan = true;
        if (btn) {
          btn.textContent = 'Saved!';
          btn.classList.add('calc-save-to-plan-saved');
          setTimeout(function () {
            btn.textContent = 'Add to Scenario';
            btn.classList.remove('calc-save-to-plan-saved');
            btn.disabled = false;
          }, 2000);
        }
      })
      .catch(function (err) {
        if (btn) btn.disabled = false;
        console.error('Save to plan failed:', err);
        if (btn) btn.textContent = 'Save failed — try again';
        setTimeout(function () { if (btn) btn.textContent = 'Add to Scenario'; }, 3000);
      });
  }

  function debouncedUpdatePlan() {
    if (calcDebounceTimer) clearTimeout(calcDebounceTimer);
    calcDebounceTimer = setTimeout(function () {
      calcDebounceTimer = null;
      if (!currentCalcInPlan || !currentCalcScenarioId || !currentCalcStrategyId) return;
      var inputs = getCalcInputsForPlan();
      if (!inputs) return;
      fetch(API_BASE + '/api/plan', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_id: currentCalcScenarioId,
          strategy_id: currentCalcStrategyId,
          inputs: inputs
        })
      }).catch(function (err) { console.error('Update plan failed:', err); });
    }, 500);
  }

  function attachCalcInputHandlers() {
    function onInput() {
      if (currentCalcStrategyId === 'ita_002') {
        var compDisplay = document.getElementById('calc_comp_display');
        var compPct = document.getElementById('calc_comp_percent');
        if (compDisplay && compPct) compDisplay.textContent = compPct.value + '%';
      } else if (currentCalcStrategyId === 'ita_025') {
        var equip = document.getElementById('calc_equipment_cost');
        var equipDisp = document.getElementById('calc_equip_display');
        if (equip && equipDisp) equipDisp.textContent = '$' + parseInt(equip.value || 0, 10).toLocaleString();
      }
      runCalculator();
      debouncedUpdatePlan();
    }
    var scheduleC = document.getElementById('calc_schedule_c');
    var compPct = document.getElementById('calc_comp_percent');
    var equip = document.getElementById('calc_equipment_cost');
    var bonusSel = document.getElementById('calc_bonus_percent');
    var taxSel = document.getElementById('calc_tax_rate');
    if (scheduleC) scheduleC.addEventListener('input', onInput);
    if (compPct) compPct.addEventListener('input', onInput);
    if (equip) equip.addEventListener('input', onInput);
    if (bonusSel) bonusSel.addEventListener('change', onInput);
    if (taxSel) taxSel.addEventListener('change', onInput);
  }

  function runCalculator() {
    var amountEl = document.getElementById('calc_result_amount');
    var descEl = document.getElementById('calc_result_description');
    if (!amountEl || !currentCalcStrategyId) return;
    var strategyId = currentCalcStrategyId;
    var inputs = {};
    if (strategyId === 'ita_002') {
      var scheduleC = document.getElementById('calc_schedule_c');
      var compPct = document.getElementById('calc_comp_percent');
      if (!scheduleC || !compPct) return;
      inputs = { schedule_c_income: parseFloat(scheduleC.value) || 0, comp_percentage: parseFloat(compPct.value) || 40 };
    } else if (strategyId === 'ita_025') {
      var equip = document.getElementById('calc_equipment_cost');
      var bonusSel = document.getElementById('calc_bonus_percent');
      var taxSel = document.getElementById('calc_tax_rate');
      if (!equip || !bonusSel || !taxSel) return;
      inputs = {
        equipment_cost: parseFloat(equip.value) || 0,
        bonus_percentage: parseFloat(bonusSel.value) || 100,
        tax_rate: parseFloat(taxSel.value) || 0.24
      };
    } else return;
    fetch(API_BASE + '/api/strategy-savings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy_id: strategyId, inputs: inputs })
    })
      .then(function (res) { return res.json(); })
      .then(function (result) {
        if (result.error) {
          amountEl.textContent = 'Error';
          if (descEl) descEl.textContent = result.error;
          return;
        }
        amountEl.textContent = (result.display && result.display.main ? result.display.main : '$' + Math.round(result.savings || 0).toLocaleString()) + '/yr';
        if (descEl && result.display && result.display.details) {
          descEl.innerHTML = result.display.details.join('<br>');
        }
      })
      .catch(function (err) {
        amountEl.textContent = 'Error';
        if (descEl) descEl.textContent = err.message || 'Calculation failed';
      });
  }

  function closeCalculatorDrawer() {
    var drawer = document.getElementById('calcDrawer');
    var overlay = document.getElementById('calcDrawerOverlay');
    if (drawer) drawer.classList.remove('open');
    if (overlay) {
      overlay.classList.remove('show');
      overlay.setAttribute('aria-hidden', 'true');
    }
  }

  function addStrategyToPlan(strategyId) {
    if (strategyId === 'ita_002' || strategyId === 'ita_025') {
      openCalculatorDrawer(strategyId);
    } else {
      console.log('Add strategy to plan:', strategyId, '(calculator not yet implemented)');
    }
  }

  function fetchInsights(s) {
    insightsLoading.hidden = false;
    insightsPlaceholder.hidden = true;
    insightsActions.hidden = true;
    insightsCards.innerHTML = '';

    fetch(API_BASE + '/api/insights', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario: s.text || '',
        data_model: s.data_model || null,
        tax_result: s.data_model ? '' : (s.result || '')
      }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.error || res.statusText);
          return data;
        });
      })
      .then(function (data) {
        var strategies = data.strategies || [];
        renderInsightCards(strategies);
        insightsLoading.hidden = true;
        insightsActions.hidden = false;
      })
      .catch(function (err) {
        insightsLoading.hidden = true;
        insightsPlaceholder.hidden = false;
        insightsPlaceholder.textContent = 'Error loading insights: ' + (err.message || 'Unknown error');
        insightsActions.hidden = true;
      });
  }

  function saveInsightsToStorage() {
    if (!currentScenarioIdForInsights || currentInsightsStrategies.length === 0) return;
    try {
      localStorage.setItem(STORAGE_PREFIX + currentScenarioIdForInsights, JSON.stringify({
        strategies: currentInsightsStrategies,
        savedAt: new Date().toISOString(),
      }));
    } catch (e) { /* quota exceeded */ }
  }

  function recalculateInsights() {
    var s = scenarios.find(function (sc) { return sc.id === currentScenarioIdForInsights; });
    if (!s) return;
    fetchInsights(s);
  }

  function attachCardHandlers(card) {
    card.querySelectorAll('.btn-insights').forEach(function (btn) {
      if (btn.disabled) return;
      btn.addEventListener('click', function () { showInsightsPage(btn.dataset.id); });
    });
    var ta = card.querySelector('.scenario-inline-text');
    if (ta) {
      var s = scenarios.find(function (x) { return x.id === ta.dataset.id; });
      if (s) ta.value = s.text || '';
      ta.addEventListener('blur', function () {
        var id = this.dataset.id;
        var sc = scenarios.find(function (x) { return x.id === id; });
        if (sc && this.value.trim() !== sc.text) {
          sc.text = this.value.trim();
          invalidateScenarioCalc(sc);
          bumpScenarioVersion(sc);
          renderScenarios();
        }
      });
    }
    card.querySelectorAll('.btn-calculate').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = btn.dataset.id;
        var s = scenarios.find(function (sc) { return sc.id === id; });
        var ta = card.querySelector('.scenario-inline-text');
        if (s && ta) s.text = ta.value.trim();
        var planEntries = window._planCache && window._planCache[id];
        runCalculation(id, planEntries);
      });
    });
    card.querySelectorAll('.btn-restore').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = btn.dataset.id;
        var s = scenarios.find(function (sc) { return sc.id === id; });
        if (!s) return;
        var ta2 = card.querySelector('.scenario-inline-text');
        if (ta2) ta2.value = s.text || '';
      });
    });
  }

  function ensureComparisonSelection() {
    selectedForComparison = selectedForComparison.filter(function (id) {
      return scenarios.some(function (s) { return s.id === id; });
    });
    if (selectedForComparison.length === 0 && scenarios.length > 0) {
      scenarios.slice(0, MAX_COMPARE).forEach(function (s) {
        selectedForComparison.push(s.id);
      });
    }
    if (selectedForComparison.length > MAX_COMPARE) {
      selectedForComparison = selectedForComparison.slice(0, MAX_COMPARE);
    }
  }

  function toggleScenarioInComparison(id, forceChecked) {
    var idx = selectedForComparison.indexOf(id);
    if (forceChecked === true) {
      if (idx >= 0) return;
      if (selectedForComparison.length >= MAX_COMPARE) {
        maxSelectionMessage.hidden = false;
        return false;
      }
      selectedForComparison.push(id);
      return true;
    }
    if (forceChecked === false) {
      if (idx >= 0) selectedForComparison.splice(idx, 1);
      maxSelectionMessage.hidden = true;
      return true;
    }
    if (idx >= 0) {
      selectedForComparison.splice(idx, 1);
      maxSelectionMessage.hidden = true;
    } else {
      if (selectedForComparison.length >= MAX_COMPARE) {
        maxSelectionMessage.hidden = false;
        return false;
      }
      selectedForComparison.push(id);
    }
    return true;
  }

  function deleteScenario(id) {
    var idx = scenarios.findIndex(function (sc) { return sc.id === id; });
    if (idx <= 0) return;
    scenarios.splice(idx, 1);
    selectedForComparison = selectedForComparison.filter(function (sid) { return sid !== id; });
    ensureComparisonSelection();
    renderScenarios();
  }

  function renderScenarios() {
    if (scenarios.length === 0) {
      emptyState.hidden = false;
      comparisonEmpty.hidden = true;
      comparisonCards.hidden = true;
      scenariosSidebar.hidden = true;
      selectedForComparison = [];
      return;
    }
    ensureComparisonSelection();
    emptyState.hidden = true;
    scenariosSidebar.hidden = false;
    if (selectedForComparison.length < MAX_COMPARE) {
      maxSelectionMessage.hidden = true;
    }

    var id2024Actual = scenarios.find(function (s) { return getTaxYearFromScenario(s) === 2024; });
    var id2024ActualId = id2024Actual ? id2024Actual.id : null;
    var sidebar2024Toggle = document.getElementById('sidebar-2024-toggle');
    var toggle2024Cta = document.getElementById('toggle-2024-cta');
    if (sidebar2024Toggle && toggle2024Cta) {
      if (id2024ActualId) {
        sidebar2024Toggle.hidden = false;
        toggle2024Cta.textContent = hide2024Actual ? 'Show' : 'Hide';
        toggle2024Cta.className = 'sidebar-2024-cta ' + (hide2024Actual ? 'toggle-show' : 'toggle-hide');
        toggle2024Cta.setAttribute('aria-label', hide2024Actual ? 'Show 2024 Actual in comparison' : 'Hide 2024 Actual from comparison');
      } else {
        sidebar2024Toggle.hidden = true;
      }
    }

    var listHtml = '';
    scenarios.forEach(function (s, i) {
      var scenarioIndex = i + 1;
      var isBaseline = i === 0;
      var canDelete = !isBaseline;
      var checked = selectedForComparison.indexOf(s.id) >= 0 ? ' checked' : '';
      var deleteClass = canDelete ? '' : ' scenario-list-item-delete--hidden';
      var sidebarLabel = s.displayName || (getTaxYearFromScenario(s) === 2024 ? '2024 Actual' : 'Baseline ' + scenarioIndex);
      listHtml += '<li class="scenario-list-item" data-id="' + escapeHtml(s.id) + '">' +
        '<input type="checkbox" class="scenario-list-item-checkbox" data-id="' + escapeHtml(s.id) + '" id="scenario-cb-' + escapeHtml(s.id) + '"' + checked + ' aria-label="Compare ' + escapeHtml(sidebarLabel) + '">' +
        '<label class="scenario-list-item-label" for="scenario-cb-' + escapeHtml(s.id) + '">' + escapeHtml(sidebarLabel) + '</label>' +
        '<button type="button" class="scenario-list-item-delete' + deleteClass + '" data-id="' + escapeHtml(s.id) + '" aria-label="Delete scenario" title="Delete">×</button>' +
        '</li>';
    });
    scenarioListEl.innerHTML = listHtml;

    scenarioListEl.querySelectorAll('.scenario-list-item-checkbox').forEach(function (cb) {
      cb.addEventListener('change', function () {
        var id = this.dataset.id;
        var added = toggleScenarioInComparison(id, this.checked);
        if (!added) this.checked = false;
        renderScenarios();
      });
    });
    scenarioListEl.querySelectorAll('.scenario-list-item-delete').forEach(function (btn) {
      if (btn.classList.contains('scenario-list-item-delete--hidden')) return;
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        deleteScenario(btn.dataset.id);
      });
    });

    if (selectedForComparison.length === 0) {
      comparisonCards.hidden = true;
      comparisonEmpty.hidden = (currentView === 'insights');
      return;
    }
    comparisonEmpty.hidden = true;
    comparisonCards.hidden = (currentView === 'insights');
    if (currentView === 'insights' && insightsView) insightsView.hidden = false;
    comparisonCards.innerHTML = '';

    var idsToShow = selectedForComparison;
    if (hide2024Actual && id2024ActualId) {
      idsToShow = selectedForComparison.filter(function (id) { return id !== id2024ActualId; });
    }
    if (idsToShow.length === 0) {
      comparisonEmpty.hidden = false;
      comparisonCards.hidden = true;
      return;
    }

    var planPromises = selectedForComparison.map(function (id) {
      return fetch(API_BASE + '/api/plan?scenario_id=' + encodeURIComponent(id))
        .then(function (r) { return r.json().catch(function () { return { strategies: [] }; }); })
        .then(function (data) { return { id: id, strategies: data.strategies || [] }; });
    });
    Promise.all(planPromises).then(function (results) {
      var planCache = {};
      results.forEach(function (r) { planCache[r.id] = r.strategies; });
      window._planCache = planCache;
      idsToShow.forEach(function (id) {
        var s = scenarios.find(function (sc) { return sc.id === id; });
        if (!s) return;
        var scenarioIndex = scenarios.indexOf(s) + 1;
        var planEntries = planCache[id] || [];
        var wrap = document.createElement('div');
        wrap.className = 'scenario-card';
        wrap.dataset.id = s.id;
        wrap.innerHTML = buildCardHtml(s, scenarioIndex, planEntries);
        comparisonCards.appendChild(wrap);
        attachCardHandlers(wrap);
      });
    });
  }

  function runCalculation(id, planEntries) {
    const s = scenarios.find(function (sc) { return sc.id === id; });
    if (!s || !s.text) return;

    function doCalculate(entries) {
      entries = entries || [];
      if (!window._planCache) window._planCache = {};
      window._planCache[id] = entries;

      s.loading = true;
      s.error = undefined;
      s.result = undefined;
      s.data_model = undefined;
      s.resultWithStrategies = undefined;
      renderScenarios();

      var body = { scenario: s.text };
      if (entries.length) {
        body.strategies = entries.map(function (e) {
          return { strategy_id: e.strategy_id, inputs: e.inputs || {}, title: e.title };
        });
      }

      fetch(API_BASE + '/api/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.error || res.statusText);
          return data;
        });
      })
      .then(function (data) {
        s.loading = false;
        s.result = data.result || '';
        s.data_model = data.data_model || null;
        s.resultWithStrategies = data.result_with_strategies || null;
        s.error = undefined;
        if (s.data_model && s.data_model.tax_situation) {
          var ts = s.data_model.tax_situation;
          var ty = (ts.personal && ts.personal.tax_year != null) ? ts.personal.tax_year : ts.tax_year;
          if (ty != null) s.tax_year = parseInt(ty, 10);
        }
        renderScenarios();
      })
      .catch(function (err) {
        s.loading = false;
        s.error = err.message || 'Calculation failed';
        s.result = undefined;
        s.data_model = undefined;
        s.resultWithStrategies = undefined;
        renderScenarios();
      });
    }

    fetch(API_BASE + '/api/plan?scenario_id=' + encodeURIComponent(id))
      .then(function (res) {
        return res.json().catch(function () { return { strategies: [] }; });
      })
      .then(function (data) {
        doCalculate((data && data.strategies) || []);
      })
      .catch(function () {
        var fallback = planEntries || (window._planCache && window._planCache[id]) || [];
        doCalculate(fallback);
      });
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /** UC-5: monotonic version for scenario text; increments when text changes invalidate prior calcs. */
  function bumpScenarioVersion(s) {
    if (!s) return;
    s.scenario_version = (typeof s.scenario_version === 'number' ? s.scenario_version : 0) + 1;
  }

  function invalidateScenarioCalc(s) {
    if (!s) return;
    s.result = undefined;
    s.data_model = undefined;
    s.resultWithStrategies = undefined;
    s.error = undefined;
  }

  var assistantDrawer = document.getElementById('assistantDrawer');
  var assistantDrawerOverlay = document.getElementById('assistantDrawerOverlay');
  var assistantDrawerClose = document.getElementById('assistantDrawerClose');
  var btnOpenAssistant = document.getElementById('btn-open-assistant');
  var assistantScenarioSelect = document.getElementById('assistant-scenario-select');
  var assistantScenarioText = document.getElementById('assistant-scenario-text');
  var assistantScenarioVersionLine = document.getElementById('assistant-scenario-version-line');
  var assistantApplyScenario = document.getElementById('assistant-apply-scenario');
  var assistantMemoryList = document.getElementById('assistant-memory-list');
  var assistantMemoryInput = document.getElementById('assistant-memory-input');
  var assistantMemoryAdd = document.getElementById('assistant-memory-add');
  var assistantMemoryStatus = document.getElementById('assistant-memory-status');

  function openAssistantDrawer() {
    if (!assistantDrawer || !assistantDrawerOverlay) return;
    assistantDrawer.removeAttribute('hidden');
    assistantDrawer.classList.add('open');
    assistantDrawerOverlay.classList.add('show');
    assistantDrawerOverlay.setAttribute('aria-hidden', 'false');
    if (btnOpenAssistant) btnOpenAssistant.setAttribute('aria-expanded', 'true');
    populateAssistantScenarioSelect();
    refreshAssistantPanel();
  }

  function closeAssistantDrawer() {
    if (!assistantDrawer || !assistantDrawerOverlay) return;
    assistantDrawer.classList.remove('open');
    assistantDrawerOverlay.classList.remove('show');
    assistantDrawerOverlay.setAttribute('aria-hidden', 'true');
    assistantDrawer.setAttribute('hidden', '');
    if (btnOpenAssistant) btnOpenAssistant.setAttribute('aria-expanded', 'false');
  }

  function getAssistantScenarioId() {
    if (assistantScenarioSelect && assistantScenarioSelect.value) return assistantScenarioSelect.value;
    if (selectedForComparison.length > 0) return selectedForComparison[0];
    if (scenarios.length > 0) return scenarios[0].id;
    return null;
  }

  function populateAssistantScenarioSelect() {
    if (!assistantScenarioSelect) return;
    var current = getAssistantScenarioId();
    assistantScenarioSelect.innerHTML = '';
    scenarios.forEach(function (s, i) {
      var opt = document.createElement('option');
      opt.value = s.id;
      var label = s.displayName || (getTaxYearFromScenario(s) === 2024 ? '2024 Actual' : 'Baseline ' + (i + 1));
      opt.textContent = label + ' — ' + (s.id || '').replace(/^scenario_/, '').slice(0, 8);
      assistantScenarioSelect.appendChild(opt);
    });
    if (scenarios.length === 0) {
      var o = document.createElement('option');
      o.value = '';
      o.textContent = '— No scenarios —';
      assistantScenarioSelect.appendChild(o);
      return;
    }
    if (current && scenarios.some(function (x) { return x.id === current; })) {
      assistantScenarioSelect.value = current;
    } else {
      assistantScenarioSelect.value = scenarios[0].id;
    }
  }

  function refreshAssistantScenarioSection() {
    var id = getAssistantScenarioId();
    var s = scenarios.find(function (sc) { return sc.id === id; });
    if (assistantScenarioText) assistantScenarioText.value = s ? (s.text || '') : '';
    if (assistantScenarioVersionLine) {
      if (s && typeof s.scenario_version === 'number') {
        assistantScenarioVersionLine.textContent = 'Scenario version: ' + s.scenario_version + ' (increments when scenario text changes and prior results are cleared).';
        assistantScenarioVersionLine.hidden = false;
      } else {
        assistantScenarioVersionLine.textContent = '';
        assistantScenarioVersionLine.hidden = true;
      }
    }
  }

  function refreshAssistantMemoryList() {
    var id = getAssistantScenarioId();
    if (!assistantMemoryList || !id) return;
    assistantMemoryList.innerHTML = '';
    fetch(API_BASE + '/api/memory?scenario_id=' + encodeURIComponent(id))
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.error || res.statusText);
          return data;
        });
      })
      .then(function (data) {
        var items = data.items || [];
        items.forEach(function (item) {
          var li = document.createElement('li');
          li.className = 'assistant-memory-item';
          li.dataset.memoryId = item.id;
          var span = document.createElement('span');
          span.className = 'assistant-memory-text';
          span.textContent = item.text || '';
          var del = document.createElement('button');
          del.type = 'button';
          del.className = 'assistant-memory-remove';
          del.textContent = 'Remove';
          del.dataset.memoryId = item.id;
          del.addEventListener('click', function () {
            removeAssistantMemory(item.id);
          });
          li.appendChild(span);
          li.appendChild(del);
          assistantMemoryList.appendChild(li);
        });
      })
      .catch(function () {
        assistantMemoryList.innerHTML = '';
        var li = document.createElement('li');
        li.className = 'assistant-memory-item';
        li.textContent = 'Could not load memory (is the server running?)';
        assistantMemoryList.appendChild(li);
      });
  }

  function setAssistantStatus(msg, isError) {
    if (!assistantMemoryStatus) return;
    assistantMemoryStatus.textContent = msg || '';
    assistantMemoryStatus.hidden = !msg;
    assistantMemoryStatus.classList.toggle('assistant-status--error', !!isError);
  }

  function refreshAssistantPanel() {
    refreshAssistantScenarioSection();
    refreshAssistantMemoryList();
    loadChatMessages();
    setAssistantStatus('', false);
  }

  var assistantTabChat = document.getElementById('assistant-tab-chat');
  var assistantTabContext = document.getElementById('assistant-tab-context');
  var assistantPanelChat = document.getElementById('assistant-panel-chat');
  var assistantPanelContext = document.getElementById('assistant-panel-context');
  var chatMessagesEl = document.getElementById('chat-messages');
  var chatEmptyEl = document.getElementById('chat-empty');
  var chatLoadingEl = document.getElementById('chat-loading');
  var chatInputEl = document.getElementById('chat-input');
  var chatSendBtn = document.getElementById('chat-send');
  var chatClearBtn = document.getElementById('chat-clear');

  function setAssistantTab(which) {
    var isChat = which === 'chat';
    if (assistantPanelChat) {
      assistantPanelChat.classList.toggle('assistant-panel--active', isChat);
    }
    if (assistantPanelContext) {
      assistantPanelContext.classList.toggle('assistant-panel--active', !isChat);
    }
    if (assistantTabChat) {
      assistantTabChat.classList.toggle('assistant-tab--active', isChat);
      assistantTabChat.setAttribute('aria-selected', isChat ? 'true' : 'false');
    }
    if (assistantTabContext) {
      assistantTabContext.classList.toggle('assistant-tab--active', !isChat);
      assistantTabContext.setAttribute('aria-selected', (!isChat).toString());
    }
  }

  function renderChatMessages(messages) {
    if (!chatMessagesEl || !chatEmptyEl) return;
    chatMessagesEl.innerHTML = '';
    var list = messages || [];
    chatEmptyEl.hidden = list.length > 0;
    list.forEach(function (m) {
      var div = document.createElement('div');
      div.className = 'chat-message chat-message--' + (m.role === 'user' ? 'user' : 'assistant');
      div.textContent = m.content || '';
      chatMessagesEl.appendChild(div);
    });
    chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
  }

  function loadChatMessages() {
    var id = getAssistantScenarioId();
    if (!id || !chatMessagesEl) {
      renderChatMessages([]);
      return;
    }
    fetch(API_BASE + '/api/chat?scenario_id=' + encodeURIComponent(id))
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.error || res.statusText);
          return data;
        });
      })
      .then(function (data) {
        renderChatMessages(data.messages || []);
      })
      .catch(function () {
        renderChatMessages([]);
      });
  }

  function sendChatMessage() {
    var id = getAssistantScenarioId();
    var s = scenarios.find(function (sc) { return sc.id === id; });
    if (!id || !chatInputEl || !s) return;
    var text = chatInputEl.value.trim();
    if (!text) return;
    if (chatLoadingEl) chatLoadingEl.hidden = false;
    if (chatSendBtn) chatSendBtn.disabled = true;
    fetch(API_BASE + '/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario_id: id,
        message: text,
        scenario_text: s.text || '',
      }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.error || res.statusText);
          return data;
        });
      })
      .then(function () {
        chatInputEl.value = '';
        loadChatMessages();
      })
      .catch(function (err) {
        alert(err.message || 'Chat request failed');
      })
      .finally(function () {
        if (chatLoadingEl) chatLoadingEl.hidden = true;
        if (chatSendBtn) chatSendBtn.disabled = false;
      });
  }

  function clearChatThread() {
    var id = getAssistantScenarioId();
    if (!id) return;
    if (!window.confirm('Clear all messages in this chat for this scenario?')) return;
    fetch(API_BASE + '/api/chat?scenario_id=' + encodeURIComponent(id), { method: 'DELETE' })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.error || res.statusText);
          return data;
        });
      })
      .then(function () {
        loadChatMessages();
      })
      .catch(function (err) {
        alert(err.message || 'Could not clear chat');
      });
  }

  function applyAssistantScenario() {
    var id = getAssistantScenarioId();
    var s = scenarios.find(function (sc) { return sc.id === id; });
    if (!s || !assistantScenarioText) return;
    var t = assistantScenarioText.value.trim();
    if (!t) {
      setAssistantStatus('Scenario text cannot be empty.', true);
      return;
    }
    s.text = t;
    s.tax_year = parseTaxYearFromText(t) || s.tax_year;
    invalidateScenarioCalc(s);
    bumpScenarioVersion(s);
    setAssistantStatus('Scenario updated. Run Calculate Tax on the card to refresh results.', false);
    refreshAssistantScenarioSection();
    renderScenarios();
  }

  function addAssistantMemory() {
    var id = getAssistantScenarioId();
    if (!id || !assistantMemoryInput) return;
    var text = assistantMemoryInput.value.trim();
    if (!text) {
      setAssistantStatus('Enter text to remember.', true);
      return;
    }
    setAssistantStatus('Saving…', false);
    fetch(API_BASE + '/api/memory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: id, text: text }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.error || res.statusText);
          return data;
        });
      })
      .then(function () {
        assistantMemoryInput.value = '';
        setAssistantStatus('Saved.', false);
        refreshAssistantMemoryList();
      })
      .catch(function (err) {
        setAssistantStatus(err.message || 'Failed to save memory', true);
      });
  }

  function removeAssistantMemory(memoryId) {
    var id = getAssistantScenarioId();
    if (!id || !memoryId) return;
    fetch(API_BASE + '/api/memory?scenario_id=' + encodeURIComponent(id) + '&memory_id=' + encodeURIComponent(memoryId), {
      method: 'DELETE',
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.error || res.statusText);
          return data;
        });
      })
      .then(function () {
        setAssistantStatus('Removed.', false);
        refreshAssistantMemoryList();
      })
      .catch(function (err) {
        setAssistantStatus(err.message || 'Failed to remove', true);
      });
  }

  if (btnOpenAssistant) {
    btnOpenAssistant.addEventListener('click', function () {
      openAssistantDrawer();
    });
  }
  if (assistantDrawerClose) {
    assistantDrawerClose.addEventListener('click', closeAssistantDrawer);
  }
  if (assistantDrawerOverlay) {
    assistantDrawerOverlay.addEventListener('click', closeAssistantDrawer);
  }
  if (assistantScenarioSelect) {
    assistantScenarioSelect.addEventListener('change', refreshAssistantPanel);
  }
  if (assistantApplyScenario) {
    assistantApplyScenario.addEventListener('click', applyAssistantScenario);
  }
  if (assistantMemoryAdd) {
    assistantMemoryAdd.addEventListener('click', addAssistantMemory);
  }
  if (assistantMemoryInput) {
    assistantMemoryInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        addAssistantMemory();
      }
    });
  }

  if (assistantTabChat) {
    assistantTabChat.addEventListener('click', function () {
      setAssistantTab('chat');
    });
  }
  if (assistantTabContext) {
    assistantTabContext.addEventListener('click', function () {
      setAssistantTab('context');
    });
  }
  if (chatSendBtn) {
    chatSendBtn.addEventListener('click', sendChatMessage);
  }
  if (chatClearBtn) {
    chatClearBtn.addEventListener('click', clearChatThread);
  }
  if (chatInputEl) {
    chatInputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    });
  }

  function saveScenario() {
    const text = scenarioText.value.trim();
    if (!text) return;
    if (editingScenarioId) {
      var s = scenarios.find(function (sc) { return sc.id === editingScenarioId; });
      if (s) {
        s.text = text;
        s.tax_year = parseTaxYearFromText(text) || s.tax_year;
        s.result = undefined;
        s.data_model = undefined;
        s.resultWithStrategies = undefined;
        s.error = undefined;
        bumpScenarioVersion(s);
      }
    } else {
      var taxYear = parseTaxYearFromText(text);
      const id = 'scenario_' + Date.now();
      var displayName = taxYear === 2024 ? '2024 Actual' : null;
      scenarios.push({ id: id, text: text, createdAt: new Date().toISOString(), tax_year: taxYear, displayName: displayName, scenario_version: 0 });
      if (selectedForComparison.length < MAX_COMPARE) {
        selectedForComparison.push(id);
      }
      // Ground rule: when a 2024 return is created, auto-create Base-2026 projection
      if (taxYear === 2024) {
        var base2026Id = 'scenario_' + (Date.now() + 1);
        var base2026Text = textForYear(text, 2026);
        scenarios.push({
          id: base2026Id,
          text: base2026Text,
          createdAt: new Date().toISOString(),
          tax_year: 2026,
          displayName: 'Base-2026',
          projectionOf: id,
          scenario_version: 0
        });
        if (selectedForComparison.length < MAX_COMPARE) {
          selectedForComparison.push(base2026Id);
        }
      }
    }
    closeModal();
    renderScenarios();
  }

  btnAddScenario.addEventListener('click', openModalForNew);
  btnAddScenarioSidebar.addEventListener('click', openModalForNew);

  modalBackdrop.addEventListener('click', closeModal);
  modalClose.addEventListener('click', closeModal);
  modalCancel.addEventListener('click', closeModal);
  modalSave.addEventListener('click', saveScenario);

  modal.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeModal();
  });

  // 1040 PDF upload: send to server, run extraction + description pipeline, fill scenario text.
  var uploadPdfStatus = document.getElementById('upload-pdf-status');
  upload1040.addEventListener('change', function () {
    var file = this.files && this.files[0];
    if (!file || file.type !== 'application/pdf') {
      if (uploadPdfStatus) { uploadPdfStatus.hidden = true; }
      return;
    }
    uploadPdfStatus.hidden = false;
    uploadPdfStatus.textContent = 'Extracting from PDF… (this may take over a minute)';
    uploadPdfStatus.classList.remove('upload-pdf-status--error');

    var formData = new FormData();
    formData.append('file', file);

    fetch(API_BASE + '/api/pdf-to-description', {
      method: 'POST',
      body: formData
    })
      .then(function (res) {
        if (!res.ok) return res.json().then(function (body) { throw new Error(body.error || res.statusText); });
        return res.json();
      })
      .then(function (data) {
        if (data.description != null) {
          scenarioText.value = data.description;
          uploadPdfStatus.textContent = 'Scenario filled from PDF. You can edit the text and save.';
        } else {
          uploadPdfStatus.textContent = 'No description returned.';
          uploadPdfStatus.classList.add('upload-pdf-status--error');
        }
      })
      .catch(function (err) {
        uploadPdfStatus.textContent = 'Error: ' + (err.message || 'Upload failed');
        uploadPdfStatus.classList.add('upload-pdf-status--error');
      })
      .finally(function () {
        upload1040.value = '';
      });
  });

  if (backToComparison) {
    backToComparison.addEventListener('click', function (e) {
      e.preventDefault();
      showComparisonPage();
    });
  }

  var toggle2024CtaEl = document.getElementById('toggle-2024-cta');
  if (toggle2024CtaEl) {
    toggle2024CtaEl.addEventListener('click', function () {
      hide2024Actual = !hide2024Actual;
      renderScenarios();
    });
    toggle2024CtaEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        hide2024Actual = !hide2024Actual;
        renderScenarios();
      }
    });
  }

  if (btnSaveInsights) {
    btnSaveInsights.addEventListener('click', saveInsightsToStorage);
  }
  if (btnRecalculateInsights) {
    btnRecalculateInsights.addEventListener('click', recalculateInsights);
  }

  var calcDrawerOverlay = document.getElementById('calcDrawerOverlay');
  var calcDrawerClose = document.getElementById('calcDrawerClose');
  if (calcDrawerOverlay) calcDrawerOverlay.addEventListener('click', closeCalculatorDrawer);
  if (calcDrawerClose) calcDrawerClose.addEventListener('click', closeCalculatorDrawer);

  // Copy from Baseline: separate handler; copies selected baseline text into the scenario textarea.
  copyFromBaselineSelect.addEventListener('change', function () {
    var id = this.value;
    if (!id) return;
    var s = scenarios.find(function (sc) { return sc.id === id; });
    if (s && s.text) {
      scenarioText.value = s.text;
    }
    this.value = '';
  });

  function clearAllInsightsStorage() {
    var toRemove = [];
    var i;
    for (i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      if (k && k.indexOf(STORAGE_PREFIX) === 0) toRemove.push(k);
    }
    toRemove.forEach(function (k) { localStorage.removeItem(k); });
  }

  function serializeScenario(s) {
    return {
      id: s.id,
      text: s.text || '',
      createdAt: s.createdAt,
      tax_year: s.tax_year,
      displayName: s.displayName != null ? s.displayName : null,
      projectionOf: s.projectionOf != null ? s.projectionOf : null,
      scenario_version: typeof s.scenario_version === 'number' ? s.scenario_version : 0,
      result: s.result !== undefined && s.result !== null ? s.result : null,
      data_model: s.data_model != null ? s.data_model : null,
      resultWithStrategies: s.resultWithStrategies !== undefined && s.resultWithStrategies !== null ? s.resultWithStrategies : null,
      error: s.error !== undefined ? s.error : undefined
    };
  }

  function collectInsightsFromStorage() {
    var out = {};
    scenarios.forEach(function (s) {
      var raw = localStorage.getItem(STORAGE_PREFIX + s.id);
      if (raw) {
        try { out[s.id] = JSON.parse(raw); } catch (e) { /* ignore */ }
      }
    });
    return out;
  }

  function fetchServerSnapshotForScenario(id) {
    return Promise.all([
      fetch(API_BASE + '/api/chat?scenario_id=' + encodeURIComponent(id)).then(function (r) { return r.json(); }),
      fetch(API_BASE + '/api/memory?scenario_id=' + encodeURIComponent(id)).then(function (r) { return r.json(); }),
      fetch(API_BASE + '/api/plan?scenario_id=' + encodeURIComponent(id)).then(function (r) { return r.json(); })
    ]).then(function (parts) {
      return {
        chat: (parts[0] && parts[0].messages) ? parts[0].messages : [],
        memory: (parts[1] && parts[1].items) ? parts[1].items : [],
        plan: (parts[2] && parts[2].strategies) ? parts[2].strategies : []
      };
    });
  }

  function saveWorkspaceToServer() {
    var label = window.prompt('Label for this snapshot (optional):', '');
    if (label === null) return;
    if (btnWorkspaceSave) btnWorkspaceSave.disabled = true;
    var serverPromises = scenarios.map(function (s) {
      return fetchServerSnapshotForScenario(s.id).then(function (block) {
        return { id: s.id, block: block };
      });
    });
    Promise.all(serverPromises).then(function (pairs) {
      var serverByScenario = {};
      pairs.forEach(function (p) {
        serverByScenario[p.id] = p.block;
      });
      var state = {
        version: WORKSPACE_STATE_VERSION,
        scenarios: scenarios.map(serializeScenario),
        selectedForComparison: selectedForComparison.slice(),
        hide2024Actual: hide2024Actual,
        insightsByScenario: collectInsightsFromStorage(),
        ui: {
          currentView: currentView,
          currentScenarioIdForInsights: currentScenarioIdForInsights
        },
        serverByScenario: serverByScenario
      };
      return fetch(API_BASE + '/api/workspace/snapshot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label: label || '', state: state })
      });
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw new Error(data.error || res.statusText);
        return data;
      });
    }).then(function (data) {
      window.alert('Workspace saved.' + (data.id ? '\nSnapshot id: ' + data.id : ''));
    }).catch(function (err) {
      window.alert('Save failed: ' + (err.message || 'Unknown error'));
    }).finally(function () {
      if (btnWorkspaceSave) btnWorkspaceSave.disabled = false;
    });
  }

  function closeWorkspaceLoadModal() {
    if (workspaceLoadModal) workspaceLoadModal.hidden = true;
    if (workspaceLoadStatus) {
      workspaceLoadStatus.textContent = '';
      workspaceLoadStatus.hidden = true;
    }
  }

  function openWorkspaceLoadModal() {
    if (!workspaceLoadModal || !workspaceSnapshotSelect) return;
    if (workspaceLoadStatus) {
      workspaceLoadStatus.textContent = '';
      workspaceLoadStatus.hidden = true;
    }
    fetch(API_BASE + '/api/workspace/snapshots')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var list = data.snapshots || [];
        workspaceSnapshotSelect.innerHTML = '';
        if (list.length === 0) {
          var opt = document.createElement('option');
          opt.value = '';
          opt.textContent = 'No snapshots yet';
          workspaceSnapshotSelect.appendChild(opt);
          workspaceSnapshotSelect.disabled = true;
        } else {
          workspaceSnapshotSelect.disabled = false;
          list.forEach(function (snap) {
            var o = document.createElement('option');
            o.value = snap.id;
            var lab = snap.label || '(no label)';
            var when = (snap.created_at || '').replace('T', ' ').slice(0, 19);
            o.textContent = lab + ' — ' + when;
            workspaceSnapshotSelect.appendChild(o);
          });
        }
        workspaceLoadModal.hidden = false;
      })
      .catch(function (err) {
        window.alert('Could not list snapshots: ' + (err.message || 'Unknown error'));
      });
  }

  function applyWorkspaceStateFromSnapshot(state) {
    if (!state || state.version !== WORKSPACE_STATE_VERSION) {
      return Promise.reject(new Error('Unsupported or missing snapshot version (expected ' + WORKSPACE_STATE_VERSION + ').'));
    }
    return fetch(API_BASE + '/api/workspace/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state: state })
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw new Error(data.error || res.statusText);
      });
    }).then(function () {
      clearAllInsightsStorage();
      var insights = state.insightsByScenario || {};
      Object.keys(insights).forEach(function (sid) {
        try {
          localStorage.setItem(STORAGE_PREFIX + sid, JSON.stringify(insights[sid]));
        } catch (e) { /* quota */ }
      });
      scenarios = (state.scenarios || []).map(function (raw) {
        return {
          id: raw.id,
          text: raw.text || '',
          createdAt: raw.createdAt,
          tax_year: raw.tax_year,
          displayName: raw.displayName,
          projectionOf: raw.projectionOf,
          scenario_version: raw.scenario_version,
          result: raw.result,
          data_model: raw.data_model,
          resultWithStrategies: raw.resultWithStrategies,
          error: raw.error
        };
      });
      selectedForComparison = (state.selectedForComparison || []).slice();
      hide2024Actual = !!state.hide2024Actual;
      var ui = state.ui || {};
      var wantInsights = ui.currentView === 'insights' && ui.currentScenarioIdForInsights &&
        scenarios.some(function (sc) { return sc.id === ui.currentScenarioIdForInsights; });
      if (wantInsights) {
        currentView = 'insights';
        currentScenarioIdForInsights = ui.currentScenarioIdForInsights;
      } else {
        currentView = 'comparison';
        currentScenarioIdForInsights = null;
      }
      closeWorkspaceLoadModal();
      renderScenarios();
      if (wantInsights) {
        showInsightsPage(ui.currentScenarioIdForInsights);
      } else {
        if (insightsView) insightsView.hidden = true;
      }
      refreshAssistantPanel();
    });
  }

  function confirmLoadWorkspace() {
    var id = workspaceSnapshotSelect && workspaceSnapshotSelect.value;
    if (!id) return;
    if (!window.confirm('Replace the current workspace with this snapshot? Unsaved changes will be lost.')) return;
    if (workspaceLoadConfirm) workspaceLoadConfirm.disabled = true;
    if (workspaceLoadStatus) {
      workspaceLoadStatus.textContent = 'Loading…';
      workspaceLoadStatus.hidden = false;
    }
    fetch(API_BASE + '/api/workspace/snapshot/' + encodeURIComponent(id))
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.error || res.statusText);
          return data;
        });
      })
      .then(function (data) {
        return applyWorkspaceStateFromSnapshot(data.state);
      })
      .then(function () {
        if (workspaceLoadStatus) workspaceLoadStatus.hidden = true;
      })
      .catch(function (err) {
        if (workspaceLoadStatus) {
          workspaceLoadStatus.textContent = err.message || 'Load failed';
          workspaceLoadStatus.hidden = false;
        } else {
          window.alert('Load failed: ' + (err.message || 'Unknown error'));
        }
      })
      .finally(function () {
        if (workspaceLoadConfirm) workspaceLoadConfirm.disabled = false;
      });
  }

  if (btnWorkspaceSave) {
    btnWorkspaceSave.addEventListener('click', saveWorkspaceToServer);
  }
  if (btnWorkspaceLoad) {
    btnWorkspaceLoad.addEventListener('click', openWorkspaceLoadModal);
  }
  if (workspaceLoadClose) workspaceLoadClose.addEventListener('click', closeWorkspaceLoadModal);
  if (workspaceLoadCancel) workspaceLoadCancel.addEventListener('click', closeWorkspaceLoadModal);
  if (workspaceLoadBackdrop) workspaceLoadBackdrop.addEventListener('click', closeWorkspaceLoadModal);
  if (workspaceLoadConfirm) workspaceLoadConfirm.addEventListener('click', confirmLoadWorkspace);

  renderScenarios();
})();
