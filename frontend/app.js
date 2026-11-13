const API_BASE = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
  ? '' 
  : '';

let cachedRates = { USD: 1.0, EUR: 1.085, GBP: 1.282, JPY: 0.00667, CAD: 0.742, AUD: 0.658, CHF: 1.124, INR: 0.01205, SGD: 0.751 };

// DOM Elements
const kpiTotalSpend = document.getElementById('kpiTotalSpend');
const kpiRecordCount = document.getElementById('kpiRecordCount');
const kpiPendingCount = document.getElementById('kpiPendingCount');
const kpiOverrunCount = document.getElementById('kpiOverrunCount');
const expenseTableBody = document.getElementById('expenseTableBody');
const budgetGrid = document.getElementById('budgetGrid');
const categorySpendBars = document.getElementById('categorySpendBars');
const currencyBreakdown = document.getElementById('currencyBreakdown');

const navItems = document.querySelectorAll('.nav-item');
const tabPanes = document.querySelectorAll('.tab-pane');
const pageHeading = document.getElementById('pageHeading');
const pageSubheading = document.getElementById('pageSubheading');

// Modal Elements
const newExpenseModal = document.getElementById('newExpenseModal');
const openModalBtn = document.getElementById('openNewExpenseModal');
const closeModalBtn = document.getElementById('closeExpenseModal');
const cancelModalBtn = document.getElementById('cancelExpenseModal');
const newExpenseForm = document.getElementById('newExpenseForm');
const expAmountInput = document.getElementById('expAmount');
const expCurrencySelect = document.getElementById('expCurrency');
const previewAmountUsd = document.getElementById('previewAmountUsd');

const auditModal = document.getElementById('auditModal');
const closeAuditModalBtn = document.getElementById('closeAuditModal');
const closeAuditBtn = document.getElementById('closeAuditBtn');
const auditModalBody = document.getElementById('auditModalBody');

// Filter Elements
const ledgerSearch = document.getElementById('ledgerSearch');
const filterCategory = document.getElementById('filterCategory');
const filterStatus = document.getElementById('filterStatus');
const refreshBtn = document.getElementById('refreshBtn');

// FX Calculator in sidebar
const fxCalcAmount = document.getElementById('fxCalcAmount');
const fxCalcFrom = document.getElementById('fxCalcFrom');
const fxCalcResult = document.getElementById('fxCalcResult');

// Navigation Tabs
navItems.forEach(item => {
  item.addEventListener('click', () => {
    navItems.forEach(n => n.classList.remove('active'));
    tabPanes.forEach(p => p.classList.remove('active'));

    item.classList.add('active');
    const tabId = item.dataset.tab;

    if (tabId === 'ledger') {
      document.getElementById('tabLedger').classList.add('active');
      pageHeading.textContent = 'Expense Ledger';
      pageSubheading.textContent = 'Multi-currency disbursement, voucher tracking, and approval workflow';
      loadExpenses();
    } else if (tabId === 'budgets') {
      document.getElementById('tabBudgets').classList.add('active');
      pageHeading.textContent = 'Budget Pacing';
      pageSubheading.textContent = 'Real-time category burn rate and overage threshold monitoring';
      loadBudgets();
    } else if (tabId === 'analytics') {
      document.getElementById('tabAnalytics').classList.add('active');
      pageHeading.textContent = 'Financial Analytics';
      pageSubheading.textContent = 'Institutional spending distribution across operational expense centers';
      loadAnalytics();
    }
  });
});

// Fetch FX rates
async function fetchFxRates() {
  try {
    const res = await fetch(`${API_BASE}/api/forex/rates`);
    if (res.ok) {
      const data = await res.json();
      cachedRates = data.rates;
    }
  } catch (err) {
    console.warn('Using cached FX rates');
  }
}

// Update FX Calculator
function updateFxCalculator() {
  const amount = parseFloat(fxCalcAmount.value) || 0;
  const from = fxCalcFrom.value;
  const rate = cachedRates[from] || 1.0;
  const usd = (amount * rate).toFixed(2);
  fxCalcResult.textContent = `= $${Number(usd).toLocaleString('en-US', { minimumFractionDigits: 2 })} USD`;
}

fxCalcAmount.addEventListener('input', updateFxCalculator);
fxCalcFrom.addEventListener('change', updateFxCalculator);

// Real-time USD preview in modal
function updatePreviewUsd() {
  const amt = parseFloat(expAmountInput.value) || 0;
  const curr = expCurrencySelect.value;
  const rate = cachedRates[curr] || 1.0;
  const usd = (amt * rate).toFixed(2);
  previewAmountUsd.textContent = `$${Number(usd).toLocaleString('en-US', { minimumFractionDigits: 2 })} USD`;
}

expAmountInput.addEventListener('input', updatePreviewUsd);
expCurrencySelect.addEventListener('change', updatePreviewUsd);

// Open / Close Modal
openModalBtn.addEventListener('click', () => {
  newExpenseModal.classList.add('open');
  document.getElementById('expDate').value = new Date().toISOString().slice(0, 10);
  updatePreviewUsd();
});

function closeModal() {
  newExpenseModal.classList.remove('open');
  newExpenseForm.reset();
}

closeModalBtn.addEventListener('click', closeModal);
cancelModalBtn.addEventListener('click', closeModal);

// Close Audit Modal
function closeAudit() {
  auditModal.classList.remove('open');
}
closeAuditModalBtn.addEventListener('click', closeAudit);
closeAuditBtn.addEventListener('click', closeAudit);

// Load Expenses
async function loadExpenses() {
  try {
    let url = `${API_BASE}/api/expenses?`;
    if (filterCategory.value) url += `category=${encodeURIComponent(filterCategory.value)}&`;
    if (filterStatus.value) url += `status=${encodeURIComponent(filterStatus.value)}&`;
    if (ledgerSearch.value.trim()) url += `search=${encodeURIComponent(ledgerSearch.value.trim())}&`;

    const res = await fetch(url);
    const data = await res.json();
    renderExpenses(data.expenses);
  } catch (err) {
    expenseTableBody.innerHTML = `<tr><td colspan="8" class="text-center text-crimson">Failed to load expenses</td></tr>`;
  }
}

function renderExpenses(expenses) {
  if (!expenses || expenses.length === 0) {
    expenseTableBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted" style="padding: 2.5rem;">No expense vouchers found matching filter criteria.</td></tr>`;
    return;
  }

  expenseTableBody.innerHTML = expenses.map(exp => {
    const statusClass = `badge-${exp.status.toLowerCase()}`;
    const formattedOrig = `${exp.currency} ${Number(exp.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    const formattedUsd = `$${Number(exp.amount_usd).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;

    let actionBtns = `<button class="btn-xs" onclick="viewAuditTrail('${exp.id}')">Audit</button>`;

    if (exp.status === 'DRAFT') {
      actionBtns += `<button class="btn-xs btn-xs-primary" onclick="updateStatus('${exp.id}', 'SUBMITTED')">Submit</button>`;
    } else if (exp.status === 'SUBMITTED') {
      actionBtns += `<button class="btn-xs btn-xs-primary" onclick="updateStatus('${exp.id}', 'APPROVED')">Approve</button>`;
      actionBtns += `<button class="btn-xs btn-xs-danger" onclick="updateStatus('${exp.id}', 'REJECTED')">Reject</button>`;
    } else if (exp.status === 'APPROVED') {
      actionBtns += `<button class="btn-xs btn-xs-primary" onclick="updateStatus('${exp.id}', 'REIMBURSED')">Reimburse</button>`;
    }

    return `
      <tr>
        <td style="font-family: var(--font-mono); font-size: 0.8rem;">${exp.date}</td>
        <td>
          <div style="font-weight: 600;">${escapeHtml(exp.title)}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(exp.merchant)}</div>
        </td>
        <td><span style="font-size: 0.8rem; background: var(--bg-surface-elevated); padding: 2px 8px; border-radius: 4px;">${exp.category}</span></td>
        <td style="font-family: var(--font-mono); font-weight: 600;">${formattedOrig}</td>
        <td style="font-family: var(--font-mono); color: var(--emerald); font-weight: 600;">${formattedUsd}</td>
        <td><span class="badge ${statusClass}">${exp.status}</span></td>
        <td style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted);">${exp.receipt_ref || '—'}</td>
        <td>
          <div class="action-buttons">
            ${actionBtns}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

// Update Expense Status
window.updateStatus = async function(id, nextStatus) {
  try {
    const res = await fetch(`${API_BASE}/api/expenses/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: nextStatus,
        performed_by: 'Financial Controller',
        notes: `Authorized transition to ${nextStatus}`
      })
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Transition error: ${err.detail}`);
      return;
    }

    loadExpenses();
    loadAnalytics();
  } catch (err) {
    alert('Failed to update expense status');
  }
};

// View Audit Trail
window.viewAuditTrail = async function(id) {
  try {
    const res = await fetch(`${API_BASE}/api/expenses/${id}`);
    if (!res.ok) return;
    const data = await res.json();

    let logsHtml = data.audit_logs.map(log => `
      <div style="padding: 0.75rem 0; border-bottom: 1px solid var(--border-subtle); display: flex; flex-direction: column; gap: 0.2rem;">
        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted);">
          <span>${new Date(log.timestamp).toLocaleString()}</span>
          <span style="color: var(--emerald); font-weight: 600;">${log.performed_by}</span>
        </div>
        <div style="font-family: var(--font-mono); font-weight: 600; font-size: 0.85rem; color: #fff;">${log.action}</div>
        <div style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(log.notes)}</div>
      </div>
    `).join('');

    auditModalBody.innerHTML = `
      <div style="padding: 1rem 1.5rem; max-height: 400px; overflow-y: auto;">
        <div style="margin-bottom: 1rem;">
          <h4 style="font-size: 1.1rem; color: #fff;">${escapeHtml(data.title)}</h4>
          <p style="font-size: 0.85rem; color: var(--text-muted);">Merchant: ${escapeHtml(data.merchant)} | Amount: $${Number(data.amount_usd).toFixed(2)} USD</p>
        </div>
        <div style="font-size: 0.8rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 0.5rem;">Event History</div>
        ${logsHtml || '<p class="text-muted">No audit logs available.</p>'}
      </div>
    `;

    auditModal.classList.add('open');
  } catch (err) {
    console.error(err);
  }
};

// Form Submit: Create Expense
newExpenseForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  const payload = {
    title: document.getElementById('expTitle').value.trim(),
    category: document.getElementById('expCategory').value,
    merchant: document.getElementById('expMerchant').value.trim(),
    amount: parseFloat(expAmountInput.value),
    currency: expCurrencySelect.value,
    date: document.getElementById('expDate').value || undefined,
    receipt_ref: document.getElementById('expReceiptRef').value.trim() || undefined,
    tax_amount: parseFloat(document.getElementById('expTax').value) || 0.0,
    notes: document.getElementById('expNotes').value.trim() || undefined,
  };

  try {
    const res = await fetch(`${API_BASE}/api/expenses`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Error creating expense: ${err.detail}`);
      return;
    }

    closeModal();
    loadExpenses();
    loadAnalytics();
  } catch (err) {
    alert('Failed to submit expense voucher.');
  }
});

// Load Budgets
async function loadBudgets() {
  try {
    const res = await fetch(`${API_BASE}/api/budgets`);
    const data = await res.json();

    budgetGrid.innerHTML = data.budgets.map(b => {
      let progressClass = 'progress-green';
      let statusBadge = `<span class="badge badge-approved">ON TRACK</span>`;

      if (b.status === 'WARNING') {
        progressClass = 'progress-amber';
        statusBadge = `<span class="badge badge-submitted">PACING HIGH (80%+)</span>`;
      } else if (b.status === 'EXCEEDED') {
        progressClass = 'progress-crimson';
        statusBadge = `<span class="badge badge-rejected">OVER BUDGET (+$${b.overage_amount_usd.toFixed(2)})</span>`;
      }

      const pctWidth = Math.min(100, b.pacing_percentage);

      return `
        <div class="budget-card">
          <div class="budget-header">
            <span class="budget-title">${escapeHtml(b.category)}</span>
            ${statusBadge}
          </div>
          <div class="budget-numbers">
            <span class="budget-spent">$${b.spent_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            <span class="budget-limit">Limit: $${b.monthly_limit_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill ${progressClass}" style="width: ${pctWidth}%;"></div>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted);">
            <span>${b.pacing_percentage}% consumed</span>
            <span>$${b.remaining_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })} remaining</span>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    budgetGrid.innerHTML = `<p class="text-crimson">Failed to load budgets.</p>`;
  }
}

// Load Analytics & KPI strip
async function loadAnalytics() {
  try {
    const res = await fetch(`${API_BASE}/api/analytics/summary`);
    const data = await res.json();

    kpiTotalSpend.textContent = `$${Number(data.total_spend_usd).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    kpiRecordCount.textContent = data.total_expense_records;

    const pending = (data.breakdown_by_status['SUBMITTED']?.count || 0) + (data.breakdown_by_status['DRAFT']?.count || 0);
    kpiPendingCount.textContent = pending;

    // Check overruns
    const bRes = await fetch(`${API_BASE}/api/budgets`);
    const bData = await bRes.json();
    const overruns = bData.budgets.filter(b => b.is_over_budget).length;
    kpiOverrunCount.textContent = overruns;

    // Render category spend bars
    const maxSpend = Math.max(...data.breakdown_by_category.map(c => c.total_usd), 1);
    categorySpendBars.innerHTML = data.breakdown_by_category.map(cat => {
      const widthPct = Math.round((cat.total_usd / maxSpend) * 100);
      return `
        <div class="breakdown-row">
          <div class="breakdown-info">
            <span>${escapeHtml(cat.category)}</span>
            <span style="font-family: var(--font-mono); font-weight: 600;">$${cat.total_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })} (${cat.count})</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill progress-green" style="width: ${widthPct}%;"></div>
          </div>
        </div>
      `;
    }).join('');

    // Render currency breakdown pills
    currencyBreakdown.innerHTML = data.breakdown_by_currency.map(c => `
      <div class="curr-pill">
        <span class="curr-pill-code">${c.currency}</span>
        <span class="curr-pill-val">${c.original_amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
        <span style="font-size: 0.72rem; color: var(--text-subtle);">${c.count} vouchers</span>
      </div>
    `).join('');

  } catch (err) {
    console.warn('Analytics update skipped');
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// Filter listeners
filterCategory.addEventListener('change', loadExpenses);
filterStatus.addEventListener('change', loadExpenses);
ledgerSearch.addEventListener('input', () => {
  clearTimeout(window.searchTimeout);
  window.searchTimeout = setTimeout(loadExpenses, 250);
});
refreshBtn.addEventListener('click', () => {
  loadExpenses();
  loadAnalytics();
  loadBudgets();
});

// Initialization
fetchFxRates();
loadExpenses();
loadAnalytics();
